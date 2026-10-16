# Multi-agent PR review team

This example demonstrates an application-controlled coordination graph, not
three personas taking turns in one conversation. Two isolated Copilot SDK
sessions review the same immutable PR snapshot concurrently. A third session
starts only after both outputs validate and consumes those results. The final
artifact is an advisory report for a human, never an approval or posted review.

The original architect and refactor-guard agents still use manual transitions.
This team uses three new role profiles and the shared PR evidence and SDK
transport. [ADR 0004](../adr/0004-coordinate-pr-review-with-validated-handoffs.md)
records the proposed architectural choice.

## Roles and handoffs

| Stage | Receives | Produces |
| --- | --- | --- |
| Architecture specialist | Bounded pinned snapshot and trusted engineering guidelines | Architecture/impact observations, added-line and guideline citations |
| Security specialist | The same snapshot and guidelines, in a separate context | Conditional security findings with the same citation requirements |
| Application validation barrier | Both structured specialist replies | Validated results with stable architecture IDs `AO1`, `A1` and security IDs `SO1`, `S1` |
| Coordinator | Validated observations, their IDs, cited changed-line snippets, snapshot identity, and trusted guidelines | Cited synthesis, a priority for every finding, potential disagreements, and human-review questions |
| Application and human reviewer | Validated synthesis plus all original findings | Local JSON/Markdown for human evaluation; no automated publication or remediation |

The coordinator cannot add findings, suppress an original finding, or rewrite
its severity/confidence. Every finding must appear exactly once in its review
order. High/critical findings must be `first`; medium findings cannot be
`later`. These are conservative ordering rules, not approval decisions.
Potential disagreements cite at least two findings and do not silently choose
a winner. No flagged disagreement is not evidence of consensus.

Application validation checks shape, ownership, citations, completeness, and
ordering constraints. It cannot prove the semantic truth of a model's prose,
the completeness of the specialist reviews, or the existence of a real
disagreement. Human reviewers must check these against the actual change.

## Run without a model

From the repository root, with Python 3.11 or later:

```sh
mkdir -p reports
python3 -B -m automation.review_team \
  --fixture examples/pr_review/pull_request.json \
  --replay examples/review_team/replay.json \
  --output reports/review-team.json
```

This runs the same asynchronous graph and validators using **authored replay
outputs**, not SDK sessions or recorded model responses. No SDK installation,
credential, network access, or model upload is needed. Replay requires a
fixture; it cannot masquerade as a live review of a fetched PR.

The bundled snapshot's PR number, SHAs, source snippets, and dependency are
fictional. Its metadata risk score is 55/100 using the existing
[single-agent scoring rubric](pr-impact-walkthrough.md). The authored replay
preserves three findings and flags a tension between caller-validation context
and query-boundary protection. That is an illustrative coordination case,
not advice that input validation replaces parameter binding.

Role outputs are fixed in replay, but request UUIDs and timings vary. The
Markdown report explicitly says that no model sessions ran.

## Run three real SDK sessions

Use an eligible, authenticated Copilot account and the pinned optional SDK:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-copilot.txt
.venv/bin/python -m copilot download-runtime
mkdir -p reports
.venv/bin/python -B -m automation.review_team \
  --fixture examples/pr_review/pull_request.json \
  --model gpt-5-mini --allow-model-upload \
  --output reports/review-team-sdk.json
```

The runtime is prepared once before concurrent requests. Model availability
depends on the account; supply an explicitly supported model. Both specialists
and the coordinator use that same model in separate sessions, not independently
corroborating models. There are exactly three requests on a successful run,
with at most two concurrent. A failed specialist stage can consume up to two
requests without reaching synthesis; there are no automatic retries.
Account usage limits and model-specific billing still apply.

Logged-in local authentication is used unless `COPILOT_GITHUB_TOKEN` is
supplied through the environment. Do not put credentials on the command line
or into committed files. The shared SDK transport gives each call a separate
temporary working directory and client/session, no tools or MCP servers,
no repository/plugin configuration discovery, and a permission handler that
does not grant execution.

To use a real open GitHub.com PR, provide an appropriately scoped read
credential through `GH_TOKEN` or `GITHUB_TOKEN`, then:

```sh
.venv/bin/python -B -m automation.review_team \
  --repo OWNER/REPOSITORY --pr 123 \
  --model gpt-5-mini --allow-model-upload \
  --output reports/review-team-live.json
```

Replace the repository/number with an authorized open PR. The application
fetches a bounded REST snapshot and rechecks its immutable references; it does
not check out, import, build, or execute the proposed code.

**Approve and sanitize data before upload.** The two specialist calls receive
the patches and guidelines; the coordinator receives their observations and
cited snippets. There is no automatic secret redaction. Reports contain the
full snapshot, validated observations, and provenance; treat them as sensitive
when reviewing non-public changes. PR content and specialist replies remain
untrusted data and cannot expand runtime permissions.

## Inspect the report and trace

Every successful run creates a new `.json` bundle and sibling `.md` report.
Both paths must be unused, their parent directory must exist, and symlinks
cannot be overwritten. The Markdown is written first and JSON last; each file
uses atomic no-overwrite publication, but the pair is not a transaction. A
filesystem failure can leave only the Markdown. A complete JSON bundle is the
completion artifact; inspect errors rather than treating a lone Markdown as
successful completion.

The report contains coordinator source links, the complete original specialist
observations, review priorities with unchanged severity/confidence, questions,
metadata risk factors, and an execution trace. Stable IDs depend on role and
validated output order, not which concurrent specialist finishes first.

Trace events record scheduling, starting, and successful validation. A
successful trace must show both specialist validations before the coordinator
starts. Application-assigned request IDs identify stages; they are **not SDK
session IDs**. The JSON also records:

- The pinned snapshot and guideline SHA-256.
- Fixed role-profile paths and full-file SHA-256 fingerprints.
- SHA-256 of the serialized data prompt and canonical validated output for each event.

The data-prompt hash is not a fingerprint of the entire runtime/system prompt.
Profile hashes identify the files read; specialist instructions also include
the shared PR system instructions in application code. Hashes and timestamps
help inspect execution and provenance, not prove model accuracy, independent
reasoning, or a semantic audit. Hidden model reasoning is not collected.

## Failure behavior and limits

### PR input eligibility

The team inherits the single-agent reviewer's limits: 1-25 changed files,
1,000 total added lines, and 50,000 combined patch characters. **Every changed
file must have a complete textual patch.** These checks run before any
specialist or coordinator model call.

A PR adding a PDF resume or a WebP/PNG portrait is unsupported, even if its
code and documentation are otherwise reviewable. Missing patches fail with
`Missing textual patch; binary or unavailable diffs are unsupported`.
GitHub can omit text patches as well as binary patches, and incomplete hunks
are rejected. The application does not assume an omitted patch is harmless.
There is no file-ignore, partial-review, automatic batching, or truncation
mode in either the CLI or Actions workflow.

Use smaller text-only PRs for live evaluation, and review binary assets
manually or with appropriate tooling. Splitting oversized text changes can
resolve size errors; isolating a binary asset in its own PR does not make that
PR supported. Rerunning unchanged input or changing the token/model will not
resolve these errors. Fixing one condition may expose another exceeded limit.
See the [shared limits and recovery guidance](pr-impact-walkthrough.md#limits-and-failures).

### Model-output failures and request budgets

If a specialist fails authentication, times out, or returns invalid output, its
sibling is cancelled and the coordinator is not invoked. Cancellation requests
local cleanup; it does not guarantee the provider did no billable work.
Invalid coordinator output likewise aborts. These failures return a nonzero
exit code and create no success report. There is no silent replay fallback,
partial-success synthesis, or model-generated replacement for a failed role.
Failed-run trace events are not persisted as a successful report.

The specialist contract allows at most one finding per `(evidence, category)`
pair, even when multiple guidelines apply. Specialists must combine related
concerns for a pair before returning their reply. The shared instructions and
schema state this restriction explicitly, and the schema's item budget cannot
exceed the number of possible unique pairs. Actual duplicate pairs remain a
hard validation failure; no finding is silently dropped and no retry is added.
For a wording-only edit, an overview with zero findings is normally appropriate.
The model must not infer absent documentation or safeguards from a partial
file diff, but concrete material documentation concerns remain in scope.

The serialized specialist prompt and coordinator
handoff each have a 100,000-character cap. Each model reply has a
40,000-character cap. Each specialist can return 1-3 overview statements and
0-5 findings; coordinator synthesis retains all findings from both roles.
Each text field is at most 600 characters without C0/C1 control characters.
Role profiles have a 12,000-byte cap. A handoff exceeding its budget aborts
before the third request rather than being truncated.

`--timeout` is a per-request deadline: positive seconds, at most 600, default
120. There are two sequential stages, not three sequential calls. The team
does not recursively create agents, retry, edit files through models, post
comments, approve merges, or invoke the existing publication command.

## Maintainer-triggered Actions

After merging the workflow and application into the default branch:

1. Reuse the `copilot-pr-analysis` environment and its `COPILOT_GITHUB_TOKEN` secret configured for the single-agent PR workflow.
2. Open **Actions → Multi-agent PR review team (SDK) → Run workflow**, select the default branch, and supply an open PR number and available model.
3. Explicitly approve model upload, run, then inspect the advisory job summary and `pr-review-team` JSON/Markdown artifact.

The [workflow](../../.github/workflows/pr-review-team.yml) checks the dispatch
branch and upload approval, checks out the trusted dispatch SHA without
persisted credentials, installs the pinned SDK, and predownloads its runtime.
Its GitHub token has only contents-read and PR-read permissions. There is no
publication job or opt-in posting mode.

Artifacts request three-day retention. The job summary is a separate copy
subject to Actions run/log retention, not that artifact setting. Choose data
appropriate for everyone who can view either surface. The environment's
configured protection/reviewer rules still apply. The workflow has a
15-minute timeout and serializes runs for the same PR.

## Verification and surface boundaries

On 2026-10-15 the dependency-free replay and a live three-request run completed
locally on macOS with SDK 1.0.22 and gpt-5-mini against the bundled synthetic
snapshot. Both specialists validated before the coordinator started, and the
coordinator's finding references validated. An earlier live attempt rejected
control characters in coordinator output without writing a report; the schema
and profile now explicitly expose that existing plain-text restriction.

Automated tests exercise a synchronization barrier proving both specialists
enter before either can finish, fan-in ordering, cancellation, role ownership,
finding retention, citation/priority validation, escaping, and CLI boundaries.
Existing SDK tests cover the shared isolated transport. Workflow syntax has
been checked locally. The first
[remote team run](https://github.com/krshearman/systems-and-solutions/actions/runs/38816283832)
reached specialist inference on a one-line README edit but rejected duplicate
architecture findings before coordinator execution. The uniqueness rule had
not been communicated in the model instructions/schema; those now match the
existing validator, with regression coverage for the one-line case and strict
duplicate rejection. The same public PR completed locally with the updated
contract. A subsequent
[successful Actions run](https://github.com/krshearman/systems-and-solutions/actions/runs/38822130409)
completed specialist validation, coordinator synthesis, and report generation.
The maintainer confirmed the generated review report. Model noncompliance can
still fail validation; this does not guarantee every future response is valid
or semantically correct.
The existing single-agent workflow's successful publication is not a team run.

The application explicitly loads three `.agent.md` instruction bodies. It does
not demonstrate native profile discovery, native skill activation, or editor
handoffs. Frontmatter is not the runtime permission authority. Native use of
these new profiles in VS Code, CLI, or GitHub.com has not been verified.
See the [surface guide](../copilot-surfaces.md) for separate observations.
