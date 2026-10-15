"""Summarize synthetic incident records without changing their input stream."""

from collections.abc import Iterable

from examples.refactor_guard.legacy_api import normalize_level, parse_line


def summarize(lines: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in lines:
        if not line.strip():
            continue
        _, severity, _ = parse_line(line)
        normalized = normalize_level(severity)
        counts[normalized] = counts.get(normalized, 0) + 1
    return counts
