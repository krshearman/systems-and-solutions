---
name: architectural-decision-record
description: Draft an evidence-backed Architectural Decision Record when a user requests an ADR or a change introduces a durable architectural choice. Capture context, alternatives, tradeoffs, compliance constraints, and human review.
---

# Architectural Decision Record

Use this skill to document one architectural decision, not to implement it or
accept it. This skill can be used by the architect agent or independently.

## Gather the decision

1. Read repository instructions, `docs/engineering-guidelines.md`, relevant
   evidence, and existing records under `docs/adr/`.
2. Establish the problem, chosen approach, meaningful alternatives, affected
   surfaces, and known constraints. Identify the source of each material claim.
3. If the choice is unresolved, ask one focused question before creating a
   selected-decision draft. Missing non-blocking details may remain explicitly
   labeled assumptions or open questions.
4. If no durable architectural choice exists, explain why an ADR is unnecessary
   and do not create one.

## Allocate the record safely

- Create records only under `docs/adr/`. Create that directory if absent.
- Inspect names matching `NNNN-title.md`, where NNNN is exactly four digits.
  Allocate one more than the largest existing numeric prefix, starting at
  `0001` in an empty directory. Do not reuse gaps or duplicate a prefix.
- Use a short lowercase ASCII kebab-case title. Construct the filename from
  that title, not an arbitrary user-provided filesystem path.
- Immediately before writing, recheck the directory and target. If another
  record has taken the number, allocate again. Never overwrite an existing file
  or delete a record to make room. If the surface cannot safely create a new
  file without overwriting, return the proposed contents without writing and
  explain the limitation. Numbering is not an atomic concurrency guarantee.
- Stop and ask the maintainer if the four-digit range is exhausted.
- Modify an existing Proposed record only when explicitly asked to revise that
  record; retain its number. Do not rewrite Accepted or Superseded records.

## Draft from the template

Read [templates/adr.md](templates/adr.md) and preserve its headings. Replace
placeholders with evidence-backed content; leave unknowns explicitly labeled,
not blank or disguised as facts.

- Set status to **Proposed** and the date to the actual drafting date.
- State one decision. Describe the chosen option and at least one credible
  alternative, with reasons for not choosing it. Include retaining the current
  design when it is a meaningful option.
- Separate positive consequences, costs, and risks. Describe mitigations as
  planned unless evidence shows they exist.
- In compliance constraints, distinguish verified repository constraints from
  external obligations and unverified assumptions. If no external requirements
  were supplied, say so; do not infer regulatory applicability or certification.
- Reference relevant repository evidence and authoritative external sources.
  Do not invent links, line numbers, measurements, reviewer names, or approvals.
- Describe how to validate the decision and whether each check has actually
  run. State rollback or supersession considerations, including irreversible
  effects when relevant.
- Use sanitized evidence only. Do not include secrets or private incident data.

## Return for review

Check that the filename and heading agree, all template sections remain, no
placeholder tokens remain, the status is Proposed, and material claims are
traceable. Report the draft path, assumptions, and outstanding human decisions.
Never mark a record Accepted, commit it, or publish it as part of this skill.
