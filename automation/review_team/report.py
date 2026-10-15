"""Keep source findings intact alongside coordinator decisions and execution trace."""

from ..pr_review.evidence import Snapshot, risk_factors, risk_score
from ..pr_review.report import Guidelines, finding_body, safe_text
from .contracts import PREFIXES, PRIORITIES, ROLES, finding_index
from .runtime import Profile, TeamResult


def render_report(
    snapshot: Snapshot, guidelines: Guidelines, result: TeamResult,
    profiles: dict[str, Profile], model: str | None,
) -> str:
    lines = [
        "# Multi-agent PR review team", "",
        "**Advisory only. Human review required. Nothing is approved or posted.**", "",
        f"- Mode: {'Live isolated SDK sessions; model: ' + safe_text(model) if model else 'Offline replay; no model sessions ran'}",
        f"- Snapshot: {snapshot.repository} PR {snapshot.number}",
        f"- Base: `{snapshot.base_sha}`; head: `{snapshot.head_sha}`",
        f"- Guidelines SHA-256: `{guidelines.sha256}`",
        f"- Deterministic change-risk score: **{risk_score(snapshot)}/100**", "",
        "Architecture and security specialists run in parallel. The coordinator starts "
        "only after both results validate, consumes those results, and retains every "
        "finding. The score is the existing metadata heuristic, not a vulnerability probability.", "",
        "## Coordinator synthesis", "",
    ]
    for item in result.coordinator.summary:
        refs = ", ".join(f"[{identifier}](#{identifier.lower()})" for identifier in item.sources)
        lines.append(f"- {safe_text(item.statement)} ({refs})")
    lines.extend(["", "## Human review order", "",
                  "| Finding | Priority | Original severity | Confidence | Coordinator rationale |",
                  "| --- | --- | --- | --- | --- |"])
    findings = finding_index(result.specialists)
    for row in sorted(result.coordinator.priorities, key=lambda row: PRIORITIES.index(row.priority)):
        finding = findings[row.finding]
        lines.append(
            f"| [{row.finding}](#{row.finding.lower()}) | {row.priority} | {finding.severity} "
            f"| {finding.confidence}/10 | {safe_text(row.reason)} |"
        )
    if not findings:
        lines.append("| None | Human review still required | N/A | N/A | No source findings supplied |")
    lines.extend(["", "## Coordinator-flagged potential disagreements", ""])
    for item in result.coordinator.disagreements:
        lines.append(f"- {', '.join(item.findings)}: {safe_text(item.statement)}")
    if not result.coordinator.disagreements:
        lines.append("None flagged. This is not proof of agreement or correctness.")
    lines.extend(["", "## Original specialist observations", ""])
    for role in ROLES:
        lines.extend([f"### {role.title()}", ""])
        prefix = PREFIXES[role]
        for index, item in enumerate(result.specialists[role].overview, 1):
            identifier = f"{prefix}O{index}"
            lines.append(
                f'<a id="{identifier.lower()}"></a>**{identifier}:** '
                f"{safe_text(item.statement)} ({', '.join(item.files)})"
            )
            lines.append("")
        for index, finding in enumerate(result.specialists[role].findings, 1):
            identifier = f"{prefix}{index}"
            path, line, content = snapshot.line_evidence[finding.evidence]
            lines.extend([
                f'<a id="{identifier.lower()}"></a>**{identifier}: {safe_text(path)}:{line}**', "",
                finding_body(finding), "", f"Changed line ({finding.evidence}): {safe_text(content)}", "",
            ])
        if not result.specialists[role].findings:
            lines.extend(["No findings supplied by this specialist; not an assurance of safety.", ""])
    lines.extend(["## Questions for the human reviewer", ""])
    lines.extend(f"- {safe_text(question)}" for question in result.coordinator.human_review_questions)
    lines.extend(["", "## Source files and risk factors", ""])
    lines.extend(
        f"- F{index}: {safe_text(file.filename)} ({file.status}, +{file.additions}/-{file.deletions})"
        for index, file in enumerate(snapshot.files, 1)
    )
    lines.extend(f"- Risk factor +{weight}: {reason}" for reason, weight in risk_factors(snapshot))
    lines.extend(["", "## Execution trace", "",
                  "| Sequence | Agent | State | Elapsed ms | Application request ID |",
                  "| --- | --- | --- | --- | --- |"])
    lines.extend(
        f"| {event.sequence} | {event.agent} | {event.state} | {event.elapsed_ms} | `{event.request_id}` |"
        for event in result.trace
    )
    lines.extend(["", "## Role provenance", ""])
    lines.extend(
        f"- {role}: {safe_text(profile.path)}; SHA-256 `{profile.sha256}`"
        for role, profile in profiles.items()
    )
    lines.extend(["", "## Boundaries", "",
                  "These are application-orchestrated SDK sessions using role-profile instruction "
                  "bodies, not native profile discovery or editor handoffs. Separate contexts are "
                  "not independent model corroboration. Trace request IDs are application-assigned, "
                  "not SDK session IDs. The JSON bundle records handoff hashes and all validated "
                  "outputs, not hidden model reasoning. Citation validity does not prove truth; "
                  "potential disagreements, review priority, and security implications need human "
                  "verification. This team has no publication or code-editing path.", ""])
    return "\n".join(lines)
