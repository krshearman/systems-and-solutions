# 0003: Separate PR analysis from advisory publication

- Status: Proposed
- Date: 2026-10-15
- Decision owner: Unassigned

## Context

The portfolio needs a Python Copilot SDK application that summarizes PR impact
and security observations against repository guidelines. PR patches are
untrusted data, model output is fallible, and model access and review publication
need different credentials. The maintainer selected a manually triggered first
version with report-only behavior by default and explicit opt-in publication.

The existing incident tool provides an isolated SDK transport pattern. The
repository guidelines require least privilege, no execution of untrusted fork
code with secrets, validation before posting, and human accountability.

## Decision

Use a maintainer-triggered default-branch workflow with separate analysis and
publication jobs. Analyze immutable, complete, bounded textual patches fetched
through GitHub's API without checking out PR code. Calculate an explained
review-priority score locally, independent of model findings. Validate model
observations against added-line evidence and guideline section IDs.

The analysis job receives read-only repository/PR permissions and a separately
configured Copilot environment credential. Report-only is the default.
Explicit publication uses a separate PR-write job without the configured
Copilot credential, revalidates the report and current evidence, and submits
only COMMENT reviews. The local CLI follows the same split through separate
`analyze` and `publish --confirm-post` commands.

## Alternatives considered

- Automatically analyze every PR: less maintainer effort, but introduces
  recurring model charges and additional fork, workflow, and secret-boundary
  controls. Deferred for this first version.
- A single privileged analysis-and-posting job: simpler configuration, but
  needlessly couples model access and review-write authority. Not selected.
- Offline risk scoring only: reproducible and credential-free, but does not
  demonstrate the requested SDK analysis or advisory inline integration.
  Retained as an explicit mode rather than the only implementation.

## Consequences and tradeoffs

The workflow does not execute PR code or grant tools to the model. Publication
is explicit and uses independently revalidated locations. The score remains
reproducible when model output changes.

Costs include manual setup and triggering, bounded diff support, and possible
duplicate reviews after explicit reruns. There is no comprehensive source or
runtime analysis, calibrated risk probability, vulnerability assurance, or
automatic approval. Citation validity does not establish semantic correctness.
A small check-to-post race remains; the review is pinned to the analyzed commit.

## Compliance and constraints

These are public-portfolio constraints, not employer policies or a compliance
certification. No external regulatory requirements were supplied.

Before using the Action, the maintainer must configure the
`copilot-pr-analysis` environment, restrict it to the default branch, and store
an eligible Copilot credential there. The workflow does not audit those
settings or assume ordinary workflow-token Copilot entitlement. Upload requires
explicit authorization; secret and personal-data redaction are not implemented.
Reports and workflow summaries can themselves disclose code or sensitive
security observations, so publication and retention require human judgment.

## Validation

Local dependency-free and SDK-installed contract suites have run successfully,
including patch completeness, citation checks, risk thresholds, stale-evidence
rejection, permission separation, and COMMENT-only publication payloads.
Workflow syntax was checked with actionlint. A local synthetic-fixture SDK run
with SDK 1.0.22 and `gpt-5-mini` generated a report without posting.

Live Actions credentials, an open-PR end-to-end run, and actual review
publication still require maintainer verification. This record was drafted
using direct reads of the ADR skill instructions and template; native skill
activation is not asserted.

## Rollback or supersession

Disable or remove the dispatch workflow and revoke its Copilot environment
credential. Retain offline analysis if useful. Removing the workflow does not
erase posted reviews, job summaries, or downloaded artifacts; handle those
through GitHub controls. Supersede this record before introducing automatic
PR triggers, broader model tools, or approval authority.

## Open questions and review

Who will own environment configuration and credential rotation? Are the
project-defined scoring weights useful in practice? Should later versions
support larger diffs or calibrated evidence beyond changed lines? The record
remains Proposed pending human acceptance.

## References

- [Engineering guidelines](../engineering-guidelines.md)
- [PR walkthrough and operational limits](../examples/pr-impact-walkthrough.md)
- [Maintainer-triggered workflow](../../.github/workflows/pr-impact.yml)
- [Snapshot and scoring contract](../../automation/pr_review/evidence.py)
- [Validated COMMENT publication](../../automation/pr_review/github.py)
- [Shared isolated SDK transport](../../automation/sdk.py)
- [GitHub SDK authentication](https://github.com/github/copilot-sdk/blob/main/docs/auth/authenticate.md)
- [GitHub Actions environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
- [REST pull-request reviews](https://docs.github.com/en/rest/pulls/reviews#create-a-review-for-a-pull-request)
