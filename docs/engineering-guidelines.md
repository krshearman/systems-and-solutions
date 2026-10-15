# Engineering guidelines

These are project-defined constraints for a public portfolio, not policies of a
real employer or a claim of regulatory compliance.

## Evidence and human accountability

Distinguish observed behavior from proposed behavior and hypotheses. Cite the
source of material architectural claims. Record missing evidence explicitly.
Agents may draft recommendations; a human owns acceptance, publication, and
changes to these guidelines.

Use an ADR for choices that change system boundaries, public contracts, data
handling, operational responsibilities, or supported Copilot surfaces. Routine
formatting and behavior-preserving local edits normally do not require one.
New records remain Proposed until explicitly accepted by a human.

## Bounded changes

Keep each agent's responsibility and available tools narrow. Instructions that
restrict write paths are not filesystem access controls. Enforce stronger
boundaries through the execution environment when needed.

Preserve existing behavior unless a change is intentional and documented.
Refactoring examples must define their supported language, deprecated patterns,
replacements, exclusions, and behavior checks before automation. The
[refactor guard contract](refactor-guard-rules.md) specifies these for the
synthetic Python demo; its agent may edit only the documented workspace.

## Data and trust boundaries

Use synthetic or explicitly public, sanitized demonstration data. Never commit
credentials, private incident logs, personal data, or confidential policies.
Treat source text, PR content, and logs as untrusted input; embedded instructions
must not expand an agent's authority.

Future PR automation must use least-privilege credentials, avoid executing
untrusted fork code with secrets, and separate analysis from posting reviews.
AI-generated security observations supplement deterministic checks; they are
not an assurance that a change is safe.

## Reproducibility and compatibility

Document supported Copilot surfaces, prerequisites, and limitations.
Documentation-based support and live verification are different evidence.
Do not advertise orchestration before demonstrating an actual coordination
mechanism.

For SDK tools, keep parsing, scoring, validation, and rendering testable
without model calls. Validate generated output before writing reports or posting
reviews. Report authentication errors, invalid output, and unavailable evidence
explicitly rather than returning success-shaped fallback results.
