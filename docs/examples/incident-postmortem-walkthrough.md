# Incident post-mortem CLI

This is a usable Python CLI, not a fixed-output agent demonstration. It accepts
your own logs in either documented format, sorts their timestamps, retains
source-line citations, and writes an executive-oriented Markdown draft.

The timeline is deterministic. Optional Copilot SDK analysis adds a cited
summary, reported impact requiring verification, unverified cause hypotheses,
proposed actions, and open questions. It cannot establish root cause or certify
that a model's interpretation is correct.

## Input contract

Choose the format explicitly; the CLI does not guess.

**Timestamped text:** one record per line:

```text
2026-10-15T09:00:00Z INFO Deployment started.
2026-10-15T10:01:00+01:00 ERROR Probe returned HTTP 503.
```

**JSON Lines:** exactly these three string fields per record:

```json
{"timestamp":"2026-10-15T09:00:00Z","level":"INFO","message":"Deployment started."}
{"timestamp":"2026-10-15T09:01:00Z","level":"ERROR","message":"Probe returned HTTP 503."}
```

Use UTF-8 and ISO 8601 timestamps with seconds and an explicit `Z` or numeric
offset. Up to six fractional-second digits are supported. Naive timestamps,
duplicate JSON keys, extra/missing fields, control characters, malformed
nonblank lines, and invalid values fail explicitly. Blank lines are ignored,
but original physical line numbers remain the evidence IDs. Records sort in
UTC, with original line order breaking ties.

Levels contain ASCII letters, normalize to uppercase, and map WARN/ERR to
WARNING/ERROR. This is not a parser for arbitrary multiline stack traces,
syslog, vendor-specific JSON, or the earlier refactor demo's pipe format.
Convert such inputs deliberately before use; nothing is silently skipped.

Limits are 256 KiB per file, 200 events, 2,048 characters per message, and
60,000 characters in the serialized model prompt. Model output is limited to
40,000 characters. Exceeding a limit fails instead of truncating evidence.

## 1. Generate an evidence-only report

Run commands in a normal shell, including the canvas terminal, from the
repository root. Do not enter them into a Copilot chat prompt.

Python 3.11 or later is sufficient for this mode. No SDK, model call,
authentication, database, or plugin is required:

```sh
mkdir -p reports
python3 -B -m automation.incident_postmortem \
  --input examples/incident_response/service-incident.txt \
  --format text \
  --output reports/incident-evidence.md \
  --offline
```

For JSONL, substitute `service-incident.jsonl` and `--format jsonl`. The two
bundled synthetic files describe the same deliberately unordered events.
Both should produce the same timeline order: **L2, L3, L4, L1**.

Reports label the observed log window, not an outage duration. Evidence-only
mode is a deliberate choice, not a fallback after a model failure.

## 2. Install the optional SDK

Create an isolated environment rather than changing system Python:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-copilot.txt
```

The manifest pins `github-copilot-sdk==1.0.22`; transitive dependencies are not a
fully locked dependency graph. This version requires Python 3.11 or later and
uses a bundled runtime, which may download on first startup. To pre-download it:

```sh
.venv/bin/python -m copilot download-runtime
```

The live mode needs authenticated GitHub Copilot access, an allowed model, and
network access. It uses the logged-in user; see the
[SDK authentication guidance](https://github.com/github/copilot-sdk/tree/main/docs/auth).
Do not put tokens in committed files, report examples, or shell commands.
Model availability and usage charges depend on the account and selected model.

These are POSIX commands. On Windows, use the equivalent Python executable
under `.venv\Scripts\`.

## 3. Generate a Copilot-assisted draft

The following command sends only the bundled synthetic records. For your own
data, sanitize the logs and obtain any required approval first. There is no
automatic secret or personal-data redaction. The explicit upload flag is consent
for transmission, not proof that the data is safe.

```sh
.venv/bin/python -B -m automation.incident_postmortem \
  --input examples/incident_response/service-incident.jsonl \
  --format jsonl \
  --output reports/incident-copilot.md \
  --model gpt-5-mini \
  --allow-model-upload \
  --timeout 120
```

Substitute a model ID available to your account. No model is silently selected
or substituted. The SDK call uses an empty-mode client in temporary storage,
an empty tool allow-list, no repository config discovery, no extensions, no
personal plugins, and a permission handler that does not approve requests.
This CLI does not invoke the architect or refactor-guard agent.

The response is constrained with a JSON schema and validated again locally.
Factual findings must cite supplied evidence IDs. Unknown, duplicate, or missing
citations and malformed output are rejected. Valid IDs do not prove that their
associated statements are true; read the original lines.

No tools are granted to the model. This does not eliminate model inference
risks or network transmission of the explicitly supplied evidence. SDK auth and
runtime operations still use the network.

## 4. Review the report

Inspect the source filename and SHA-256 fingerprint, UTC chronology, citation
links, and distinction between findings and hypotheses. A deployment followed
by an error does not establish causation; an HTTP 200 probe does not establish
complete customer recovery. Confirm business impact, root cause, owners, and
deadlines before sharing.

Every report remains an unapproved draft. Action owners and deadlines are
unassigned rather than invented. Original messages are included in the timeline,
so reports themselves may contain sensitive information.

Output directories must already exist. Existing outputs, including symlinks,
are never overwritten. Reports are staged in the destination directory and
published without replacement using a hard link; use a filesystem supporting
that operation. Concurrent creation of the output fails rather than overwrites.
Temporary files are cleaned up. On POSIX the staged report is private to the
current user. `reports/` is ignored by Git; no report is automatically committed,
published, or accepted.

Invalid input, missing dependencies, authentication/runtime failures, invalid
model output, timeout, and output errors exit nonzero. A model failure never
becomes an evidence-only success. SDK diagnostics show a failure category rather
than dumping provider responses that might contain sensitive content.

## Validation and observed limitations

Run deterministic checks without network or model calls:

```sh
python3 -B -m unittest discover -s tests -v
.venv/bin/python -B -m unittest discover -s tests -p 'test_incident*.py' -v
```

Without the optional SDK, the API-signature compatibility test is explicitly
skipped. With it installed, that test binds adapter arguments to the actual
SDK signatures. Mocked SDK tests check isolation settings, permission denial,
cleanup, invalid responses, and explicit errors; they are not live-model proof.
CI covers both dependency-free and SDK-installed paths on Python 3.11 and 3.13,
without credentials or model calls.

On 2026-10-15, a local macOS/Python 3.13.2 smoke run with SDK 1.0.22 and
`gpt-5-mini` generated cited drafts from the bundled text and JSONL samples. The first
attempt failed explicitly because the provider rejected JSON Schema
`uniqueItems`; that keyword was removed from the provider schema while local
duplicate-citation rejection was retained. No report was written for the
failed attempt. This records a local integration observation, not validation on
every OS, model, log format, or Copilot surface. Review model interpretations;
format validation is not factual verification.
