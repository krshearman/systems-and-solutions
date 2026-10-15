"""Specialist ownership and complete, non-suppressing coordinator contracts."""

from dataclasses import asdict, dataclass
import json

from ..json_data import decode_object
from ..pr_review.evidence import ReviewError, Snapshot, text
from ..pr_review.report import Analysis, Finding, Guidelines, validate_analysis

ROLES = ("architecture", "security")
PREFIXES = {"architecture": "A", "security": "S"}
PRIORITIES = ("first", "next", "later")


def validate_specialist(
    role: str, raw: str, snapshot: Snapshot, guidelines: Guidelines
) -> Analysis:
    if role not in ROLES:
        raise ReviewError("Unknown specialist role")
    analysis = validate_analysis(raw, snapshot, guidelines)
    allowed = {"architecture", "impact"} if role == "architecture" else {"security"}
    if any(finding.category not in allowed for finding in analysis.findings):
        raise ReviewError(f"{role} specialist produced a finding outside its role")
    return analysis


def finding_index(specialists: dict[str, Analysis]) -> dict[str, Finding]:
    return {
        f"{PREFIXES[role]}{index}": finding
        for role in ROLES
        for index, finding in enumerate(specialists[role].findings, 1)
    }


def source_ids(specialists: dict[str, Analysis]) -> list[str]:
    return [
        f"{PREFIXES[role]}O{index}"
        for role in ROLES
        for index in range(1, len(specialists[role].overview) + 1)
    ] + list(finding_index(specialists))


@dataclass(frozen=True)
class Summary:
    statement: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class Priority:
    finding: str
    priority: str
    reason: str


@dataclass(frozen=True)
class Disagreement:
    findings: tuple[str, ...]
    statement: str


@dataclass(frozen=True)
class Synthesis:
    summary: tuple[Summary, ...]
    priorities: tuple[Priority, ...]
    disagreements: tuple[Disagreement, ...]
    human_review_questions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def synthesis_schema(specialists: dict[str, Analysis]) -> dict[str, object]:
    findings = list(finding_index(specialists))
    string = {
        "type": "string", "minLength": 1, "maxLength": 600,
        "pattern": r"^[^\u0000-\u001f\u007f-\u009f]+$",
        "description": "One line of plain text, without newline, tab, or other control characters.",
    }

    def record(properties: dict[str, object]) -> dict[str, object]:
        return {"type": "object", "additionalProperties": False,
                "required": list(properties), "properties": properties}

    def references(values: list[str], minimum: int, maximum: int) -> dict[str, object]:
        return {"type": "array", "minItems": minimum, "maxItems": maximum,
                "items": {"type": "string", "enum": values or ["NO_FINDINGS"]}}

    return record({
        "summary": {
            "type": "array", "minItems": 1, "maxItems": 4,
            "items": record({"statement": string, "sources": references(source_ids(specialists), 1, 6)}),
        },
        "priorities": {
            "type": "array", "minItems": len(findings), "maxItems": len(findings),
            "items": record({
                "finding": {"type": "string", "enum": findings or ["NO_FINDINGS"]},
                "priority": {"type": "string", "enum": list(PRIORITIES)}, "reason": string,
            }),
        },
        "disagreements": {
            "type": "array", "minItems": 0, "maxItems": 3 if len(findings) >= 2 else 0,
            "items": record({"findings": references(findings, 2, 4), "statement": string}),
        },
        "human_review_questions": {
            "type": "array", "minItems": 1, "maxItems": 5, "items": string,
        },
    })


def validate_synthesis(raw: str, specialists: dict[str, Analysis]) -> Synthesis:
    if len(raw) > 40_000:
        raise ReviewError("Coordinator output exceeds 40000 characters")
    data = decode_object(raw, "Coordinator output", ReviewError)
    if set(data) != {"summary", "priorities", "disagreements", "human_review_questions"}:
        raise ReviewError("Coordinator output has missing or unexpected sections")
    known = finding_index(specialists)

    def items(key: str, minimum: int, maximum: int) -> list[object]:
        value = data[key]
        if not isinstance(value, list) or not minimum <= len(value) <= maximum:
            raise ReviewError(f"Coordinator section {key} has an invalid item count")
        return value

    def record(value: object, fields: set[str]) -> dict[str, object]:
        if not isinstance(value, dict) or set(value) != fields:
            raise ReviewError("Coordinator record has missing or unexpected fields")
        return value

    def references(value: object, allowed: set[str], minimum: int, maximum: int) -> tuple[str, ...]:
        if (
            not isinstance(value, list) or not minimum <= len(value) <= maximum
            or any(not isinstance(ref, str) or ref not in allowed for ref in value)
            or len(set(value)) != len(value)
        ):
            raise ReviewError("Coordinator references unknown or duplicate source IDs")
        return tuple(value)

    summaries: list[Summary] = []
    for item in items("summary", 1, 4):
        row = record(item, {"statement", "sources"})
        summaries.append(Summary(
            text(row["statement"]), references(row["sources"], set(source_ids(specialists)), 1, 6)
        ))
    priorities: list[Priority] = []
    for item in items("priorities", len(known), len(known)):
        row = record(item, {"finding", "priority", "reason"})
        identifier, priority = text(row["finding"]), text(row["priority"])
        if identifier not in known or priority not in PRIORITIES:
            raise ReviewError("Coordinator priority has an unknown finding or priority")
        severity = known[identifier].severity
        if (severity in {"high", "critical"} and priority != "first") or (
            severity == "medium" and priority == "later"
        ):
            raise ReviewError("Coordinator cannot lower review priority below source severity")
        priorities.append(Priority(identifier, priority, text(row["reason"])))
    if {row.finding for row in priorities} != set(known):
        raise ReviewError("Coordinator must retain every specialist finding exactly once")
    disagreements: list[Disagreement] = []
    seen: set[frozenset[str]] = set()
    for item in items("disagreements", 0, 3):
        row = record(item, {"findings", "statement"})
        refs = references(row["findings"], set(known), 2, 4)
        if frozenset(refs) in seen:
            raise ReviewError("Duplicate coordinator disagreement")
        seen.add(frozenset(refs))
        disagreements.append(Disagreement(refs, text(row["statement"])))
    questions = tuple(text(item) for item in items("human_review_questions", 1, 5))
    return Synthesis(tuple(summaries), tuple(priorities), tuple(disagreements), questions)
