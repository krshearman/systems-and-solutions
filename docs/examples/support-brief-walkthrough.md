# Support signal to engineering brief

## Problem and decisions

Support reports often mix observations, incomplete reproduction details, and
impact claims. This example preserves the original records, highlights missing
evidence, and optionally asks Copilot for cited synthesis and possible duplicate
relationships. It never treats similar symptoms as a confirmed shared cause.

The fixture is entirely synthetic. It contains two potentially related
queued-label reports and a different download failure. No employer/customer
data or production adoption is implied.

## Offline first

From the repository root, with Python 3.11 or later:

```sh
mkdir -p reports
python3 -B -m automation.support_brief \
  --input examples/support_brief/signals.json \
  --output reports/support-brief.md \
  --offline
```

The Markdown brief includes all source records, supplied reproduction steps,
reported impact, deterministic evidence gaps, source SHA-256, proposed next
steps, and the human issue-creation checkpoint. Offline mode does not perform
AI synthesis or propose duplicate candidates. Its absence of candidates is not
evidence that the reports are unique.

Read the report before sharing it. Input is not automatically redacted.
Nothing is sent over the network in offline mode.

## Optional Copilot synthesis

Use an authenticated Copilot CLI/account with model access, the pinned optional
SDK, and a Python environment containing `requirements-copilot.txt`:

```sh
python3 -m pip install -r requirements-copilot.txt
python3 -B -m automation.support_brief \
  --input examples/support_brief/signals.json \
  --output reports/support-brief-sdk.md \
  --model YOUR_MODEL_ID \
  --allow-model-upload
```

Replace `YOUR_MODEL_ID` with an available model ID. The upload flag explicitly
confirms approval to send the supplied evidence to Copilot; sanitize it first.
This uses the shared isolated, tool-free SDK transport, without repository
discovery, personal plugins, or MCP servers. It does not invoke the workshop
agent or its skill. Model calls can incur usage charges.

The response must contain cited summary claims, optional duplicate candidates,
proposed next steps, and open questions. Unknown/repeated citations, missing
sections, empty required sections, and invalid shapes reject the entire
response. A duplicate candidate needs at least two distinct source IDs.
Checks establish structural validity, not factual accuracy or prompt-injection
resistance. A human must assess source support, impact, and duplicate claims.

## Input contract and failures

Input is a UTF-8 JSON object containing only `signals`, with 1..25 records,
at most 65,536 bytes. Each record has exactly the fields shown in the fixture.
IDs are unique `S` plus 2..4 ASCII digits. Title, area, and observed behavior
must be nonempty; expected behavior, environment, and reported impact may be
empty strings. Reproduction is an array of 0..8 nonempty steps.

Text limits are 160 characters for title, 80 for area, 500 for environment and
each step, and 1,000 for observed/expected behavior and reported impact.
Control characters and duplicate JSON keys are rejected. All records stay
visible; the tool neither deduplicates nor silently truncates.
SDK prompts are limited to 50,000 characters after JSON serialization; model
output is limited to 40,000 characters. Reduce the evidence set if necessary.

The output parent must exist. Existing output files and symlinks are never
overwritten. Invalid input, SDK failures, and invalid analysis return nonzero
with an explicit error; they never become successful offline fallbacks.
Use a new filename on each run.

## Human checkpoint and evidence

Verify citations against the original records, independently reproduce where
possible, and confirm what may be shared. A human chooses the issue scope,
title, priority, and owner. This application has no issue-creation or publication
capability, no automatic routing, and no model-driven code execution.

Deterministic fixtures and mocked SDK tests cover ingestion, validation,
rendering, consent, no-overwrite behavior, and explicit failures. They do not
establish live model quality. Live SDK verification for this new tool has not
been recorded. To record it, note the date, model, command, sanitized output,
human citation review, and any rejected responses without exposing credentials.
