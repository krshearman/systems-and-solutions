import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from automation.incident_postmortem import logs
from automation.incident_postmortem.logs import IncidentError, read_evidence


SAMPLES = Path(__file__).resolve().parents[1] / "examples/incident_response"


class IncidentLogTests(unittest.TestCase):
    def parse(self, content, log_format="text"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "incident.log"
            path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
            return read_evidence(path, log_format)

    def test_sample_formats_produce_the_same_sorted_events(self):
        text = read_evidence(SAMPLES / "service-incident.txt", "text")
        structured = read_evidence(SAMPLES / "service-incident.jsonl", "jsonl")
        self.assertEqual(text.events, structured.events)
        self.assertEqual([event.line for event in text.events], [2, 3, 4, 1])
        self.assertEqual([event.level for event in text.events], ["INFO", "ERROR", "WARNING", "INFO"])

    def test_offsets_are_normalized_and_ties_keep_source_order(self):
        evidence = self.parse(
            "2026-10-15T10:00:00+01:00 err first\n\n"
            "2026-10-15T09:00:00Z INFO second\n"
            "2026-10-15T08:59:59.123456Z warn earlier\n"
        )
        self.assertEqual([event.line for event in evidence.events], [4, 1, 3])
        self.assertEqual(evidence.events[1].utc_timestamp, "2026-10-15T09:00:00Z")
        self.assertEqual(evidence.events[2].evidence_id, "L3")

    def test_fingerprint_uses_original_bytes_and_message_is_preserved(self):
        content = b"2026-10-15T09:00:00Z INFO hello|world  \r\n"
        evidence = self.parse(content)
        self.assertEqual(evidence.sha256, hashlib.sha256(content).hexdigest())
        self.assertEqual(evidence.events[0].message, "hello|world  ")

    def test_malformed_or_naive_timestamps_are_rejected(self):
        for timestamp in (
            "2026-10-15T09:00:00", "2026-99-15T09:00:00Z",
            "2026-10-15T09:00:00+24:00", "2026-10-15T09:00:00.1234567Z",
            "0001-01-01T00:00:00+01:00",
        ):
            with self.subTest(timestamp=timestamp), self.assertRaises(IncidentError):
                self.parse(f"{timestamp} INFO example")

    def test_jsonl_rejects_missing_extra_duplicate_and_wrong_type_fields(self):
        valid = {"timestamp": "2026-10-15T09:00:00Z", "level": "INFO", "message": "example"}
        cases = [
            json.dumps({**valid, "extra": True}),
            json.dumps({"timestamp": valid["timestamp"], "message": "example"}),
            json.dumps({**valid, "message": 42}),
            json.dumps({**valid, "level": ["INFO"]}),
            '{"timestamp":"2026-10-15T09:00:00Z","level":"INFO","message":"a","message":"b"}',
            "[]", "{broken", '{"message":NaN}',
        ]
        for record in cases:
            with self.subTest(record=record), self.assertRaises(IncidentError):
                self.parse(record, "jsonl")

    def test_invalid_record_is_not_silently_skipped(self):
        with self.assertRaisesRegex(IncidentError, "Line 2"):
            self.parse("2026-10-15T09:00:00Z INFO first\nbroken\n")

    def test_empty_invalid_encoding_and_invalid_format_fail(self):
        for content in ("", "\n  \n", b"\xff"):
            with self.subTest(content=content), self.assertRaises(IncidentError):
                self.parse(content)
        with self.assertRaises(IncidentError):
            self.parse("example", "unknown")

    def test_input_limits_fail_instead_of_truncating(self):
        content = "2026-10-15T09:00:00Z INFO example\n"
        with patch.object(logs, "MAX_BYTES", 8), self.assertRaisesRegex(IncidentError, "nothing was truncated"):
            self.parse(content)
        with patch.object(logs, "MAX_EVENTS", 1), self.assertRaisesRegex(IncidentError, "nothing was truncated"):
            self.parse(content * 2)
        with patch.object(logs, "MAX_MESSAGE", 2), self.assertRaisesRegex(IncidentError, "message exceeds"):
            self.parse(content)

    def test_exact_input_limits_are_accepted(self):
        content = "2026-10-15T09:00:00Z INFO example\n"
        with (
            patch.object(logs, "MAX_BYTES", len(content.encode())),
            patch.object(logs, "MAX_EVENTS", 1),
            patch.object(logs, "MAX_MESSAGE", len("example")),
        ):
            self.assertEqual(len(self.parse(content).events), 1)

    def test_control_characters_and_surrogates_are_rejected(self):
        for message in ("\x1b[31mexample", "\ud800", "\x9bexample"):
            record = json.dumps({
                "timestamp": "2026-10-15T09:00:00Z", "level": "INFO", "message": message,
            })
            with self.subTest(message=repr(message)), self.assertRaises(IncidentError):
                self.parse(record, "jsonl")

    def test_json_line_numbers_are_not_split_by_unicode_message_separators(self):
        record = '{"timestamp":"2026-10-15T09:00:00Z","level":"INFO","message":"hello\u2028world"}'
        evidence = self.parse(record, "jsonl")
        self.assertEqual(evidence.events[0].line, 1)
        self.assertEqual(evidence.events[0].message, "hello\u2028world")

    def test_deeply_nested_json_fails_explicitly(self):
        with self.assertRaisesRegex(IncidentError, "Line 1:"):
            self.parse("[" * 2000 + "0" + "]" * 2000, "jsonl")

    def test_decoder_recursion_errors_are_reported_explicitly(self):
        with patch.object(logs.json, "loads", side_effect=RecursionError):
            with self.assertRaisesRegex(IncidentError, "invalid JSON"):
                self.parse("{}", "jsonl")


if __name__ == "__main__":
    unittest.main()
