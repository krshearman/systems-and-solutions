from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.check_refactor_guard import APPROVED, ROOT, WORKSPACE
from tools.check_refactor_guard import RefactorPolicyError, check_source


BEFORE = ROOT / "examples/refactor_guard/before.py"
CHECKER = ROOT / "tools/check_refactor_guard.py"


class RefactorPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.approved = APPROVED.read_text(encoding="utf-8")

    def test_approved_fixture_passes(self):
        check_source(self.approved, self.approved)

    def test_fixtures_differ_only_by_the_declared_replacements(self):
        expected = BEFORE.read_text(encoding="utf-8")
        expected = expected.replace(
            "examples.refactor_guard.legacy_api",
            "examples.refactor_guard.event_api",
        )
        expected = expected.replace("normalize_level", "normalize_severity")
        expected = expected.replace("parse_line", "parse_record")
        check_source(expected, self.approved)

    def test_checked_in_workspace_is_approved(self):
        check_source(WORKSPACE.read_text(encoding="utf-8"), self.approved)

    def test_legacy_fixture_is_rejected(self):
        with self.assertRaisesRegex(RefactorPolicyError, "approved modernization"):
            check_source(BEFORE.read_text(encoding="utf-8"), self.approved)

    def test_formatting_and_comments_are_not_executable_changes(self):
        candidate = "# parse_line is mentioned only in a comment.\n\n" + self.approved
        candidate = candidate.replace(
            "counts: dict[str, int] = {}", "counts: dict[str,int]={}"
        )
        check_source(candidate, self.approved)

    def test_unrelated_executable_changes_are_rejected(self):
        mutations = {
            "new import": "import os\n" + self.approved,
            "changed public name": self.approved.replace("def summarize(", "def count("),
            "changed return": self.approved.replace("return counts", "return {}"),
            "changed count": self.approved.replace("+ 1", "+ 2"),
            "changed blank handling": self.approved.replace(
                "if not line.strip():", "if not line:"
            ),
            "new side effect": self.approved.replace(
                "return counts", "print(counts)\n    return counts"
            ),
        }
        for name, candidate in mutations.items():
            with self.subTest(mutation=name):
                with self.assertRaises(RefactorPolicyError):
                    check_source(candidate, self.approved)

    def test_mixed_legacy_and_modern_calls_are_rejected(self):
        with self.assertRaises(RefactorPolicyError):
            check_source(
                self.approved.replace(
                    "normalized = normalize_severity(severity)",
                    "normalized = normalize_level(severity)",
                ),
                self.approved,
            )

    def test_syntax_error_reports_its_location(self):
        with self.assertRaisesRegex(
            RefactorPolicyError, "Invalid candidate syntax on line 1"
        ):
            check_source("def broken(", self.approved)

    def test_candidate_is_parsed_not_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "must-not-exist"
            candidate = f"open({str(marker)!r}, 'w').write('executed')\n"
            with self.assertRaises(RefactorPolicyError):
                check_source(candidate, self.approved)
            self.assertFalse(marker.exists())


class RefactorGateCliTests(unittest.TestCase):
    def run_gate(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(CHECKER), *map(str, args)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_default_workspace_passes(self):
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS:", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_legacy_fixture_fails_with_nonzero_exit(self):
        result = self.run_gate(BEFORE)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL: Candidate differs from the approved modernization", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_approved_fixture_passes_with_zero_exit(self):
        result = self.run_gate(APPROVED)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS:", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_invalid_syntax_is_an_explicit_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "broken.py"
            candidate.write_text("def broken(", encoding="utf-8")
            result = self.run_gate(candidate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL: Invalid candidate syntax on line 1", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_missing_candidate_is_an_explicit_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_gate(Path(directory) / "missing.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL:", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_invalid_encoding_is_an_explicit_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "invalid.py"
            candidate.write_bytes(b"\xff")
            result = self.run_gate(candidate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL:", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
