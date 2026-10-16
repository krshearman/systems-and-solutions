# PR impact and security summarizer

This Python application explains change-risk factors and uses the Copilot SDK
to draft evidence-linked impact, architecture, and security observations.
It is not a vulnerability scanner, test runner, autonomous reviewer, or merge
gate. Surrounding source files are not fetched or executed.

## 1. Try the offline fixture

Run from the repository root in a normal shell, including the canvas terminal:

```sh
mkdir -p reports
python3 -B -m automation.pr_review analyze \
  --fixture examples/pr_review/pull_request.json \
  --offline --output reports/pr-review.json
```

Python 3.11 or later is sufficient. This writes an advisory Markdown report
and a JSON evidence bundle, without SDK access, authentication, or GitHub calls.
Existing outputs, including dangling symlinks, are refused before analysis.
Choose new output paths for subsequent runs.

The fixture contains a deliberately unsafe SQL-interpolation snippet and a
fictional dependency upgrade. Its PR number 999999 and commit SHAs are not live
review targets. No fixture source is imported or executed. The expected score
is **55/100**: dependency manifest 20, auth-named path 25, and code changed
without a test-named file 10. No model is needed to calculate that score.

## 2. Generate model observations locally

Use the existing pinned SDK environment from the incident walkthrough, or set
it up with:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-copilot.txt
```

Then send only the bundled synthetic diff and public engineering guidelines:

```sh
.venv/bin/python -B -m automation.pr_review analyze \
  --fixture examples/pr_review/pull_request.json \
  --model gpt-5-mini --allow-model-upload \
  --output reports/pr-review-copilot.json
```

Choose a model available to the authenticated account. Local SDK execution can
use the logged-in user. An explicit `COPILOT_GITHUB_TOKEN`, when supplied,
disables logged-in-user fallback for that request. The SDK is pinned to 1.0.22;
transitive dependencies are not fully locked.

The upload flag is approval to transmit the diff and guidelines, not automatic
redaction. Do not send credentials, private code, personal data, or confidential
policies without proper authorization. Model availability, entitlement,
organization policy, and usage charges still apply.

## 3. Analyze an actual open PR

REST access requires `GH_TOKEN` or `GITHUB_TOKEN` with access to the base
repository and pull request. For local use with an existing authenticated
GitHub CLI, this sets the credential without printing it or putting a literal
token in shell history:

```sh
export GH_TOKEN="$(gh auth token)"
```

Do not enable shell tracing when handling credentials. The REST credential and
Copilot credential can be different; consult the
[SDK authentication guidance](https://github.com/github/copilot-sdk/blob/main/docs/auth/authenticate.md)
for eligible OAuth or fine-grained user tokens. Do not assume an ordinary
workflow token has Copilot entitlement. Server-to-server organization
authentication is documented upstream but is not configured by this showcase.

Set `PR_NUMBER` to a real open PR number before running:

```sh
PR_NUMBER=123
.venv/bin/python -B -m automation.pr_review analyze \
  --repo krshearman/systems-and-solutions --pr "$PR_NUMBER" \
  --model gpt-5-mini --allow-model-upload \
  --output reports/live-pr-review.json
```

Replace the illustrative `123`; no such PR is assumed to exist. Use `--offline`
instead of the two model flags to fetch and score a live diff without sending
it to Copilot. This CLI currently supports GitHub.com, not GitHub Enterprise
Server or other providers.

The application reads PR metadata, compares immutable base/head SHAs through
GitHub's REST API, and rechecks metadata. It rejects missing files, missing
patches, incomplete hunk counts, unsupported statuses, or moving references.
There is no fallback to a partial review. Fork PRs can be manually selected
when the base repository API exposes their complete comparison; no fork
checkout or code execution occurs.

## 4. Understand the score and evidence

The project-defined rubric is additive, capped at 100, and independent of model
findings. It is not calibrated against vulnerabilities or production incidents.
Renames consider both old and new path names.

| Factor | Points |
| --- | --- |
| A `.github/workflows/` path | 25 |
| Recognized dependency manifest or lockfile | 20 |
| Auth/security/permission/secret/token-named path segment | 25 |
| Infrastructure/deployment path, `.tf`, or `.bicep` | 15 |
| More than 100 changed lines | 10 |
| More than 400 changed lines, instead of the preceding factor | 20 |
| More than 10 changed files | 10 |
| Recognized code extension without a test-named path in the diff | 10 |

Scores 0-19 are low, 20-49 moderate, and 50-100 high review priority. A low or
zero score does not establish safety. Path-name heuristics can overcount or
miss risk; a changed test file does not prove coverage. The exact path and
extension rules live in `automation/pr_review/evidence.py`.

Files receive IDs F1, F2, and so on. Findings must cite an actual added line
such as `F1:L2` and one of the guideline section IDs G1-G4. Overview statements
cite file IDs. Deleted-only changes can have an overview but cannot receive
new-side inline findings. Valid citation IDs establish location, not truth.
Model confidence is subjective, not a probability or independent verification.

Each `(added-line evidence ID, category)` pair may appear only once in findings,
even when several guidelines apply. The model must combine related concerns
and recommendations for that pair into one finding. Its instructions and
schema describe this rule; the application still rejects duplicates rather
than silently discarding observations. The schema caps findings at the smaller
of five and the number of available line/category pairs.

Wording-only changes normally need only an overview, not invented findings.
Changed hunks do not establish that documentation, ownership, tests, or
safeguards are missing elsewhere. A documentation change can still warrant a
finding when the supplied evidence demonstrates a concrete material consequence.

## 5. Optional publication

After reviewing a live report and checking disclosure requirements, explicitly
publish that bundle:

```sh
.venv/bin/python -B -m automation.pr_review publish \
  --input reports/live-pr-review.json \
  --repo krshearman/systems-and-solutions --pr "$PR_NUMBER" \
  --confirm-post
```

The REST credential now needs pull-request write permission. Offline bundles
cannot be published as model reviews. Before posting, the application validates
the bundle, current guidelines fingerprint, exact PR identity, complete current
patches, and base/head references again.
In Actions, both jobs use the dispatch's trusted application revision, including
its guidelines; they do not switch to a newer default-branch checkout mid-run.

Publication creates one **COMMENT** review containing the explained score,
overview, and observations. Up to five observations with confidence at least
8/10 become new-side inline comments; lower-confidence observations remain in
the summary. It never submits APPROVE or REQUEST_CHANGES and does not alter code.
Model text is escaped, including mentions, before use in comments.

The API write is not retried. A network failure may occur after GitHub accepts a
review, so inspect the PR before rerunning; separate successful publications
can create duplicates. A small race remains between the final metadata check
and POST; `commit_id` pins the review to the analyzed head, and the report
identifies both SHAs even if the branch moves in that interval.

Suspected security issues may require private verification and coordinated
disclosure rather than a public comment. Opting into publication is not
verification of every AI claim.

## 6. Configure the GitHub Action

Merge the workflow into the default branch before expecting the Actions
`Run workflow` control. This implementation does not configure repository
secrets, environment protection rules, billing, or organization policies.

1. Create a GitHub environment named `copilot-pr-analysis`. Restrict its
   deployment branches to the repository's default branch. Optional required
   reviewers can gate credential access.
2. Store an eligible Copilot user credential as the environment secret
   `COPILOT_GITHUB_TOKEN`, not an unrestricted repository secret. Grant only
   required Copilot access. The workflow does not audit environment settings;
   the branch restriction is a required maintainer configuration.
3. In Actions, select **Advisory PR impact and security summary**, run from the
   default branch, enter an open PR number and allowed model, explicitly
   approve upload, and leave **publish** false for the first run.
4. Review the job summary and download the `pr-impact-review` artifact. Only
   choose **publish** true when authorizing a subsequent run to post its newly
   generated advisory review. That option is prospective authorization, not
   a pause for human review of the generated text.

The analysis job has contents-read and PR-read permissions and the Copilot
environment credential. It checks out only the dispatch's trusted default-branch
SHA and installs dependencies from that revision, never from the PR.
Untrusted patches arrive as API data. The model has no tools, MCP servers,
repository config discovery, plugins, or extensions.

The optional publication job depends on successful analysis, downloads only
that run's artifact, uses the same trusted application revision, and receives
PR-write permission but no configured Copilot credential. It treats the artifact
as JSON data, not executable code. There are no `pull_request` or
`pull_request_target` triggers. All user inputs reach shell commands through
quoted environment variables. Workflow concurrency serializes runs per PR.

Artifacts contain full patches and model text and expire after three days.
The job summary is another persisted copy under the Actions run's access and
retention controls; artifact expiry does not remove it. Consider repository
visibility before running. `reports/` is ignored locally.

## Limits and failures

This application and the multi-agent review team share a strict, text-only
input contract. These are application limits, not general GitHub or Copilot
platform limits.

| PR input | Supported limit |
| --- | --- |
| Changed files | 1-25 |
| Added lines, across all files | At most 1,000 |
| Combined patch characters, across all files | At most 50,000 |
| Patch availability | Complete textual patches for every changed file |

**Binary assets are unsupported even when the rest of the PR is text.**
GitHub does not supply textual patches for files such as PDF resumes and
WebP/PNG headshots. It can also omit patches for oversized or unavailable
text diffs. A missing patch fails the entire review with:

```text
Missing textual patch; binary or unavailable diffs are unsupported
```

An asset reported as having zero additions/deletions is not evidence that its
content was reviewed. Incomplete textual hunks are rejected too. Input
validation stops before model calls; no partial review is produced. Neither
CLI nor Actions provides a binary-file ignore option, automatic batching,
or truncation fallback.

Split oversized text changes into smaller reviewable PRs. For a PR containing
binary assets, use human review or appropriate asset-inspection tools; moving
those assets into a separate PR does not make that binary PR eligible.
Rerunning unchanged input, changing the model, or replacing credentials does
not resolve these input-contract errors. Resolving one limit may expose
another, so check file types, added-line totals, and patch size together.

Additional limits are 100,000 serialized model-input characters, 40,000
model-output characters, 16,000 guideline bytes, and 256,000 input JSON bytes.
API responses are capped at 1,000,000 bytes. Limits fail explicitly, never
truncate.

Output parents must exist and support hard links. Each report file is private
on POSIX and published atomically without replacement, with the JSON bundle
written last. The pair is not a filesystem transaction: a failed second write
can leave the Markdown file, but the command fails and Actions will not publish.
Authentication, API, schema, stale-evidence, timeout, and write errors exit
nonzero. No failed model request becomes an offline success.

## Validation record

Deterministic checks require no model calls:

```sh
python3 -B -m unittest discover -s tests -v
.venv/bin/python -B -m unittest discover -s tests -v
python3 -B tools/check_refactor_guard.py
```

CI runs the dependency-free and SDK-installed suites on Python 3.11 and 3.13.
Coverage includes exact patch/size boundaries, changed-line references,
schema/Unicode handling, score thresholds, stale and modified snapshots,
COMMENT-only payloads, inline confidence filtering, explicit consent, and
existing incident behavior. Workflow boundary assertions supplement local
actionlint validation; neither is a live GitHub execution.

With Go available, reproduce the workflow syntax check:

```sh
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12 \
  .github/workflows/pr-impact.yml .github/workflows/ci.yml
```

On 2026-10-15, an offline run and a real local SDK run on macOS/Python 3.13.2
with SDK 1.0.22 and `gpt-5-mini` produced reports from the bundled synthetic
fixture. The model identified the SQL interpolation concern conditionally and
also emitted lower-confidence observations, illustrating why human review
remains necessary. No actual GitHub review was posted. Live open-PR collection,
environment credentials, and Actions publication remain unverified remotely.
