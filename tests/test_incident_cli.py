from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from automation.incident_postmortem.__main__ import main, write_new_report
from automation.incident_postmortem.logs import IncidentError


ROOT = Path(__file__).resolve().parents[1]


class IncidentCliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / "report.md"
        self.args = [
            "--input", str(ROOT / "examples/incident_response/service-incident.txt"),
            "--format", "text", "--output", str(self.output),
        ]

    def run_cli(self, *mode):
        with redirect_stdout(StringIO()) as out, redirect_stderr(StringIO()) as err:
            result = main([*self.args, *mode])
        return result, out.getvalue(), err.getvalue()

    def test_offline_mode_writes_a_report_without_importing_or_calling_sdk(self):
        with patch("automation.incident_postmortem.__main__.analyze_with_copilot") as sdk:
            code, output, error = self.run_cli("--offline")
        self.assertEqual(code, 0, error)
        sdk.assert_not_called()
        self.assertIn("Unapproved draft written", output)
        self.assertIn("Evidence only; no model call", self.output.read_text())

    def test_jsonl_cli_path_works(self):
        self.args[1] = str(ROOT / "examples/incident_response/service-incident.jsonl")
        self.args[3] = "jsonl"
        code, _, error = self.run_cli("--offline")
        self.assertEqual(code, 0, error)
        self.assertIn("Event count: 4", self.output.read_text())

    def test_model_upload_requires_explicit_consent(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            main([*self.args, "--model", "example-model"])
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_existing_output_is_not_overwritten_and_no_model_is_called(self):
        self.output.write_text("keep me", encoding="utf-8")
        with patch("automation.incident_postmortem.__main__.analyze_with_copilot") as sdk:
            code, _, error = self.run_cli("--model", "example", "--allow-model-upload")
        self.assertEqual(code, 1)
        self.assertIn("already exists", error)
        self.assertEqual(self.output.read_text(), "keep me")
        sdk.assert_not_called()

    def test_sdk_failure_is_not_an_offline_fallback(self):
        sdk = AsyncMock(side_effect=IncidentError("SDK request failed"))
        with patch("automation.incident_postmortem.__main__.analyze_with_copilot", sdk):
            code, output, error = self.run_cli("--model", "example", "--allow-model-upload")
        self.assertEqual(code, 1)
        self.assertIn("SDK request failed", error)
        self.assertEqual(output, "")
        self.assertFalse(self.output.exists())

    def test_broken_output_symlink_is_not_replaced(self):
        target = Path(self.directory.name) / "missing.md"
        self.output.symlink_to(target)
        code, _, error = self.run_cli("--offline")
        self.assertEqual(code, 1)
        self.assertIn("already exists", error)
        self.assertTrue(self.output.is_symlink())
        self.assertFalse(target.exists())

    def test_bad_input_creates_no_report(self):
        self.args[1] = str(Path(self.directory.name) / "missing.log")
        code, _, error = self.run_cli("--offline")
        self.assertEqual(code, 1)
        self.assertIn("regular log file", error)
        self.assertFalse(self.output.exists())

    def test_nonfinite_or_unbounded_timeouts_are_rejected(self):
        for timeout in ("nan", "inf", "0", "-1", "601", "bad"):
            with self.subTest(timeout=timeout), redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                main([*self.args, "--offline", "--timeout", timeout])

    def test_atomic_publication_does_not_replace_a_racing_output(self):
        self.output.write_text("keep me", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            write_new_report(self.output, "replacement")
        self.assertEqual(self.output.read_text(), "keep me")
        self.assertEqual(list(Path(self.directory.name).glob(".incident-*.tmp")), [])

    def test_failed_publication_leaves_no_partial_report_or_temporary_file(self):
        with patch("automation.incident_postmortem.__main__.os.link", side_effect=OSError("disk failure")):
            code, output, error = self.run_cli("--offline")
        self.assertEqual(code, 1)
        self.assertIn("disk failure", error)
        self.assertEqual(output, "")
        self.assertFalse(self.output.exists())
        self.assertEqual(list(Path(self.directory.name).glob(".incident-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
