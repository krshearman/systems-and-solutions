from copy import deepcopy
from dataclasses import replace
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
from contextlib import redirect_stderr, redirect_stdout
from urllib.error import HTTPError, URLError

from automation.pr_review.__main__ import GUIDELINES, main
from automation.pr_review.evidence import (
    MAX_PATCH, ReviewError, added_lines, risk_score, snapshot_from_dict,
)
from automation.pr_review.github import GitHub, NoRedirect
from automation.pr_review.report import (
    analysis_schema, model_prompt, read_guidelines, render_report, validate_analysis,
)
from automation.sdk import SdkError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/pr_review/pull_request.json"


def valid_analysis():
    return {
        "overview": [{"statement": "Adds a synthetic user query and changes a dependency.", "files": ["F1", "F2"]}],
        "findings": [{
            "category": "security", "severity": "high", "confidence": 9,
            "evidence": "F1:L2", "guideline": "G3",
            "statement": "If name is untrusted, interpolating it into SQL can change query semantics.",
            "recommendation": "Use bound parameters for the name value.",
        }],
    }


class ReviewBase(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_text())
        self.snapshot = snapshot_from_dict(self.data)
        self.guidelines = read_guidelines(GUIDELINES)
        self.analysis = validate_analysis(json.dumps(valid_analysis()), self.snapshot, self.guidelines)


class EvidenceTests(ReviewBase):
    def test_snapshot_round_trip_and_exact_changed_line_ids(self):
        self.assertEqual(snapshot_from_dict(self.snapshot.to_dict()), self.snapshot)
        self.assertEqual(set(self.snapshot.line_evidence), {"F1:L1", "F1:L2", "F1:L3", "F2:L1"})
        self.assertEqual(self.snapshot.line_evidence["F1:L2"][:2], ("examples/demo/auth.py", 2))
        data = deepcopy(self.data)
        data["repository"] = data["repository"].upper()
        self.assertEqual(snapshot_from_dict(data), self.snapshot)

    def test_context_deletions_and_multiple_hunks_have_correct_new_line_numbers(self):
        value = "@@ -10,3 +10,3 @@\n context\n-old\n+new\n end\n@@ -20 +20,2 @@\n tail\n+extra"
        self.assertEqual(added_lines(value, 2, 1), {11: "new", 21: "extra"})

    def test_unicode_line_separator_does_not_invent_a_patch_line(self):
        self.assertEqual(added_lines("@@ -0,0 +1 @@\n+hello\u2028world", 1, 0), {1: "hello\u2028world"})

    def test_incomplete_malformed_and_overlapping_patches_fail(self):
        patches = [
            "@@ -0,0 +1,2 @@\n+only one",
            "@@ -0,0 +1 @@\nmissing prefix",
            "@@ -0,0 +1 @@\n+x\n@@ -0,0 +1 @@\n+y",
            "not a hunk", "@@ -0,0 +0 @@\n+x",
        ]
        for value in patches:
            with self.subTest(value=value), self.assertRaises(ReviewError):
                added_lines(value, 1, 0)
        with self.assertRaises(ReviewError):
            added_lines("@@ -0,0 +1 @@\n+x", 2, 0)

    def test_binary_missing_fields_and_unsafe_paths_fail(self):
        for key, value in (
            ("patch", None), ("status", "copied"), ("filename", "../escape.py"),
            ("filename", "/absolute.py"), ("filename", "bad\nname.py"),
            ("additions", True), ("previous_filename", "unexpected.py"),
        ):
            data = deepcopy(self.data)
            data["files"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ReviewError):
                snapshot_from_dict(data)
        data = deepcopy(self.data)
        data["files"].append(data["files"][0])
        with self.assertRaisesRegex(ReviewError, "Duplicate"):
            snapshot_from_dict(data)

    def test_snapshot_metadata_and_file_count_are_strict(self):
        for key, value in (
            ("repository", "not a repo"), ("number", True), ("base_sha", "main"),
            ("head_sha", None), ("files", []), ("files", self.data["files"] * 13),
        ):
            data = deepcopy(self.data)
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ReviewError):
                snapshot_from_dict(data)
        data = deepcopy(self.data)
        data["unexpected"] = True
        with self.assertRaises(ReviewError):
            snapshot_from_dict(data)

    def test_exact_patch_and_added_line_limits(self):
        data = deepcopy(self.data)
        file = data["files"][0]
        data["files"] = [file]
        file["additions"] = 1
        prefix = "@@ -0,0 +1 @@\n+"
        file["patch"] = prefix + "x" * (MAX_PATCH - len(prefix))
        snapshot_from_dict(data)
        file["patch"] += "x"
        with self.assertRaisesRegex(ReviewError, "50000"):
            snapshot_from_dict(data)
        for count in (1000, 1001):
            file["additions"] = count
            file["patch"] = f"@@ -0,0 +1,{count} @@\n" + "\n".join("+x" for _ in range(count))
            if count == 1000:
                snapshot_from_dict(data)
            else:
                with self.assertRaisesRegex(ReviewError, "1000 added"):
                    snapshot_from_dict(data)

    def test_risk_is_deterministic_and_explained_by_metadata_not_model(self):
        self.assertEqual(risk_score(self.snapshot), 55)
        data = deepcopy(self.data)
        data["files"][0]["filename"] = "tests/test_auth.py"
        self.assertEqual(risk_score(snapshot_from_dict(data)), 45)

    def test_renames_preserve_the_original_path_risk_signal(self):
        data = deepcopy(self.data)
        file = data["files"][0]
        file.update(
            filename="src/query.py", previous_filename=".github/workflows/auth.py",
            status="renamed",
        )
        self.assertEqual(risk_score(snapshot_from_dict(data)), 80)

    def test_exact_file_count_limit(self):
        data = deepcopy(self.data)
        file = data["files"][0]
        data["files"] = [{**file, "filename": f"src/file{index}.py"} for index in range(25)]
        snapshot_from_dict(data)
        data["files"].append({**file, "filename": "src/extra.py"})
        with self.assertRaisesRegex(ReviewError, "25 changed files"):
            snapshot_from_dict(data)

    def test_breadth_threshold_counts_files_not_rename_paths(self):
        data = deepcopy(self.data)
        file = data["files"][0]
        for count, expected in ((10, 10), (11, 20)):
            data["files"] = [
                {**file, "filename": f"src/file{index}.py"} for index in range(count)
            ]
            self.assertEqual(risk_score(snapshot_from_dict(data)), expected)

    def test_size_thresholds_and_score_cap(self):
        for count, expected in ((100, 10), (101, 20), (400, 20), (401, 30)):
            data = deepcopy(self.data)
            file = data["files"][0]
            data["files"] = [file]
            file["filename"] = "src/main.py"
            file["additions"] = count
            file["patch"] = f"@@ -0,0 +1,{count} @@\n" + "\n".join("+x" for _ in range(count))
            self.assertEqual(risk_score(snapshot_from_dict(data)), expected)
        data["files"].extend(
            {**file, "filename": name}
            for name in (".github/workflows/demo.yml", "infra/security.tf", "package.json")
        )
        for file in data["files"]:
            file.update(additions=200, patch="@@ -0,0 +1,200 @@\n" + "\n".join("+x" for _ in range(200)))
        self.assertEqual(risk_score(snapshot_from_dict(data)), 100)


class ModelReportTests(ReviewBase):
    def test_schema_prompt_and_report_keep_evidence_and_guidelines_separate(self):
        schema = analysis_schema(self.snapshot, self.guidelines)
        self.assertNotIn("uniqueItems", json.dumps(schema))
        prompt = json.loads(model_prompt(self.snapshot, self.guidelines))
        self.assertIn("trusted_guidelines", prompt)
        self.assertEqual(prompt["untrusted_files"][0]["id"], "F1")
        rendered = render_report(self.snapshot, self.guidelines, self.analysis, "example")
        self.assertIn("55/100", rendered)
        self.assertIn(self.snapshot.head_sha, rendered)
        self.assertIn("F1:L2", rendered)
        self.assertIn("Guideline: G3", rendered)
        self.assertIn("Not an approval", rendered)

    def test_unknown_or_context_line_citations_and_invalid_findings_fail(self):
        for key, value in (
            ("evidence", "F1:L99"), ("evidence", "F2:L2"), ("guideline", "G99"),
            ("confidence", True), ("confidence", 11), ("confidence", 0),
            ("category", "approval"), ("severity", "safe"),
            ("statement", "\x9bhidden"), ("recommendation", ""),
        ):
            data = valid_analysis()
            data["findings"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ReviewError):
                validate_analysis(json.dumps(data), self.snapshot, self.guidelines)

    def test_duplicate_unknown_and_malformed_json_sections_fail(self):
        data = valid_analysis()
        data["findings"] *= 2
        with self.assertRaisesRegex(ReviewError, "Duplicate finding"):
            validate_analysis(json.dumps(data), self.snapshot, self.guidelines)
        for raw in ('{"overview":[],"overview":[],"findings":[]}', "not JSON", "{}",
                    json.dumps({**valid_analysis(), "risk": 0}), " " * 40001):
            with self.subTest(raw=raw[:30]), self.assertRaises(ReviewError):
                validate_analysis(raw, self.snapshot, self.guidelines)
        data = valid_analysis()
        data["overview"][0]["files"] = ["F1", "F1"]
        with self.assertRaises(ReviewError):
            validate_analysis(json.dumps(data), self.snapshot, self.guidelines)

    def test_model_mentions_and_markup_cannot_become_active_content(self):
        data = valid_analysis()
        data["findings"][0]["statement"] = "@someone <script> [click](https://example.org)"
        analysis = validate_analysis(json.dumps(data), self.snapshot, self.guidelines)
        rendered = render_report(self.snapshot, self.guidelines, analysis, "example")
        self.assertNotIn("@someone", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("[click](", rendered)

    def test_deletion_only_patches_cannot_generate_inline_findings(self):
        data = deepcopy(self.data)
        file = data["files"][0]
        data["files"] = [file]
        file.update(status="removed", additions=0, deletions=1, patch="@@ -1 +0,0 @@\n-old")
        snapshot = snapshot_from_dict(data)
        self.assertEqual(snapshot.line_evidence, {})
        self.assertEqual(analysis_schema(snapshot, self.guidelines)["properties"]["findings"]["maxItems"], 0)
        with self.assertRaises(ReviewError):
            validate_analysis(json.dumps(valid_analysis()), snapshot, self.guidelines)

    def test_empty_findings_are_honest_and_modes_cannot_be_mixed(self):
        data = valid_analysis()
        data["findings"] = []
        analysis = validate_analysis(json.dumps(data), self.snapshot, self.guidelines)
        self.assertIn("does not establish absence", render_report(self.snapshot, self.guidelines, analysis, "example"))
        with self.assertRaises(ReviewError):
            render_report(self.snapshot, self.guidelines, None, "example")

    def test_exact_model_output_and_serialized_input_limits(self):
        raw = json.dumps(valid_analysis())
        raw += " " * (40000 - len(raw))
        validate_analysis(raw, self.snapshot, self.guidelines)
        with self.assertRaises(ReviewError):
            validate_analysis(raw + " ", self.snapshot, self.guidelines)
        data = deepcopy(self.data)
        data["files"] = [data["files"][0]]
        file = data["files"][0]
        file.update(additions=1, patch="@@ -0,0 +1 @@\n+")
        base = len(model_prompt(snapshot_from_dict(data), self.guidelines))
        remaining = 100000 - base
        file["patch"] += "\u00e9" * (remaining // 6) + "x" * (remaining % 6)
        self.assertEqual(len(model_prompt(snapshot_from_dict(data), self.guidelines)), 100000)
        file["patch"] += "x"
        with self.assertRaisesRegex(ReviewError, "100000"):
            model_prompt(snapshot_from_dict(data), self.guidelines)


class GitHubTests(ReviewBase):
    def client(self):
        return GitHub(self.snapshot.repository, self.snapshot.number, "synthetic-test-token")

    def metadata(self, **changes):
        return {
            "state": "open", "changed_files": len(self.snapshot.files),
            "base": {"sha": self.snapshot.base_sha, "repo": {"full_name": self.snapshot.repository}},
            "head": {"sha": self.snapshot.head_sha}, **changes,
        }

    def test_compare_uses_immutable_shas_and_rechecks_pr_state(self):
        client = self.client()
        responses = [self.metadata(), {"files": self.data["files"]}, self.metadata()]
        with patch.object(client, "request", side_effect=responses) as api:
            self.assertEqual(client.snapshot(), self.snapshot)
        self.assertIn(f"{self.snapshot.base_sha}...{self.snapshot.head_sha}", api.call_args_list[1].args[1])
        self.assertTrue(all(call.args[0] == "GET" for call in api.call_args_list))

    def test_closed_incomplete_and_racing_prs_fail_explicitly(self):
        responses = [
            [self.metadata(state="closed")],
            [self.metadata(), {"files": []}],
            [self.metadata(), {"files": self.data["files"]},
             self.metadata(head={"sha": "3" * 40})],
        ]
        for response in responses:
            client = self.client()
            with self.subTest(response=response), patch.object(client, "request", side_effect=response):
                with self.assertRaises(ReviewError):
                    client.snapshot()

    def test_publish_is_comment_only_and_uses_verified_added_lines(self):
        client = self.client()
        with (
            patch.object(client, "snapshot", return_value=self.snapshot),
            patch.object(client, "metadata", return_value=(self.snapshot.base_sha, self.snapshot.head_sha, 2)),
            patch.object(client, "request", return_value={"id": 123}) as api,
        ):
            self.assertEqual(client.publish(self.snapshot, self.guidelines, self.analysis, "example"), 123)
        method, _, payload = api.call_args.args
        self.assertEqual(method, "POST")
        self.assertEqual(payload["event"], "COMMENT")
        self.assertEqual(payload["commit_id"], self.snapshot.head_sha)
        self.assertEqual(payload["comments"][0]["path"], "examples/demo/auth.py")
        self.assertEqual(payload["comments"][0]["line"], 2)
        self.assertEqual(payload["comments"][0]["side"], "RIGHT")

    def test_low_confidence_findings_remain_in_body_but_not_inline(self):
        data = valid_analysis()
        data["findings"][0]["confidence"] = 7
        analysis = validate_analysis(json.dumps(data), self.snapshot, self.guidelines)
        client = self.client()
        with (
            patch.object(client, "snapshot", return_value=self.snapshot),
            patch.object(client, "metadata", return_value=(self.snapshot.base_sha, self.snapshot.head_sha, 2)),
            patch.object(client, "request", return_value={"id": 123}) as api,
        ):
            client.publish(self.snapshot, self.guidelines, analysis, "example")
        self.assertNotIn("comments", api.call_args.args[2])
        self.assertIn("7/10", api.call_args.args[2]["body"])

    def test_stale_wrong_target_and_modified_evidence_never_post(self):
        client = self.client()
        variants = [
            replace(self.snapshot, head_sha="3" * 40),
            replace(self.snapshot, files=(replace(self.snapshot.files[0], patch=self.snapshot.files[0].patch.replace("lookup_user", "other_name")), *self.snapshot.files[1:])),
        ]
        for current in variants:
            with self.subTest(current=current), patch.object(client, "snapshot", return_value=current), patch.object(client, "request") as api:
                with self.assertRaises(ReviewError):
                    client.publish(self.snapshot, self.guidelines, self.analysis, "example")
                api.assert_not_called()
        with self.assertRaisesRegex(ReviewError, "different PR"):
            client.publish(replace(self.snapshot, number=1), self.guidelines, self.analysis, "example")

    def test_final_prepost_head_check_and_failed_write_are_not_retried(self):
        client = self.client()
        with (
            patch.object(client, "snapshot", return_value=self.snapshot),
            patch.object(client, "metadata", return_value=(self.snapshot.base_sha, "3" * 40, 2)),
            patch.object(client, "request") as api,
        ):
            with self.assertRaises(ReviewError):
                client.publish(self.snapshot, self.guidelines, self.analysis, "example")
            api.assert_not_called()
        with patch("automation.pr_review.github.build_opener") as factory:
            factory.return_value.open.side_effect = URLError("synthetic-test-token")
            with self.assertRaises(ReviewError) as failure:
                client.request("POST", "/test", {})
            self.assertNotIn("synthetic-test-token", str(failure.exception))
            self.assertEqual(factory.return_value.open.call_count, 1)

    def test_http_errors_and_redirects_do_not_leak_credentials(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.org"))
        with patch("automation.pr_review.github.build_opener") as factory:
            factory.return_value.open.side_effect = HTTPError("https://api.github.com", 403, "secret", {}, None)
            with self.assertRaisesRegex(ReviewError, "HTTP 403"):
                self.client().request("GET", "/test")
        with self.assertRaises(ReviewError):
            GitHub("owner/repo", 1, "")

    def test_api_reads_are_bounded_and_use_only_the_fixed_github_host(self):
        with patch("automation.pr_review.github.build_opener") as factory:
            response = Mock()
            response.read.return_value = b'{"id":1}'
            factory.return_value.open.return_value.__enter__.return_value = response
            self.assertEqual(self.client().request("GET", "/test"), {"id": 1})
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.github.com/test")
            response.read.assert_called_once_with(1000001)
            response.read.return_value = b"x" * 1000001
            with self.assertRaisesRegex(ReviewError, "1000000"):
                self.client().request("GET", "/test")

    def test_malformed_repository_metadata_is_an_explicit_error(self):
        data = self.metadata(base={"sha": self.snapshot.base_sha, "repo": {"full_name": 42}})
        client = self.client()
        with patch.object(client, "request", return_value=data):
            with self.assertRaises(ReviewError):
                client.metadata()


class CliTests(ReviewBase):
    def setUp(self):
        super().setUp()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / "review.json"

    def run_cli(self, *args):
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = main(list(args))
        return code, output.getvalue(), error.getvalue()

    def analyze(self, *mode):
        return self.run_cli("analyze", "--fixture", str(FIXTURE), "--output", str(self.output), *mode)

    def test_offline_demo_has_no_sdk_or_github_side_effects(self):
        with patch("automation.pr_review.__main__.request_analysis") as sdk, patch("automation.pr_review.__main__.github_client") as github:
            code, _, _ = self.analyze("--offline")
        self.assertEqual(code, 0)
        self.assertIn("55/100", self.output.with_suffix(".md").read_text())
        self.assertIsNone(json.loads(self.output.read_text())["analysis"])
        sdk.assert_not_called()
        github.assert_not_called()

    def test_model_path_requires_consent_and_never_publishes(self):
        with self.assertRaises(SystemExit):
            self.analyze("--model", "example")
        sdk = AsyncMock(return_value=json.dumps(valid_analysis()))
        with patch("automation.pr_review.__main__.request_analysis", sdk), patch("automation.pr_review.__main__.github_client") as github:
            self.assertEqual(self.analyze("--model", "example", "--allow-model-upload")[0], 0)
        self.assertEqual(sdk.await_args.kwargs["token"], os.environ.get("COPILOT_GITHUB_TOKEN") or None)
        self.assertIsNotNone(json.loads(self.output.read_text())["analysis"])
        github.assert_not_called()

    def test_invalid_sdk_output_and_transport_errors_create_no_reports(self):
        for sdk in (AsyncMock(return_value="invalid"), AsyncMock(side_effect=SdkError("failure"))):
            with patch("automation.pr_review.__main__.request_analysis", sdk):
                self.assertEqual(self.analyze("--model", "example", "--allow-model-upload")[0], 1)
            self.assertFalse(self.output.exists())
            self.assertFalse(self.output.with_suffix(".md").exists())

    def test_output_collisions_are_rejected_before_model_calls(self):
        self.output.with_suffix(".md").symlink_to(Path(self.directory.name) / "missing")
        with patch("automation.pr_review.__main__.request_analysis") as sdk:
            self.assertEqual(self.analyze("--model", "example", "--allow-model-upload")[0], 1)
        sdk.assert_not_called()

    def test_publish_requires_confirmation_and_rejects_offline_or_changed_policy(self):
        self.analyze("--offline")
        args = ("publish", "--input", str(self.output), "--repo", self.snapshot.repository, "--pr", str(self.snapshot.number))
        with self.assertRaises(SystemExit):
            self.run_cli(*args)
        with patch("automation.pr_review.__main__.github_client") as github:
            self.assertEqual(self.run_cli(*args, "--confirm-post")[0], 1)
            bundle = json.loads(self.output.read_text())
            bundle.update(model="example", analysis=valid_analysis(), guidelines_sha256="wrong")
            self.output.write_text(json.dumps(bundle))
            self.assertEqual(self.run_cli(*args, "--confirm-post")[0], 1)
        github.assert_not_called()

    def test_publish_revalidates_bundle_and_calls_only_explicit_target(self):
        self.analyze("--offline")
        bundle = json.loads(self.output.read_text())
        bundle.update(model="example", analysis=valid_analysis())
        self.output.write_text(json.dumps(bundle))
        with patch("automation.pr_review.__main__.github_client") as factory:
            factory.return_value.publish.return_value = 123
            code, _, _ = self.run_cli(
                "publish", "--input", str(self.output), "--repo", self.snapshot.repository,
                "--pr", str(self.snapshot.number), "--confirm-post",
            )
        self.assertEqual(code, 0)
        factory.assert_called_once_with(self.snapshot.repository, self.snapshot.number)
        factory.return_value.publish.assert_called_once()

    def test_workflow_separates_credentials_and_never_checks_out_pr_head(self):
        content = (ROOT / ".github/workflows/pr-impact.yml").read_text()
        self.assertIn("workflow_dispatch:", content)
        self.assertNotIn("pull_request_target:", content)
        self.assertNotIn("pull_request:", content)
        self.assertIn("permissions: {}", content)
        analysis, publication = content.split("\n  publish:\n")
        self.assertIn("pull-requests: read", analysis)
        self.assertIn("pull-requests: write", publication)
        self.assertNotIn("COPILOT_GITHUB_TOKEN", publication)
        self.assertIn("if: ${{ inputs.publish }}", publication)
        self.assertIn("needs: analyze", publication)
        self.assertEqual(content.count("ref: ${{ github.sha }}"), 2)
        self.assertNotIn("pull_request.head", content)
        self.assertIn('--pr "$PR_NUMBER"', content)


if __name__ == "__main__":
    unittest.main()
