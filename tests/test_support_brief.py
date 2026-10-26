from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from automation.sdk import SdkError
from automation.support_brief.__main__ import main
from automation.support_brief.evidence import BriefError, MAX_BYTES, read_evidence
from automation.support_brief.report import (
    analysis_schema, model_prompt, render_report, validate_analysis,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/support_brief/signals.json"


def model_response():
    return {
        "summary": [{"statement": "Two authored reports describe stale queued labels.", "evidence": ["S01", "S02"]}],
        "duplicate_candidates": [{
            "statement": "S01 and S02 may overlap; traces are needed to establish a shared failure.",
            "evidence": ["S01", "S02"],
        }],
        "next_steps": ["Collect a reconnect trace and exact browser versions."],
        "open_questions": ["Does the download failure have a separate cause?"],
    }


class SupportEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.evidence = read_evidence(FIXTURE)

    def read_data(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signals.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return read_evidence(path)

    def test_fixture_ids_fingerprint_and_gaps(self):
        self.assertEqual([s.id for s in self.evidence.signals], ["S01", "S02", "S03"])
        self.assertEqual(self.evidence.sha256, hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        self.assertEqual(self.evidence.signals[1].gaps, (
            "expected behavior", "reproduction steps", "environment", "reported impact",
        ))
        self.assertEqual(self.evidence.signals[0].gaps, ())

    def test_invalid_records_are_rejected(self):
        original = json.loads(FIXTURE.read_text())
        mutations = [
            lambda d: d.update(extra=True),
            lambda d: d.update(signals=[]),
            lambda d: d.update(signals=d["signals"] * 9),
            lambda d: d["signals"][0].update(extra=True),
            lambda d: d["signals"][0].pop("expected"),
            lambda d: d["signals"][0].update(id="S01<script>"),
            lambda d: d["signals"][0].update(id=12),
            lambda d: d["signals"][1].update(id="S01"),
            lambda d: d["signals"][0].update(observed=" "),
            lambda d: d["signals"][0].update(observed="x" * 1001),
            lambda d: d["signals"][0].update(title="x" * 161),
            lambda d: d["signals"][0].update(area="x" * 81),
            lambda d: d["signals"][0].update(environment="x" * 501),
            lambda d: d["signals"][0].update(expected=None),
            lambda d: d["signals"][0].update(reproduction="step"),
            lambda d: d["signals"][0].update(reproduction=[""] * 2),
            lambda d: d["signals"][0].update(reproduction=["x"] * 9),
            lambda d: d["signals"][0].update(reproduction=["x" * 501]),
            lambda d: d["signals"][0].update(observed="\ud800"),
            lambda d: d["signals"][0].update(observed="hidden\x1b"),
            lambda d: d["signals"][0].update(observed="hidden\x85"),
        ]
        for mutate in mutations:
            data = json.loads(json.dumps(original))
            mutate(data)
            with self.subTest(data=data), self.assertRaises(BriefError):
                self.read_data(data)

    def test_byte_limit_duplicate_keys_and_malformed_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for raw in (
                b"x" * (MAX_BYTES + 1), b'{"signals":[],"signals":[]}', b"[]",
                b'{"signals":NaN}', b"{", b"\xff",
            ):
                path.write_bytes(raw)
                with self.subTest(raw=raw[:50]), self.assertRaises((BriefError, UnicodeError)):
                    read_evidence(path)
            with self.assertRaises(BriefError):
                read_evidence(Path(directory))

    def test_twenty_five_unique_records_are_supported(self):
        signal = json.loads(FIXTURE.read_text())["signals"][0]
        data = {"signals": [dict(signal, id=f"S{number:02}") for number in range(25)]}
        self.assertEqual(len(self.read_data(data).signals), 25)

    def test_render_preserves_sources_unknowns_and_escapes_markup(self):
        changed = replace(self.evidence.signals[0], observed="<script>alert(1)</script> [publish](https://invalid.test)")
        report = render_report(replace(self.evidence, signals=(changed,) + self.evidence.signals[1:]), None, None)
        self.assertIn("Evidence only; no model call", report)
        self.assertIn("Not supplied", report)
        self.assertIn("No duplicate candidates proposed", report)
        for signal in self.evidence.signals:
            self.assertIn(f'id="{signal.id.lower()}"', report)
        self.assertNotIn("<script>", report)
        self.assertNotIn("[publish](", report)
        self.assertIn(self.evidence.sha256, report)
        self.assertIn("Human review required", report)
        with self.assertRaises(BriefError):
            render_report(self.evidence, None, "model")

    def test_prompt_and_schema_are_bounded_and_evidence_specific(self):
        schema = analysis_schema(self.evidence)
        self.assertEqual(set(schema["required"]), set(model_response()))
        ids = schema["properties"]["summary"]["items"]["properties"]["evidence"]["items"]["enum"]
        self.assertEqual(ids, ["S01", "S02", "S03"])
        self.assertIn('"reported_impact"', model_prompt(self.evidence))
        oversized = replace(self.evidence.signals[0], observed="x" * 50_001)
        with self.assertRaises(BriefError):
            model_prompt(replace(self.evidence, signals=(oversized,)))

    def test_valid_analysis_and_rendered_citations(self):
        analysis = validate_analysis(json.dumps(model_response()), self.evidence)
        report = render_report(self.evidence, analysis, "test-model")
        self.assertIn("[S01](#s01), [S02](#s02)", report)
        self.assertIn("requested model: test-model", report)
        self.assertIn("unverified", report)

    def test_invalid_analysis_fails_closed(self):
        mutations = [
            lambda d: d.pop("open_questions"),
            lambda d: d.update(extra=[]),
            lambda d: d.update(summary=[]),
            lambda d: d.update(summary=d["summary"] * 9),
            lambda d: d.update(summary={}),
            lambda d: d["summary"][0].update(extra="x"),
            lambda d: d["summary"][0].update(statement=""),
            lambda d: d["summary"][0].update(statement="x" * 1001),
            lambda d: d["summary"][0].update(statement="\ud800"),
            lambda d: d["summary"][0].update(evidence=["S99"]),
            lambda d: d["summary"][0].update(evidence=[False]),
            lambda d: d["summary"][0].update(evidence=["S01", "S01"]),
            lambda d: d["summary"][0].update(evidence=[]),
            lambda d: d["duplicate_candidates"][0].update(evidence=["S01"]),
            lambda d: d.update(next_steps=[]),
            lambda d: d.update(open_questions=[{}]),
        ]
        for mutate in mutations:
            data = model_response()
            mutate(data)
            with self.subTest(data=data), self.assertRaises(BriefError):
                validate_analysis(json.dumps(data), self.evidence)
        for raw in ("x" * 40_001, '{"summary":[],"summary":[]}', "[]"):
            with self.assertRaises(BriefError):
                validate_analysis(raw, self.evidence)


class SupportCliTests(unittest.TestCase):
    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = main(list(args))
        return result, out.getvalue(), err.getvalue()

    def test_offline_no_network_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "brief.md"
            args = ("--input", str(FIXTURE), "--output", str(output), "--offline")
            with patch("automation.support_brief.__main__.request_analysis", new_callable=AsyncMock) as request:
                self.assertEqual(self.invoke(*args)[0], 0)
                request.assert_not_called()
                contents = output.read_text()
                result, _, error = self.invoke(*args)
                self.assertEqual(result, 1)
                self.assertIn("already exists", error)
                self.assertEqual(output.read_text(), contents)
                output.unlink()
                output.symlink_to(Path(directory) / "missing.md")
                self.assertEqual(self.invoke(*args)[0], 1)

    def test_sdk_uses_shared_transport_and_validates_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "brief.md"
            args = ("--input", str(FIXTURE), "--output", str(output), "--model", "test-model", "--allow-model-upload")
            with patch("automation.support_brief.__main__.request_analysis", new_callable=AsyncMock) as request:
                request.return_value = json.dumps(model_response())
                self.assertEqual(self.invoke(*args)[0], 0)
                request.assert_awaited_once()
                self.assertEqual(request.call_args.args[3:], ("test-model", 120.0))
                output.unlink()
                for response in ("{}", "[]"):
                    request.return_value = response
                    self.assertEqual(self.invoke(*args)[0], 1)
                    self.assertFalse(output.exists())
                request.side_effect = SdkError("deliberate transport failure")
                result, _, error = self.invoke(*args)
                self.assertEqual(result, 1)
                self.assertIn("deliberate transport failure", error)
                self.assertFalse(output.exists())

    def test_requires_consent_and_a_valid_mode(self):
        for mode in (
            [], ["--model", "test-model"], ["--model", " ", "--allow-model-upload"],
            ["--offline", "--allow-model-upload"],
            ["--offline", "--model", "test-model"],
            ["--offline", "--timeout", "nan"],
        ):
            with self.subTest(mode=mode), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--input", str(FIXTURE), "--output", "unused.md", *mode])

    def test_invalid_input_and_missing_parent_leave_no_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "brief.md"
            result, _, error = self.invoke("--input", directory, "--output", str(output), "--offline")
            self.assertEqual(result, 1)
            self.assertIn("regular", error)
            self.assertFalse(output.exists())
            self.assertEqual(self.invoke(
                "--input", str(FIXTURE), "--output", str(Path(directory) / "missing/out.md"), "--offline",
            )[0], 1)


if __name__ == "__main__":
    unittest.main()
