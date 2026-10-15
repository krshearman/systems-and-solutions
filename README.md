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
| [Refactor guard](.github/agents/refactor-guard.agent.md) | Implemented; live agent verification pending | Scoped Python modernization, behavioral contracts, and a deterministic change gate |
| PR impact and security summarizer | Planned | Copilot SDK automation, explained risk scoring, and GitHub review integration |
| Incident post-mortem CLI | Planned | Evidence-linked timelines and executive-ready draft reports |

The current showcase has two specialized agents and a reusable ADR skill.
Transitions between agents are manual, **not yet automated multi-agent
orchestration**. Later milestones will demonstrate explicit coordination rather
than merely adding more agent files.

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

## Try refactor guard

The Python example replaces two deprecated synthetic internal helpers without
changing its incident summary's behavior. Its before/after fixtures, contract
tests, and strict syntax-tree gate make the permitted change concrete.

Run the dependency-free checks from the repository root with Python 3.11 or
later:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B tools/check_refactor_guard.py
```

Follow the [live walkthrough](docs/examples/refactor-guard-walkthrough.md) to
seed the legacy target, select `refactor-guard`, and demonstrate the gate moving
from failure to success. The checked-in workspace starts modernized so normal
checks pass. The [rules](docs/refactor-guard-rules.md) define its write boundary,
behavioral invariants, exclusions, and manual architecture escalation.

The [CI workflow](.github/workflows/ci.yml) runs the deterministic checks on
Python 3.11 and 3.13. It makes no model calls and does not verify live agent
behavior.

## Design and boundaries

The [engineering guidelines](docs/engineering-guidelines.md) define this
showcase's constraints. The architect reads evidence and uses the ADR skill to
draft documentation; it does not change application code, accept decisions,
certify compliance, or publish reviews.

Agent instructions are behavioral boundaries, not a security sandbox. Tool
permissions and human review remain necessary. Worked examples are synthetic,
not claims of production use. Architecture/ADR live verification was reported
by the maintainer; refactor guard's live custom-agent execution remains pending.
