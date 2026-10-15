"""A fixed two-specialist fan-out/fan-in graph with fail-closed handoffs."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from ..pr_review.evidence import ReviewError, Snapshot
from ..pr_review.report import (
    Analysis, Guidelines, SYSTEM_PROMPT, analysis_schema, model_prompt,
)
from ..sdk import SdkError, request_analysis
from .contracts import (
    PREFIXES, ROLES, Synthesis, finding_index, synthesis_schema,
    validate_specialist, validate_synthesis,
)

ROOT = Path(__file__).resolve().parents[2]
PROFILE_NAMES = {
    "architecture": "pr-architecture-reviewer",
    "security": "pr-security-reviewer",
    "coordinator": "pr-review-coordinator",
}


@dataclass(frozen=True)
class Profile:
    name: str
    path: str
    instructions: str
    sha256: str


def read_profiles() -> dict[str, Profile]:
    profiles: dict[str, Profile] = {}
    for role, name in PROFILE_NAMES.items():
        relative = f".github/agents/{name}.agent.md"
        with (ROOT / relative).open("rb") as stream:
            raw = stream.read(12_001)
        if len(raw) > 12_000:
            raise ReviewError(f"Role profile {name} exceeds 12000 bytes")
        content = raw.decode("utf-8")
        parts = content.split("\n---\n", 1)
        if not content.startswith("---\n") or len(parts) != 2 or not parts[1].strip():
            raise ReviewError(f"Role profile {name} requires frontmatter and an instruction body")
        instructions = parts[1].strip()
        if role in ROLES:
            instructions = SYSTEM_PROMPT + "\n\n" + instructions
        profiles[role] = Profile(name, relative, instructions, hashlib.sha256(raw).hexdigest())
    return profiles


AgentCall = Callable[[Profile, str, dict[str, object]], Awaitable[str]]


def sdk_runner(model: str, timeout: float, token: str | None) -> AgentCall:
    async def run(profile: Profile, prompt: str, schema: dict[str, object]) -> str:
        return await request_analysis(prompt, profile.instructions, schema, model, timeout, token)
    return run


def digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def coordinator_prompt(
    snapshot: Snapshot, guidelines: Guidelines, specialists: dict[str, Analysis]
) -> str:
    results = {}
    for role in ROLES:
        prefix = PREFIXES[role]
        analysis = specialists[role]
        results[role] = {
            "overview": [{"id": f"{prefix}O{index}", **asdict(item)}
                         for index, item in enumerate(analysis.overview, 1)],
            "findings": [{"id": f"{prefix}{index}", **asdict(item)}
                         for index, item in enumerate(analysis.findings, 1)],
        }
    cited = {finding.evidence for finding in finding_index(specialists).values()}
    prompt = json.dumps({
        "trusted_guidelines": {"content": guidelines.content, "sections": guidelines.sections},
        "snapshot": {"repository": snapshot.repository, "number": snapshot.number,
                     "base_sha": snapshot.base_sha, "head_sha": snapshot.head_sha},
        "untrusted_specialist_results": results,
        "cited_source_lines": {
            key: {"path": path, "line": line, "content": content}
            for key, (path, line, content) in snapshot.line_evidence.items() if key in cited
        },
    }, ensure_ascii=True)
    if len(prompt) > 100_000:
        raise ReviewError("Coordinator handoff exceeds 100000 characters")
    return prompt


@dataclass(frozen=True)
class Event:
    sequence: int
    agent: str
    state: str
    request_id: str
    elapsed_ms: int
    input_sha256: str
    output_sha256: str | None


@dataclass(frozen=True)
class TeamResult:
    specialists: dict[str, Analysis]
    coordinator: Synthesis
    trace: tuple[Event, ...]


async def run_team(
    snapshot: Snapshot, guidelines: Guidelines, profiles: dict[str, Profile], runner: AgentCall
) -> TeamResult:
    if set(profiles) != {*ROLES, "coordinator"}:
        raise ReviewError("Review team requires exactly two specialist profiles and a coordinator")
    started = perf_counter()
    trace: list[Event] = []
    request_ids = {role: uuid4().hex for role in profiles}
    prompt = model_prompt(snapshot, guidelines)

    def emit(role: str, state: str, content: str, output: str | None = None) -> None:
        trace.append(Event(
            len(trace) + 1, role, state, request_ids[role],
            round((perf_counter() - started) * 1000), digest(content),
            digest(output) if output is not None else None,
        ))

    async def specialist(role: str) -> Analysis:
        emit(role, "started", prompt)
        try:
            categories = ("architecture", "impact") if role == "architecture" else ("security",)
            raw = await runner(
                profiles[role], prompt, analysis_schema(snapshot, guidelines, categories=categories)
            )
            analysis = validate_specialist(role, raw, snapshot, guidelines)
        except asyncio.CancelledError:
            emit(role, "cancelled", prompt)
            raise
        except (ReviewError, SdkError) as error:
            emit(role, "failed", prompt)
            raise ReviewError(f"{role} specialist failed: {error}") from error
        emit(role, "validated", prompt, json.dumps(analysis.to_dict(), sort_keys=True))
        return analysis

    tasks: dict[str, asyncio.Task[Analysis]] = {}
    try:
        async with asyncio.TaskGroup() as group:
            for role in ROLES:
                emit(role, "scheduled", prompt)
                tasks[role] = group.create_task(specialist(role), name=profiles[role].name)
    except* (ReviewError, SdkError) as failures:
        raise ReviewError(
            "Specialist stage failed; coordinator was not invoked. "
            + "; ".join(str(error) for error in failures.exceptions)
        ) from failures
    specialists = {role: tasks[role].result() for role in ROLES}
    handoff = coordinator_prompt(snapshot, guidelines, specialists)
    emit("coordinator", "scheduled", handoff)
    emit("coordinator", "started", handoff)
    try:
        raw = await runner(profiles["coordinator"], handoff, synthesis_schema(specialists))
        synthesis = validate_synthesis(raw, specialists)
    except asyncio.CancelledError:
        emit("coordinator", "cancelled", handoff)
        raise
    except (ReviewError, SdkError) as error:
        emit("coordinator", "failed", handoff)
        raise ReviewError(f"Coordinator stage failed; no team report was generated: {error}") from error
    emit("coordinator", "validated", handoff, json.dumps(synthesis.to_dict(), sort_keys=True))
    return TeamResult(specialists, synthesis, tuple(trace))
