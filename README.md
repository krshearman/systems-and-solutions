# systems-and-solutions

A professional portfolio of AI-assisted engineering: architectural decisions,
bounded refactoring, change-risk assessment, and incident learning. The emphasis
is on evidence, explicit boundaries, and human review rather than autonomous
approval.

## Showcase

| Component | Status | Demonstrates |
| --- | --- | --- |
| [Architect agent](.github/agents/architect-agent.agent.md) | Verified across multiple surfaces | Evidence-based change analysis and ADR skill composition |
| [ADR skill](.github/skills/architectural-decision-record/SKILL.md) | Verified across multiple surfaces | On-demand instructions, a reusable template, and proposed decision records |
| Refactor guard | Planned | Scoped modernization against documented engineering patterns |
| PR impact and security summarizer | Planned | Copilot SDK automation, explained risk scoring, and GitHub review integration |
| Incident post-mortem CLI | Planned | Evidence-linked timelines and executive-ready draft reports |

The current milestone is one specialized agent composed with a skill, **not yet
a multi-agent orchestration system**. Later milestones will demonstrate explicit
coordination and verification rather than merely adding more agent files.

## Try the architect agent

Open this repository in a supported Copilot surface and select `architect-agent`
from its custom-agent picker. For Copilot CLI, start your installed,
authenticated CLI from the repository root:

```sh
copilot
```

Then select the custom agent and submit:

```text
Use the architectural-decision-record skill to assess the decision to keep a
shared architect agent profile across Copilot surfaces, with manual transitions
instead of surface-specific handoffs. Read the repository's engineering
guidelines and surface compatibility guide. Draft a proposed ADR for human
review; distinguish documented platform support from execution verified here.
```

For change analysis, provide the relevant diff or PR context as well. The agent
must request missing evidence instead of claiming to have inspected a diff it
cannot access.

See the [walkthrough and acceptance scenarios](docs/examples/architect-walkthrough.md),
[illustrative ADR](docs/adr/0001-share-architect-profile-across-surfaces.md), and
[surface compatibility guide](docs/copilot-surfaces.md). Installation,
authentication, discovery, and tool availability depend on the surface; no SDK
or CI credentials are needed for these repository-local definitions.

## Design and boundaries

The [engineering guidelines](docs/engineering-guidelines.md) define this
showcase's constraints. The architect reads evidence and uses the ADR skill to
draft documentation; it does not change application code, accept decisions,
certify compliance, or publish reviews.

Agent instructions are behavioral boundaries, not a security sandbox. Tool
permissions and human review remain necessary. All worked examples are
illustrative, not claims of production use or successful live agent execution.
