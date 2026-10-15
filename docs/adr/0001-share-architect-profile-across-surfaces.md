# 0001: Share architect profile across surfaces

- Status: Accepted
- Date: 2026-10-15
- Decision owner: @krshearman

## Context

This portfolio starts with an architect agent and a reusable ADR skill. Its
intended Copilot surfaces are VS Code, Copilot CLI, and the coding agent on
GitHub.com. They share repository customization concepts but do not have
identical tools or handoff behavior.

The compatibility guide records documented capabilities and explicitly marks
live execution as unverified. This record is an illustrative draft prepared
with the initial definitions, not evidence of a successful agent execution.

## Decision

Propose maintaining one repository-local architect profile and one ADR skill.
Use the common profile fields and read/search/edit aliases, with no model pin
or automatic handoff configuration.

End this milestone at a Proposed ADR for human review. Native skill loading is
preferred; explicitly reading the skill and template is a disclosed fallback,
not a claim of native activation. Supply change evidence when requesting diff
analysis because the architect has no shell tool.

## Alternatives considered

**Surface-specific profiles:** These could expose tailored tools and handoff
controls. They are not selected for the first milestone because duplicated
behavior could drift and no live surface evaluations yet justify the extra
configuration.

**One generic prompt without a skill:** This would reduce file count but couple
the architect's role to the detailed ADR procedure and template. A separate
skill makes the procedure reusable independently of the agent.

## Consequences and tradeoffs

The shared profile keeps role boundaries and evidence rules in one place.
Separating the ADR procedure avoids duplicating its numbering and review rules.

The lowest-common-denominator approach omits useful surface-specific features.
Users must supply inaccessible diffs and make manual transitions. Tool aliases
and skill discovery still depend on the surface, so a shared file alone cannot
guarantee equivalent behavior.

Live walkthroughs are the proposed mitigation for compatibility uncertainty.
They have not yet been performed. Prompt-level write restrictions are not
filesystem security controls.

## Compliance and constraints

Verified project constraints are documented in `docs/engineering-guidelines.md`:
sanitized public examples, traceable claims, bounded edits, and human acceptance.
The agent definition limits tools to read/search/edit and instructs the agent
to write only ADR drafts; the latter restriction is behavioral.

No external regulatory or employer policy requirements were supplied. Their
applicability is unassessed, and this decision does not establish compliance
with an external standard.

## Validation

The profile and skill were authored against the official documentation linked
in the compatibility guide. No live surface execution is claimed.

Before accepting the compatibility assumptions, run the architect walkthrough
on each intended surface. Check profile discovery, skill activation or disclosed
fallback, complete template output, safe numbering, missing-evidence handling,
and absence of unrelated edits. Record failures as well as successes.

## Rollback or supersession

If a surface needs materially different configuration, introduce a clearly
targeted profile and document that exception with a new decision record.
Retain this record as history if accepted later; supersede rather than silently
rewriting it. This proposal itself changes no deployed service or stored data.

## Open questions and review

Which surface should receive the first live evaluation? Do actual runs justify
separate profiles or orchestration? Who will own acceptance of architecture
records? These questions remain for maintainer review.

## References

- [Architect profile](../../.github/agents/architect-agent.agent.md)
- [ADR skill](../../.github/skills/architectural-decision-record/SKILL.md)
- [Project engineering guidelines](../engineering-guidelines.md)
- [Surface compatibility and official sources](../copilot-surfaces.md)
- [Walkthrough and acceptance scenarios](../examples/architect-walkthrough.md)
