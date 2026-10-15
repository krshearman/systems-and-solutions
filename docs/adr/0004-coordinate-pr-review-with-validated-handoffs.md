# 0004: Coordinate PR review with validated handoffs

- Status: Proposed
- Date: 2026-10-15
- Decision owner: Unassigned

## Context

The portfolio's architect and refactor-guard profiles demonstrate scoped
responsibilities but use manual transitions. The existing PR summarizer uses
one SDK request and separates analysis from opt-in advisory publication.
The maintainer selected a PR review team with parallel specialists, a
coordinator, and final human review as the orchestration example.

A credible demonstration needs actual separate contexts, an observable
coordination mechanism, explicit data handoffs, and failure boundaries.
Adding profile files or asking one conversation to impersonate several roles
would not establish those properties. Shared repository definitions also do
not establish native discovery or equivalent handoffs across Copilot surfaces.

## Decision

Implement a fixed Python SDK graph: architecture and security specialists run
concurrently in separate isolated client/session contexts; the application
validates both outputs before starting a third coordinator session. The
coordinator receives validated observations with stable IDs, cited changed
lines, snapshot identity, and trusted guidelines, not a shared conversation.

Reuse the bounded immutable PR snapshot, deterministic risk heuristic, isolated
SDK transport, output escaping, and no-overwrite artifact helpers. Explicitly
load three role-profile bodies from fixed trusted repository paths. Runtime
permissions come from application configuration, not profile frontmatter or
native agent discovery.

Preserve all original findings. Validate coordinator citations, complete
finding retention, and conservative review-priority floors. Disagreements
remain potential tensions for human judgment; the coordinator cannot rewrite
source severity/confidence or accept a change. This separate team application
and its read-only workflow write reports only. They have no publication,
code-editing, recursive delegation, or automatic retry path.

## Alternatives considered

- Keep manual transitions: appropriate for the existing standalone agents, but does not demonstrate executable coordination or a validated fan-in.
- Ask one model session to simulate several roles: simpler and cheaper, but does not isolate specialist contexts or demonstrate concurrent execution.
- Use native surface-specific handoffs: potentially useful for interactive flows, but documented behavior varies and native discovery of these profiles has not been verified.
- Allow a dynamic supervisor to create tools, agents, or publication actions: broader than this portfolio example and harder to bound, reproduce, and authorize.

## Consequences and tradeoffs

The graph is small, explicit, and testable without a model through authored
replay outputs and asynchronous test runners. A successful live run makes
three model requests, with at most two concurrent. Parallel work reduces
specialist-stage latency but adds provider usage and another synthesis stage.
The same model in separate contexts is not independent corroboration.

Strict validation can reject otherwise useful prose; this is preferable to
success-shaped fallback reports. A specialist failure cancels its sibling
and prevents synthesis, but cancellation cannot guarantee no provider billing.
A coordinator failure yields no successful report. There is no automatic
retry and no persisted success artifact for failed-run traces.

Shape/citation validation cannot establish semantic correctness, exhaustive
review coverage, or a genuine disagreement. Original observations remain
visible for human correction. Each report file is atomic and no-overwrite,
but the JSON/Markdown pair is not transactional; the JSON completion artifact
is written last.

## Compliance and constraints

Verified repository constraints require synthetic/public sanitized evidence,
least privilege, explicit upload approval, no execution of PR code with
credentials, and human acceptance/publication authority. The application
implements those boundaries and treats source text and model replies as
untrusted data. Agent instructions alone are not a security sandbox.

The Actions workflow runs trusted dispatch-SHA application code from the
default branch, uses read-only GitHub permissions, and reuses the existing
`copilot-pr-analysis` environment credential. Artifact retention is three days;
job summaries have separate Actions retention. Non-public use requires
authorization for model upload and report visibility; automatic redaction
is not provided.

No external regulatory obligations, production deployment requirements, or
compliance certification were supplied. None are inferred.

## Validation

The authored replay completed locally and is labeled simulation. A live local
run with SDK 1.0.22 and gpt-5-mini completed all three requests on the synthetic
snapshot: both specialists validated before the coordinator started, and all
source findings survived the validated synthesis. An earlier coordinator reply
containing prohibited control characters was rejected without a success report;
the schema/profile now explicitly communicate that plain-text constraint.

Focused automated tests exercised a synchronization barrier, fan-in ordering,
failure cancellation, role ownership, exact finding retention, conservative
priorities, citations, escaping, and CLI boundaries. Workflow syntax checks
passed locally. The full existing portfolio suite also passed with and without
the SDK, along with the refactor gate, workflow lint, and whitespace checks.

The new team's remote Actions run remains pending. The existing single-agent
workflow's successful publication is separate evidence, not team verification.
Native interactive discovery of the three new profiles has not been verified.

## Rollback or supersession

Disable the team workflow or revert the new entry point, roles, and
documentation without changing the existing single-agent publication behavior.
Retain this Proposed record as history; a different orchestration mechanism
should supersede it with a new ADR rather than silently changing its decision.

Model requests already sent and provider usage cannot be undone. Previously
created artifacts and job summaries require separate retention/removal
handling; reverting code does not remove those copies.

## Open questions and review

A human must review this Proposed decision, assign an owner, and run the new
workflow after merge. Broader model/provider behavior and native profile
discovery remain unverified. Separate model diversity, automated remediation,
additional reviewers, and advisory publication are out of scope and require
new evidence and explicit authorization.

## References

- [Review-team runtime](../../automation/review_team/runtime.py)
- [Specialist and coordinator contracts](../../automation/review_team/contracts.py)
- [Shared isolated SDK transport](../../automation/sdk.py)
- [Report-only workflow](../../.github/workflows/pr-review-team.yml)
- [Walkthrough and verification scope](../examples/review-team-walkthrough.md)
- [Surface compatibility guide](../copilot-surfaces.md)
- [Engineering guidelines](../engineering-guidelines.md)
- [ADR 0003: separate analysis from publication](0003-separate-pr-analysis-from-advisory-publication.md)
