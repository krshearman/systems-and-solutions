import asyncio
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import replace
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from automation.pr_review.evidence import ReviewError, snapshot_from_dict
from automation.pr_review.input import GUIDELINES, read_object
from automation.pr_review.report import read_guidelines
from automation.review_team.__main__ import main
from automation.review_team.contracts import (
    ROLES, synthesis_schema, validate_specialist, validate_synthesis,
)
from automation.review_team.runtime import (
    PROFILE_NAMES, coordinator_prompt, digest, read_profiles, run_team, sdk_runner,
)
from automation.review_team.report import render_report
from automation.sdk import SdkError

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "examples/pr_review/pull_request.json"
REPLAY = ROOT / "examples/review_team/replay.json"


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = snapshot_from_dict(read_object(SNAPSHOT))
        self.guidelines = read_guidelines(GUIDELINES)
        self.data = read_object(REPLAY)
        self.specialists = {
            role: validate_specialist(
                role, json.dumps(self.data[role]), self.snapshot, self.guidelines
            ) for role in ROLES
        }

    def validate(self, data):
        return validate_synthesis(json.dumps(data), self.specialists)

    def test_coordinator_retains_every_finding_and_can_flag_a_disagreement(self):
        result = self.validate(self.data["coordinator"])
        self.assertEqual({row.finding for row in result.priorities}, {"A1", "A2", "S1"})
        self.assertEqual(result.disagreements[0].findings, ("A1", "S1"))
        self.assertEqual(next(row.priority for row in result.priorities if row.finding == "S1"), "first")

    def test_specialists_cannot_exceed_their_roles_or_invent_evidence(self):
        for role, key, value in (
            ("architecture", "category", "security"),
            ("security", "category", "impact"),
            ("security", "evidence", "F1:L99"),
            ("architecture", "guideline", "G99"),
        ):
            data = deepcopy(self.data[role])
            data["findings"][0][key] = value
            with self.subTest(role=role, key=key), self.assertRaises(ReviewError):
                validate_specialist(role, json.dumps(data), self.snapshot, self.guidelines)

    def test_coordinator_cannot_drop_duplicate_or_invent_findings(self):
        for variant in ("drop", "duplicate", "invent"):
            data = deepcopy(self.data["coordinator"])
            if variant == "drop":
                data["priorities"].pop()
            elif variant == "duplicate":
                data["priorities"][1]["finding"] = "S1"
            else:
                data["priorities"][0]["finding"] = "S99"
            with self.subTest(variant=variant), self.assertRaises(ReviewError):
                self.validate(data)

    def test_coordinator_cannot_lower_priority_below_original_severity(self):
        for index, priority in ((0, "next"), (0, "later"), (1, "later")):
            data = deepcopy(self.data["coordinator"])
            data["priorities"][index]["priority"] = priority
            with self.subTest(index=index, priority=priority), self.assertRaises(ReviewError):
                self.validate(data)

    def test_unknown_duplicate_and_invalid_source_references_fail(self):
        for references in (["AO99"], ["F1"], ["S1", "S1"], [True], []):
            data = deepcopy(self.data["coordinator"])
            data["summary"][0]["sources"] = references
            with self.subTest(references=references), self.assertRaises(ReviewError):
                self.validate(data)
        for references in (["S1"], ["A1", "A1"], ["A1", "S99"]):
            data = deepcopy(self.data["coordinator"])
            data["disagreements"][0]["findings"] = references
            with self.assertRaises(ReviewError):
                self.validate(data)

    def test_duplicate_disagreements_and_unexpected_sections_fail(self):
        data = deepcopy(self.data["coordinator"])
        data["disagreements"] *= 2
        with self.assertRaisesRegex(ReviewError, "Duplicate"):
            self.validate(data)
        data = deepcopy(self.data["coordinator"])
        data["approve"] = True
        with self.assertRaises(ReviewError):
            self.validate(data)
        with self.assertRaises(ReviewError):
            validate_synthesis('{"summary":[],"summary":[]}', self.specialists)

    def test_empty_findings_are_valid_without_claiming_consensus(self):
        specialists = {}
        for role in ROLES:
            data = deepcopy(self.data[role])
            data["findings"] = []
            specialists[role] = validate_specialist(
                role, json.dumps(data), self.snapshot, self.guidelines
            )
        data = {
            "summary": [{"statement": "Human review is still needed.", "sources": ["AO1", "SO1"]}],
            "priorities": [], "disagreements": [],
            "human_review_questions": ["What source context remains unavailable?"],
        }
        self.assertEqual(validate_synthesis(json.dumps(data), specialists).priorities, ())
        self.assertEqual(synthesis_schema(specialists)["properties"]["priorities"]["maxItems"], 0)

    def test_text_controls_and_exact_coordinator_output_limit(self):
        data = deepcopy(self.data["coordinator"])
        data["human_review_questions"] = ["\x9bhidden"]
        with self.assertRaises(ReviewError):
            self.validate(data)
        data["human_review_questions"] = ["x" * 600]
        self.validate(data)
        data["human_review_questions"] = ["x" * 601]
        with self.assertRaises(ReviewError):
            self.validate(data)
        raw = json.dumps(self.data["coordinator"])
        raw += " " * (40000 - len(raw))
        validate_synthesis(raw, self.specialists)
        with self.assertRaisesRegex(ReviewError, "40000"):
            validate_synthesis(raw + " ", self.specialists)

    def test_handoff_contains_only_validated_results_and_cited_source_lines(self):
        data = json.loads(coordinator_prompt(self.snapshot, self.guidelines, self.specialists))
        self.assertNotIn("untrusted_files", data)
        self.assertEqual(set(data["cited_source_lines"]), {"F1:L2", "F2:L1"})
        self.assertEqual(data["untrusted_specialist_results"]["security"]["findings"][0]["id"], "S1")
        self.assertEqual(data["snapshot"]["head_sha"], self.snapshot.head_sha)
        empty = coordinator_prompt(
            self.snapshot, replace(self.guidelines, content=""), self.specialists
        )
        maximum = replace(self.guidelines, content="x" * (100000 - len(empty)))
        self.assertEqual(
            len(coordinator_prompt(self.snapshot, maximum, self.specialists)), 100000
        )
        with self.assertRaisesRegex(ReviewError, "100000"):
            coordinator_prompt(
                self.snapshot, replace(maximum, content=maximum.content + "x"), self.specialists
            )

    def test_profiles_are_explicit_instruction_bodies_not_native_discovery(self):
        profiles = read_profiles()
        self.assertEqual(set(profiles), {"architecture", "security", "coordinator"})
        for profile in profiles.values():
            self.assertFalse(profile.instructions.startswith("---"))
            self.assertEqual(len(profile.sha256), 64)
            self.assertIn("tools: []", (ROOT / profile.path).read_text())
        for role in ROLES:
            self.assertIn("(evidence, category) pair", profiles[role].instructions)
            self.assertIn("wording-only", profiles[role].instructions)


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.snapshot = snapshot_from_dict(read_object(SNAPSHOT))
        self.guidelines = read_guidelines(GUIDELINES)
        self.profiles = read_profiles()
        self.data = read_object(REPLAY)
        self.names = {name: role for role, name in PROFILE_NAMES.items()}

    async def test_one_line_documentation_change_can_finish_with_no_findings(self):
        data = read_object(SNAPSHOT)
        data["files"] = data["files"][:1]
        data["files"][0].update(
            filename="README.md", status="modified", additions=1, deletions=1,
            patch="@@ -3 +3 @@\n-A synthetic portfolio.\n+A synthetic engineering portfolio.",
        )
        snapshot = snapshot_from_dict(data)
        budgets = {}

        async def runner(profile, _prompt, schema):
            role = self.names[profile.name]
            await asyncio.sleep(0)
            if role in ROLES:
                budgets[role] = schema["properties"]["findings"]["maxItems"]
                return json.dumps({
                    "overview": [{"statement": "Rewords a portfolio description.", "files": ["F1"]}],
                    "findings": [],
                })
            self.assertEqual(schema["properties"]["priorities"]["maxItems"], 0)
            return json.dumps({
                "summary": [{"statement": "Both specialists observed a wording change.",
                             "sources": ["AO1", "SO1"]}],
                "priorities": [], "disagreements": [],
                "human_review_questions": ["Does the wording reflect the intended description?"],
            })

        result = await run_team(snapshot, self.guidelines, self.profiles, runner)
        self.assertEqual(budgets, {"architecture": 2, "security": 1})
        self.assertEqual(result.coordinator.priorities, ())
        report = render_report(snapshot, self.guidelines, result, self.profiles, "example-model")
        self.assertIn("No source findings supplied", report)
        self.assertIn("not an assurance of safety", report)
        self.assertEqual(result.trace[-1].state, "validated")

    async def test_duplicate_specialist_findings_are_not_silently_dropped(self):
        calls = []
        self.data["architecture"]["findings"].append(
            deepcopy(self.data["architecture"]["findings"][0])
        )

        async def runner(profile, _prompt, _schema):
            role = self.names[profile.name]
            calls.append(role)
            await asyncio.sleep(0)
            return json.dumps(self.data[role])

        with self.assertRaisesRegex(ReviewError, r"Duplicate finding.*F1:L2, architecture"):
            await run_team(self.snapshot, self.guidelines, self.profiles, runner)
        self.assertNotIn("coordinator", calls)

    async def test_real_fanout_barrier_precedes_validated_fanin(self):
        entered, completed = set(), set()
        both_entered = asyncio.Event()
        requests = {}

        async def runner(profile, prompt, schema):
            role = self.names[profile.name]
            requests[role] = (prompt, schema)
            if role in ROLES:
                entered.add(role)
                if entered == set(ROLES):
                    both_entered.set()
                await asyncio.wait_for(both_entered.wait(), 2)
                self.assertNotIn("untrusted_specialist_results", json.loads(prompt))
                completed.add(role)
            else:
                self.assertEqual(completed, set(ROLES))
                self.assertEqual(set(json.loads(prompt)["untrusted_specialist_results"]), set(ROLES))
            return json.dumps(self.data[role])

        result = await run_team(self.snapshot, self.guidelines, self.profiles, runner)
        states = [(event.agent, event.state) for event in result.trace]
        coordinator_start = states.index(("coordinator", "started"))
        for role in ROLES:
            self.assertLess(states.index((role, "validated")), coordinator_start)
        self.assertEqual(len({event.request_id for event in result.trace}), 3)
        self.assertEqual([event.sequence for event in result.trace], list(range(1, 10)))
        self.assertEqual(result.trace[-1].input_sha256, digest(requests["coordinator"][0]))
        self.assertEqual(
            result.trace[-1].output_sha256,
            digest(json.dumps(result.coordinator.to_dict(), sort_keys=True)),
        )
        self.assertEqual(
            requests["security"][1]["properties"]["findings"]["items"]["properties"]["category"]["enum"],
            ["security"],
        )

    async def test_failed_specialist_cancels_sibling_and_never_starts_coordinator(self):
        security_started, cancelled = asyncio.Event(), asyncio.Event()
        called = []

        async def runner(profile, _prompt, _schema):
            role = self.names[profile.name]
            called.append(role)
            if role == "architecture":
                await security_started.wait()
                raise SdkError("synthetic failure")
            if role == "security":
                security_started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
            self.fail("Coordinator must not start")

        with self.assertRaisesRegex(ReviewError, "coordinator was not invoked"):
            await asyncio.wait_for(
                run_team(self.snapshot, self.guidelines, self.profiles, runner), 2
            )
        self.assertTrue(cancelled.is_set())
        self.assertNotIn("coordinator", called)

    async def test_invalid_specialist_output_also_blocks_synthesis(self):
        calls = []

        async def runner(profile, _prompt, _schema):
            role = self.names[profile.name]
            calls.append(role)
            await asyncio.sleep(0)
            return "not JSON" if role == "security" else json.dumps(self.data[role])

        with self.assertRaisesRegex(ReviewError, "coordinator was not invoked"):
            await run_team(self.snapshot, self.guidelines, self.profiles, runner)
        self.assertNotIn("coordinator", calls)

    async def test_coordinator_cannot_replace_a_failed_stage_with_success(self):
        async def runner(profile, _prompt, _schema):
            role = self.names[profile.name]
            await asyncio.sleep(0)
            return "{}" if role == "coordinator" else json.dumps(self.data[role])

        with self.assertRaisesRegex(ReviewError, "Coordinator stage failed"):
            await run_team(self.snapshot, self.guidelines, self.profiles, runner)

    async def test_sdk_runner_passes_profile_context_and_credentials_to_isolated_transport(self):
        request = AsyncMock(return_value="{}")
        with patch("automation.review_team.runtime.request_analysis", request):
            runner = sdk_runner("example-model", 42, "synthetic-test-token")
            await runner(self.profiles["security"], "data", {"type": "object"})
        request.assert_awaited_once_with(
            "data", self.profiles["security"].instructions,
            {"type": "object"}, "example-model", 42, "synthetic-test-token",
        )


class CliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / "team.json"

    def cli(self, *mode):
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            result = main([
                "--fixture", str(SNAPSHOT), "--output", str(self.output), *mode
            ])
        return result, output.getvalue(), error.getvalue()

    def test_replay_is_explicit_and_never_calls_sdk_or_github(self):
        with patch("automation.review_team.__main__.sdk_runner") as sdk, patch("automation.review_team.__main__.github_client") as github:
            code, _, _ = self.cli("--replay", str(REPLAY))
        self.assertEqual(code, 0)
        sdk.assert_not_called()
        github.assert_not_called()
        bundle = json.loads(self.output.read_text())
        self.assertEqual(bundle["mode"], "replay")
        self.assertIsNone(bundle["model"])
        self.assertEqual(len(bundle["trace"]), 9)
        report = self.output.with_suffix(".md").read_text()
        self.assertIn("no model sessions ran", report)
        self.assertIn("A1, S1", report)
        self.assertIn("55/100", report)
        self.assertIn("Human review required", report)

    def test_live_mode_is_not_a_replay_fallback_and_requires_upload_approval(self):
        with self.assertRaises(SystemExit):
            self.cli("--model", "example")

        async def failure(*_args):
            raise SdkError("synthetic failure")

        with patch("automation.review_team.__main__.sdk_runner", return_value=failure):
            code, _, error = self.cli("--model", "example", "--allow-model-upload")
        self.assertEqual(code, 1)
        self.assertIn("coordinator was not invoked", error)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_suffix(".md").exists())

    def test_coordinator_failure_creates_no_partial_success_report(self):
        data = read_object(REPLAY)
        data["coordinator"] = {}
        replay = Path(self.directory.name) / "invalid.json"
        replay.write_text(json.dumps(data))
        code, _, error = self.cli("--replay", str(replay))
        self.assertEqual(code, 1)
        self.assertIn("Coordinator stage failed", error)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_suffix(".md").exists())

    def test_existing_outputs_and_dangling_symlinks_are_not_overwritten(self):
        for suffix, symlink in ((".json", False), (".md", False), (".md", True)):
            path = self.output.with_suffix(suffix)
            if symlink:
                path.symlink_to(Path(self.directory.name) / "missing")
            else:
                path.write_text("preserve this output")
            with self.subTest(suffix=suffix, symlink=symlink):
                with patch("automation.review_team.__main__.sdk_runner") as sdk:
                    self.assertEqual(self.cli("--model", "example", "--allow-model-upload")[0], 1)
                sdk.assert_not_called()
                if not symlink:
                    self.assertEqual(path.read_text(), "preserve this output")
            path.unlink()

    def test_sdk_coordinator_failure_creates_no_success_artifact(self):
        data = read_object(REPLAY)
        names = {name: role for role, name in PROFILE_NAMES.items()}

        async def runner(profile, _prompt, _schema):
            role = names[profile.name]
            if role == "coordinator":
                raise SdkError("synthetic timeout")
            await asyncio.sleep(0)
            return json.dumps(data[role])

        with patch("automation.review_team.__main__.sdk_runner", return_value=runner):
            code, _, error = self.cli("--model", "example", "--allow-model-upload")
        self.assertEqual(code, 1)
        self.assertIn("Coordinator stage failed", error)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_suffix(".md").exists())

    def test_replay_schema_and_cli_modes_are_not_silently_coerced(self):
        with self.assertRaises(SystemExit):
            self.cli("--replay", str(REPLAY), "--allow-model-upload")
        data = read_object(REPLAY)
        data["extra_agent"] = {}
        replay = Path(self.directory.name) / "invalid.json"
        replay.write_text(json.dumps(data))
        self.assertEqual(self.cli("--replay", str(replay))[0], 1)

    def test_model_generated_markup_and_mentions_are_escaped(self):
        data = read_object(REPLAY)
        data["coordinator"]["summary"][0]["statement"] = "@someone <script> [click](https://example.org)"
        replay = Path(self.directory.name) / "markup.json"
        replay.write_text(json.dumps(data))
        self.assertEqual(self.cli("--replay", str(replay))[0], 0)
        report = self.output.with_suffix(".md").read_text()
        self.assertNotIn("@someone", report)
        self.assertNotIn("<script>", report)
        self.assertNotIn("[click](", report)

    def test_team_workflow_is_read_only_and_pins_trusted_profiles(self):
        content = (ROOT / ".github/workflows/pr-review-team.yml").read_text()
        self.assertIn("workflow_dispatch:", content)
        self.assertNotIn("pull_request:", content)
        self.assertNotIn("pull_request_target:", content)
        self.assertNotIn("pull-requests: write", content)
        self.assertNotIn("--confirm-post", content)
        self.assertIn("ref: ${{ github.sha }}", content)
        self.assertIn("environment: copilot-pr-analysis", content)
        self.assertIn("python -m copilot download-runtime", content)
        self.assertIn('--pr "$PR_NUMBER"', content)


if __name__ == "__main__":
    unittest.main()
