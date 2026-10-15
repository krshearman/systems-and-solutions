from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path
import unittest

from automation.incident_postmortem.logs import Event, Evidence, IncidentError, read_evidence
from automation.incident_postmortem.report import (
    analysis_schema, model_prompt, render_report, validate_analysis,
)


SAMPLE = Path(__file__).resolve().parents[1] / "examples/incident_response/service-incident.txt"


def valid_analysis():
    return {
        "executive_summary": [{
            "statement": "The synthetic probe logged HTTP 503.",
            "evidence": ["L3"],
        }],
        "impact": [],
        "suspected_causes": [],
        "follow_up_actions": ["Investigate the recorded probe failure."],
        "open_questions": ["Was customer traffic affected?"],
    }


class IncidentReportTests(unittest.TestCase):
    def setUp(self):
        self.evidence = read_evidence(SAMPLE, "text")

    def test_analysis_is_validated_and_citations_link_to_original_lines(self):
        analysis = validate_analysis(json.dumps(valid_analysis()), self.evidence)
        report = render_report(self.evidence, analysis, "example-model")
        self.assertIn("[L3](#l3)", report)
        self.assertIn('<a id="l3"></a>L3', report)
        self.assertIn("Owner: Unassigned", report)
        self.assertIn("Unapproved draft", report)
        self.assertIn("unverified hypotheses", report)
        self.assertIn(self.evidence.sha256, report)

    def test_timeline_is_deterministic_and_not_generated_by_the_model(self):
        report = render_report(self.evidence)
        self.assertLess(report.index('id="l2"'), report.index('id="l3"'))
        self.assertLess(report.index('id="l3"'), report.index('id="l4"'))
        self.assertLess(report.index('id="l4"'), report.index('id="l1"'))
        self.assertEqual(report, render_report(self.evidence))
        self.assertIn("Evidence only; no model call", report)
        self.assertIn("not an outage duration", report)
        self.assertNotIn("three-minute outage", report)

    def test_unknown_empty_duplicate_and_wrong_type_citations_fail(self):
        for citations in ([], ["L999"], ["L3", "L3"], [3], [[3]], "L3"):
            data = valid_analysis()
            data["executive_summary"][0]["evidence"] = citations
            with self.subTest(citations=citations), self.assertRaises(IncidentError):
                validate_analysis(json.dumps(data), self.evidence)

    def test_missing_extra_or_invalid_sections_fail(self):
        invalid = [
            {}, {**valid_analysis(), "timeline": []},
            {**valid_analysis(), "executive_summary": []},
            {**valid_analysis(), "open_questions": "unknown"},
            {**valid_analysis(), "follow_up_actions": [""]},
            {**valid_analysis(), "impact": [{"statement": "unsupported"}]},
            {**valid_analysis(), "open_questions": ["x" * 601]},
        ]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(IncidentError):
                validate_analysis(json.dumps(data), self.evidence)

    def test_non_json_duplicate_and_oversized_output_fail(self):
        for raw in ("not JSON", "```json\n{}\n```", '{"a":1,"a":2}', "x" * 40001):
            with self.subTest(raw=raw[:30]), self.assertRaises(IncidentError):
                validate_analysis(raw, self.evidence)

    def test_log_and_model_markup_is_rendered_as_text(self):
        event = Event(1, datetime(2026, 10, 15, tzinfo=UTC), "INFO", "<img src=x> | [click](https://example.com)")
        evidence = Evidence("<script>.log", "0" * 64, (event,))
        data = valid_analysis()
        data["executive_summary"][0] = {"statement": "<script>alert(1)</script>", "evidence": ["L1"]}
        report = render_report(evidence, validate_analysis(json.dumps(data), evidence), "example")
        self.assertNotIn("<img", report)
        self.assertNotIn("<script>", report)
        self.assertIn("&lt;img", report)
        self.assertIn(r"\|", report)
        self.assertIn(r"\[click\]", report)

    def test_model_schema_only_allows_supplied_evidence_and_prompt_keeps_data(self):
        schema = analysis_schema(self.evidence)
        summary = schema["properties"]["executive_summary"]["items"]
        self.assertFalse(schema["additionalProperties"])
        self.assertNotIn("uniqueItems", summary["properties"]["evidence"])
        self.assertEqual(
            summary["properties"]["evidence"]["items"]["enum"],
            ["L2", "L3", "L4", "L1"],
        )
        payload = model_prompt(self.evidence)
        self.assertIn('"id": "L3"', payload)
        self.assertIn("untrusted JSON evidence", payload)

    def test_model_input_limit_is_explicit(self):
        event = replace(self.evidence.events[0], message="x" * 60001)
        with self.assertRaisesRegex(IncidentError, "reduce the log window"):
            model_prompt(replace(self.evidence, events=(event,)))

    def test_exact_model_input_limit_is_accepted(self):
        event = replace(self.evidence.events[0], message="")
        base = replace(self.evidence, events=(event,))
        event = replace(event, message="x" * (60000 - len(model_prompt(base))))
        self.assertEqual(len(model_prompt(replace(base, events=(event,)))), 60000)
        with self.assertRaises(IncidentError):
            model_prompt(replace(base, events=(replace(event, message=event.message + "x"),)))

    def test_exact_model_output_limit_is_accepted(self):
        raw = json.dumps(valid_analysis())
        raw += " " * (40000 - len(raw))
        validate_analysis(raw, self.evidence)
        with self.assertRaises(IncidentError):
            validate_analysis(raw + " ", self.evidence)

    def test_model_mode_cannot_silently_render_as_an_offline_report(self):
        with self.assertRaisesRegex(IncidentError, "supplied together"):
            render_report(self.evidence, model="example")
        with self.assertRaisesRegex(IncidentError, "at least one"):
            render_report(replace(self.evidence, events=()))


if __name__ == "__main__":
    unittest.main()
