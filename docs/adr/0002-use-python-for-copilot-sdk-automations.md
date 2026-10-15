# 0002: Use Python for Copilot SDK automations

- Status: Acceoted
- Date: 2026-10-15
- Decision owner: @krshearman

## Context

The portfolio roadmap includes two unimplemented Copilot SDK applications: a
GitHub Actions PR impact and security summarizer, and a CLI incident post-mortem
helper. Choosing a shared implementation language affects maintenance,
dependency management, testing, and the skills demonstrated by the portfolio,
so the choice warrants an ADR.

During the live walkthrough on 2026-10-15, the maintainer selected "Use Python
for both planned Copilot SDK automations." When asked for the primary reason,
the maintainer answered "all of the above" to these options: readable automation
and log/data-processing libraries, consistency with existing Python experience
and tooling, and showcasing Python engineering skills.

These are user-stated motivations, not measured comparisons of language
performance or SDK quality. The README still marks both applications Planned;
there is no existing SDK implementation to migrate.

## Decision

Use Python as the application language for both planned Copilot SDK
automations. Keep their distinct entry points: GitHub Actions invokes the PR
analysis application, and a local CLI invokes the incident report application.

Favor consistent testing and dependency practices across the two applications.
Extract shared code only when actual common behavior exists. Keep parsing,
output validation, risk calculation, and rendering independently testable from
model calls, as required by the engineering guidelines.

This decision selects a language only. It does not select a Python version,
package manager, SDK release, model, authentication method, risk formula, or
incident-log format, and does not authorize implementation or deployment.

## Alternatives considered

**TypeScript for both applications:** A credible alternative for SDK-driven
automation and GitHub integrations. It is not selected because the maintainer
prioritized Python experience, readability, data-processing workflows, and
Python portfolio evidence. No comparative prototype was run, so no claim is
made that TypeScript is technically unsuitable.

**A different language for each application:** This could tailor each tool to
its integration needs and demonstrate a broader language range. It is not
selected because it would introduce two application-language toolchains
without a demonstrated requirement for that complexity.

**Defer the language choice:** This would preserve flexibility until prototyping
but leave the roadmap without the maintainer's preferred implementation
direction. The Proposed status allows that preference to be revisited if a
prototype exposes a blocker.

## Consequences and tradeoffs

**Benefits:** The choice aligns both applications with the maintainer's stated
experience and portfolio goals. A common language creates an opportunity to
reuse conventions and proven helpers without requiring a shared framework.
The expected readability and data-processing benefits remain design
motivations, not benchmark results.

**Costs:** Python environments, dependencies, SDK runtime requirements, and
authentication must be reproducible locally and in GitHub Actions. This choice
does not eliminate any runtime components required by the SDK.

**Risks and planned mitigations:** Model output can be malformed regardless of
language. Plan explicit schema validation and failure reporting rather than
trusting type annotations or generated prose. SDK APIs and runtime requirements
may change; check a selected release and record a working configuration before
implementation claims are made. These mitigations are not yet implemented.

## Compliance and constraints

Verified project constraints come from the engineering guidelines: sanitized
public demonstration data, traceable claims, human acceptance, least-privilege
PR automation, and no privileged execution of untrusted fork code.

Future incident examples must not introduce private logs or credentials. Future
PR security observations remain advisory and do not replace deterministic
checks. Selecting Python does not enforce these constraints by itself.

No external regulatory or employer requirements were supplied. Applicability
is unassessed; no compliance certification is asserted.

## Validation

The official Python SDK README was consulted during this walkthrough and
documents a Python SDK, installation instructions, and runtime prerequisites.
That documentation establishes a candidate implementation path, not successful
execution in this repository.

Native loading of `architectural-decision-record` was attempted in this
existing Copilot app session and returned "Skill not found." The assistant then
explicitly read the repository skill, template, guidelines, compatibility
guide, and existing ADR. This draft exercises the documented manual fallback;
the custom architect agent was not selected or invoked.

Before implementation is considered working, select supported Python and SDK
versions, verify runtime setup and authentication, and run a minimal SDK call
locally and on the intended Actions runner. Then test deterministic parsing
and output validation without model calls, plus failure handling with sanitized
fixtures. Those SDK and application checks have not been run.

## Rollback or supersession

Before implementation, revise this Proposed record only through an explicit
review request. If accepted and later invalidated by a prototype, add a
superseding decision rather than rewriting history.

Changing languages after implementation would require replacing application
code, dependency setup, and workflow invocation while preserving documented
report contracts and behavior checks. This draft itself changes no runtime,
deployed service, or stored incident data.

## Open questions and review

The maintainer's language preference is confirmed; acceptance of this ADR
remains pending. Assign a decision owner during review.

Which supported Python and SDK versions, dependency tooling, and authentication
strategy should implementation use? What schemas and representative fixtures
will define successful PR and incident reports? These choices remain open and
are not prerequisites for documenting the language preference.

Native skill discovery in a fresh session and custom-agent execution remain
separate verification tasks. This walkthrough does not establish why native
loading failed or whether restarting would resolve it.

## References

- Maintainer decisions in the live walkthrough conversation, 2026-10-15:
  "Use Python for both planned Copilot SDK automations" and "all of the above"
  in response to the three rationale options reproduced in Context.
- [Portfolio roadmap](../../README.md)
- [Project engineering guidelines](../engineering-guidelines.md)
- [Copilot surface compatibility](../copilot-surfaces.md)
- [ADR skill](../../.github/skills/architectural-decision-record/SKILL.md)
- [ADR template](../../.github/skills/architectural-decision-record/templates/adr.md)
- [Official Python SDK README](https://github.com/github/copilot-sdk/blob/main/python/README.md),
  consulted 2026-10-15; a mutable reference, not a pinned implementation version.
