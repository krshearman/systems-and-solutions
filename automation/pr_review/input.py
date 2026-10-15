"""Shared bounded snapshot inputs for the single-agent and team applications."""

import os
from pathlib import Path

from ..json_data import decode_object
from .evidence import ReviewError
from .github import GitHub

ROOT = Path(__file__).resolve().parents[2]
GUIDELINES = ROOT / "docs/engineering-guidelines.md"


def read_object(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ReviewError("Input must be a readable regular JSON file")
    with path.open("rb") as stream:
        raw = stream.read(256_001)
    if len(raw) > 256_000:
        raise ReviewError("Input JSON exceeds 256000 bytes")
    return decode_object(raw.decode("utf-8"), "Input", ReviewError)


def github_client(repo: str, number: int) -> GitHub:
    return GitHub(repo, number, os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", ""))
