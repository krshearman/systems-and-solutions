"""Run parallel PR specialists and a coordinator; report only, never publish."""

import argparse
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from ..cli import request_timeout
from ..files import write_new_report
from ..pr_review.evidence import ReviewError, snapshot_from_dict, text
from ..pr_review.input import GUIDELINES, github_client, read_object
from ..pr_review.report import read_guidelines
from ..sdk import SdkError
from .report import render_report
from .runtime import PROFILE_NAMES, AgentCall, Profile, read_profiles, run_team, sdk_runner


def replay_runner(path: Path) -> AgentCall:
    data = read_object(path)
    if set(data) != set(PROFILE_NAMES):
        raise ReviewError("Replay requires exactly architecture, security, and coordinator outputs")
    by_name = {name: role for role, name in PROFILE_NAMES.items()}

    async def run(profile: Profile, _prompt: str, _schema: dict[str, object]) -> str:
        await asyncio.sleep(0)
        return json.dumps(data[by_name[profile.name]])
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixture", type=Path)
    source.add_argument("--repo")
    parser.add_argument("--pr", type=int)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--replay", type=Path, help="Simulated outputs; requires --fixture; no model calls")
    mode.add_argument("--model", help="Same model for three separate SDK requests, two concurrent")
    parser.add_argument("--allow-model-upload", action="store_true")
    parser.add_argument("--timeout", type=request_timeout, default=120.0, help="Per-request deadline in seconds")
    parser.add_argument("--output", required=True, type=Path, help="New .json bundle and sibling .md")
    args = parser.parse_args(argv)
    if (args.repo is not None) != (args.pr is not None):
        parser.error("--repo and --pr must be supplied together")
    if args.replay and (not args.fixture or args.allow_model_upload):
        parser.error("--replay requires --fixture and cannot enable model upload")
    if args.model is not None and (not args.model.strip() or not args.allow_model_upload):
        parser.error("--model requires a nonempty model ID and --allow-model-upload")
    try:
        if args.output.suffix != ".json":
            raise ReviewError("Output must have a .json suffix")
        markdown = args.output.with_suffix(".md")
        for path in (args.output, markdown):
            if path.exists() or path.is_symlink() or not path.parent.is_dir():
                raise ReviewError("Output paths must be new and their directory must already exist")
        snapshot = (
            snapshot_from_dict(read_object(args.fixture)) if args.fixture
            else github_client(args.repo, args.pr).snapshot()
        )
        guidelines = read_guidelines(GUIDELINES)
        profiles = read_profiles()
        model = text(args.model, 200) if args.model is not None else None
        runner = (
            sdk_runner(model, args.timeout, os.environ.get("COPILOT_GITHUB_TOKEN") or None)
            if model is not None else replay_runner(args.replay)
        )
        result = asyncio.run(run_team(snapshot, guidelines, profiles, runner))
        bundle = {
            "version": 1, "mode": "sdk" if model else "replay", "model": model,
            "snapshot": snapshot.to_dict(), "guidelines_sha256": guidelines.sha256,
            "profiles": {
                role: {"name": profile.name, "path": profile.path, "sha256": profile.sha256}
                for role, profile in profiles.items()
            },
            "specialists": {
                role: analysis.to_dict() for role, analysis in result.specialists.items()
            },
            "coordinator": result.coordinator.to_dict(),
            "trace": [asdict(event) for event in result.trace],
        }
        report = render_report(snapshot, guidelines, result, profiles, model)
        write_new_report(markdown, report)
        write_new_report(args.output, json.dumps(bundle, indent=2) + "\n")
        print(f"Advisory team report written to {str(markdown)!r}; nothing was posted")
    except (ReviewError, SdkError, OSError, UnicodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("ERROR: interrupted; no complete team report was generated", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
