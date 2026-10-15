# Copilot surface compatibility

A **surface** is the product experience through which Copilot runs: for example,
VS Code, Copilot CLI, or the coding agent on GitHub.com. Shared repository files
do not imply identical tools, permissions, discovery, or orchestration.

## Current milestone

| Surface | Repository customizations | Handoffs | Verification in this repository |
| --- | --- | --- | --- |
| VS Code with GitHub Copilot | Repository agents and skills are documented features. Select `architect-agent` or `refactor-guard` in the agent picker. Refactor guard also needs permission to execute its checks. | VS Code documents `handoffs` suggestions. None are configured here. | See the maintainer report below; detailed per-surface records are not supplied. |
| GitHub Copilot CLI | Repository agents and skills are documented features. Start in the repository and select the desired custom agent using the CLI's agent picker. Refactor guard also needs permission to execute its checks. | No CLI handoff behavior is assumed by this repository. | See the maintainer report below; detailed per-surface records are not supplied. |
| Copilot coding agent on GitHub.com (called cloud agent in current docs) | GitHub's documented picker discovery flow requires merging a new repository agent profile into the default branch. Task evidence and fixtures must also be available on the selected starting branch, with access and repository configuration permitting execution. | GitHub documents that VS Code `handoffs` are ignored by the cloud agent. | See the maintainer report below; detailed per-surface records are not supplied. |
| Local Python application using Copilot SDK | Incident and single-agent PR tools supply instructions directly. The review team explicitly reads three profile bodies and supplies separate instructions and schemas to isolated, tool-free sessions; no native discovery or skill invocation. | The review-team application starts two specialists concurrently and passes validated results to a third coordinator session. This is SDK application orchestration, not editor handoffs. | Synthetic incident, PR, and three-role review-team runs completed locally on macOS with SDK 1.0.22 and gpt-5-mini. Offline replay is a separate simulation. |
| GitHub Actions running an SDK application | Maintainer-triggered workflows use trusted default-branch code and API-fetched patches, never a PR checkout. The single-agent workflow optionally posts a COMMENT review in a separate job; the review team has read-only GitHub permissions and no publication step. Both use the configured Copilot environment credential. | Single-agent analysis/publication sequencing or the review team's application-controlled parallel-specialist/coordinator graph, not native agent handoffs. | Single-agent model inference and advisory publication were verified in the linked run below. The new team workflow passed local syntax checks; its remote execution remains pending. |

This matrix covers only the intended surfaces for this showcase, not every
product that supports skills. It records documentation-based capabilities, not
an end-to-end compatibility certification.

On 2026-10-15 the maintainer reported successful architecture/ADR use across
multiple surfaces and marked that milestone verified in the README. Specific
surface names, versions, and run evidence were not supplied in this session,
so this guide does not assign that report to individual rows. The earlier
manual skill fallback remains a historical observation, not a claim that
native loading fails everywhere.

The maintainer subsequently marked refactor guard verified across multiple
surfaces in the README. A local CLI canvas snapshot confirmed the selected
agent, and independent checks confirmed the approved final workspace; that
snapshot did not retain the earlier prompt/action history. The incident SDK
observation is documented separately in its
[walkthrough](examples/incident-postmortem-walkthrough.md).
The PR summarizer has a separate
[walkthrough](examples/pr-impact-walkthrough.md) covering its manual trigger,
credential separation, and synthetic fixture. Its
[Actions run](https://github.com/krshearman/systems-and-solutions/actions/runs/38802036685)
completed analysis and publication on 2026-10-15 and posted an
[advisory review](https://github.com/krshearman/systems-and-solutions/pull/5#pullrequestreview-5539452380).
That is not evidence that the newer multi-agent workflow has run in Actions.

## Portable baseline and limitations

The original two agents use `name`, `description`, and the documented `read`, `search`, and
`edit` tool aliases. Refactor guard additionally requests `execute` for its
documented tests and gate. Neither pins a model, configures MCP servers, or
declares surface-specific handoffs. Tool mappings and availability still vary;
confirm the selected surface exposes the needed tools before use.

The architect deliberately has no shell tool. Supply a diff through the surface
or attach/paste it when requesting change analysis. Repository file access alone
does not establish what changed. For a current-design analysis without a diff,
state that scope explicitly.

The skill is discoverable through its name and description, and the architect
also links to it explicitly. Discovery does not guarantee activation. If native
skill loading is unavailable, the agent must disclose that it read the skill
and template manually. That fallback is not evidence of native skill support.

The architect ends at an ADR draft and human review. Refactor guard ends at a
bounded code change and actual check results; when architecture changes are
needed it suggests a manual transition to the architect. These original agent
roles do not automatically coordinate with one another.

## SDK review-team orchestration

The [review-team application](../automation/review_team/runtime.py) reads the
instruction bodies of `pr-architecture-reviewer`, `pr-security-reviewer`, and
`pr-review-coordinator` from fixed repository paths. It does not ask the SDK to
discover `.agent.md` profiles, activate skills, or interpret frontmatter
handoffs. The profiles declare no tools; actual runtime permissions are
independently configured by the shared isolated SDK transport.

Each live request creates a separate client, temporary working directory, and
session, with no repository/plugin discovery, model tools, or MCP servers.
Two specialist requests run concurrently; the coordinator starts only after
both pass application validation. It receives their structured outputs and
cited source snippets rather than a shared conversation. All findings survive
into the final human-review report. Any required stage failure aborts the run.

On 2026-10-15 a local synthetic-fixture run completed all three roles with
SDK 1.0.22 and gpt-5-mini, producing validated specialist outputs, coordinator
references, and an application execution trace. This verifies the application's
mechanism, not native discovery of the three new profiles in VS Code, CLI, or
GitHub.com. Those profiles' native interactive use has not been verified.
The report-only team Actions workflow likewise still needs a remote run.
See the [walkthrough](examples/review-team-walkthrough.md) for commands,
failure behavior, costs, and the distinction between replay and live sessions.

## Prerequisites

Use a Copilot-enabled account with access to the chosen surface. Install and
authenticate the relevant editor integration or CLI, or enable the coding agent
for the repository on GitHub.com. Availability can depend on organization policy,
product version, and account access.

Refactor guard's deterministic example targets Python 3.11 or later and uses
only the standard library. Its CI matrix covers Python 3.11 and 3.13; configuring
that matrix is not evidence of a completed remote run. The tests and gate do
not require Copilot access, while live custom-agent selection does.

For GitHub.com, local unpushed files are not available to a remote agent. Publish
the definitions through the normal reviewed repository workflow. GitHub's
documented setup requires merging a new agent profile into the default branch
before it appears in the picker; pushing only a feature branch is not that
discovery flow. Afterward, publish any seeded legacy target on a disposable
evaluation branch rather than merging it into the main implementation.

## Verification record

Before adding a per-surface verification record, run the relevant
[architect walkthrough](examples/architect-walkthrough.md) or
[refactor guard walkthrough](examples/refactor-guard-walkthrough.md). Record
the product/version, date, model, selected agent, supplied context, actual tool
execution, output, boundary observations, and failures. For the ADR skill,
distinguish native activation from fallback. Do not include credentials or
private transcripts. Deterministic fixture checks are not live-agent verification.

## Sources

Documentation consulted on 2026-10-15; revisit before changing compatibility
claims because surface capabilities evolve.

- [GitHub custom agent configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration):
  profile properties, tool aliases, and cloud-agent handoff limitations.
- [Creating repository custom agents](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/create-custom-agents):
  default-branch merge prerequisite for GitHub.com picker discovery.
- [GitHub agent skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills):
  supported surfaces and repository skill locations.
- [Adding agent skills](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills):
  frontmatter and resource layout.
- [VS Code custom agents](https://code.visualstudio.com/docs/copilot/customization/custom-agents):
  agent discovery, tools, and handoffs.
