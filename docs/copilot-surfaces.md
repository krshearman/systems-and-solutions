# Copilot surface compatibility

A **surface** is the product experience through which Copilot runs: for example,
VS Code, Copilot CLI, or the coding agent on GitHub.com. Shared repository files
do not imply identical tools, permissions, discovery, or orchestration.

## Current milestone

| Surface | Custom agent and ADR skill | Handoffs | Verification in this repository |
| --- | --- | --- | --- |
| VS Code with GitHub Copilot | Repository agents and skills are documented features. Select `architect-agent` in the agent picker; use a configuration that permits repository reads and draft edits. | VS Code documents `handoffs` suggestions. None are configured here. | Not yet live-verified. |
| GitHub Copilot CLI | Repository agents and skills are documented features. Start in the repository and select `architect-agent` using the CLI's agent picker. | No CLI handoff behavior is assumed by this repository. | Not yet live-verified. |
| Copilot coding agent on GitHub.com (called cloud agent in current docs) | GitHub documents custom agent profiles and repository skills. The definitions must be available on the branch used for the task, with access and repository configuration permitting the agent to run. | GitHub documents that VS Code `handoffs` are ignored by the cloud agent. | Not yet live-verified. |
| GitHub Actions running a future Copilot SDK application | Planned, not implemented. An SDK application must explicitly configure its instructions, tools, and coordination; this repository does not assume automatic discovery of these files. | Application-controlled orchestration, not editor handoff buttons. | No SDK application exists yet. |

This matrix covers only the intended surfaces for this showcase, not every
product that supports skills. It records documentation-based capabilities, not
an end-to-end compatibility certification.

## Portable baseline and limitations

The agent uses `name`, `description`, and the documented `read`, `search`, and
`edit` tool aliases. It does not pin a model, configure MCP servers, or declare
surface-specific handoffs. Tool mappings and availability still vary; confirm
the selected surface exposes the needed tools before use.

The architect deliberately has no shell tool. Supply a diff through the surface
or attach/paste it when requesting change analysis. Repository file access alone
does not establish what changed. For a current-design analysis without a diff,
state that scope explicitly.

The skill is discoverable through its name and description, and the architect
also links to it explicitly. Discovery does not guarantee activation. If native
skill loading is unavailable, the agent must disclose that it read the skill
and template manually. That fallback is not evidence of native skill support.

The current workflow ends at a proposed ADR and human review. Future multi-agent
coordination must document each surface's actual mechanism, including a manual
transition where appropriate.

## Prerequisites

Use a Copilot-enabled account with access to the chosen surface. Install and
authenticate the relevant editor integration or CLI, or enable the coding agent
for the repository on GitHub.com. Availability can depend on organization policy,
product version, and account access.

For GitHub.com, local unpushed files are not available to a remote agent. Publish
the definitions through the normal reviewed repository workflow before trying
them there.

## Verification record

Before marking a surface verified, run the
[walkthrough](examples/architect-walkthrough.md) and record the product/version,
date, model, supplied context, native skill activation versus fallback,
resulting ADR, boundary observations, and failures. Do not include credentials
or private transcripts. A successful file-format check is not live verification.

## Sources

Documentation consulted on 2026-10-15; revisit before changing compatibility
claims because surface capabilities evolve.

- [GitHub custom agent configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration):
  profile properties, tool aliases, and cloud-agent handoff limitations.
- [GitHub agent skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills):
  supported surfaces and repository skill locations.
- [Adding agent skills](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills):
  frontmatter and resource layout.
- [VS Code custom agents](https://code.visualstudio.com/docs/copilot/customization/custom-agents):
  agent discovery, tools, and handoffs.
