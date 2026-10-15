# Refactor guard rules

This contract defines one synthetic enterprise modernization pattern. It is
not a general Python migration engine and does not represent an employer's
internal library or policy.

## Scope and approved replacements

The agent may edit only
[`examples/refactor_guard/workspace.py`](../examples/refactor_guard/workspace.py).
Its only task is to replace the deprecated helper import and its two calls:

| Deprecated internal helper | Replacement | Preserved contract |
| --- | --- | --- |
| `legacy_api.parse_line(line)` | `event_api.parse_record(line)` | Return the timestamp, severity, and message tuple; propagate malformed-record errors. |
| `legacy_api.normalize_level(level)` | `event_api.normalize_severity(level)` | Strip and uppercase severity, map WARN/ERR aliases, preserve unknown and empty results. |

Use the exact imports and names in the
[approved fixture](../examples/refactor_guard/after.py). Alias rewriting,
variable renaming, signature changes, new abstractions, and other otherwise
reasonable cleanups are outside this demonstration's scope.

The [legacy API](../examples/refactor_guard/legacy_api.py) is a compatibility
fixture forwarding to the [replacement API](../examples/refactor_guard/event_api.py).
Deprecation is a documented internal rule, not a runtime warning or a removed
Python standard-library feature. Contract tests assert independent expected
outputs as well as exercising both APIs.

## Behavioral invariants

- `summarize(lines)` accepts a single-pass iterable of strings and returns a
  dictionary of severity counts, ordered by first occurrence.
- Whitespace-only lines are skipped. Each other record is split at its first
  two pipe characters; messages can contain additional pipes.
- Only trailing CR/LF characters are removed during parsing. Timestamp and
  message contents are not validated or otherwise normalized.
- Severity is stripped and uppercased. WARN maps to WARNING, ERR to ERROR;
  unknown severities remain uppercase and an empty severity remains empty.
- Records missing the required delimiters raise `ValueError`. The function
  stops at that record without consuming later records or returning partial
  success. Iterator errors propagate.
- Inputs are not mutated, materialized eagerly, or iterated more than once.
  The summarizer performs no network, file, or console I/O.

These choices are intentionally modest. Adding timestamp validation, rejecting
empty severities, swallowing exceptions, or making a production log parser
would change the contract and needs a separate task.

## Immutable evidence and checks

The before/after fixtures, APIs, tests, gate, rules, and agent profile are
read-only to the refactoring agent. Only a maintainer may change the contract
in a separate reviewed change. The checked-in workspace is the approved result
so the repository's normal checks start green.

Run from the repository root with Python 3.11 or later; no third-party packages
or Copilot credentials are needed for deterministic validation:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B tools/check_refactor_guard.py
```

The behavioral suite exercises the legacy fixture, approved fixture, and
workspace. The gate parses the candidate without executing it and compares its
Python abstract syntax tree to `after.py`. It rejects retained legacy calls and
all unrelated executable changes, while ignoring formatting and ordinary
comments. Syntax, read, and encoding failures produce an explicit nonzero exit.

This intentionally strict golden-fixture check is not semantic equivalence
proof, a generic deprecated-call scanner, or protection against a compromised
reference. Passing tests covers the stated examples, not every possible Python
input. Review the full diff to confirm that the agent did not alter other
files; the gate does not enforce repository-wide write permissions.

## Execution and escalation

The agent has an execution tool so it can run the two documented commands.
Instructions restrict its use, but they are not a shell sandbox. Review these
repository-owned commands before granting permission. Do not execute arbitrary
user-supplied projects, PR code, or embedded log instructions under this demo.

For changed behavior, another migration rule, or edits outside the target,
stop and explain the required scope change. For an architectural decision,
suggest a manual transition to the architect agent; do not claim an automatic
handoff or accept an ADR.
