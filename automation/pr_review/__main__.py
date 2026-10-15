"""Analyze a bounded PR snapshot; publish only with a separate explicit command."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from ..files import write_new_report
from ..sdk import SdkError, request_analysis
from ..cli import request_timeout
from .evidence import ReviewError, snapshot_from_dict, text
from .input import GUIDELINES, github_client, read_object
from .report import (
    SYSTEM_PROMPT, analysis_schema, model_prompt, read_guidelines,
    render_report, validate_analysis,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze")
    source = analyze.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixture", type=Path, help="Local snapshot; publication still requires live evidence")
    source.add_argument("--repo", help="GitHub.com owner/name; requires --pr")
    analyze.add_argument("--pr", type=int)
    mode = analyze.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--model")
    analyze.add_argument("--allow-model-upload", action="store_true")
    analyze.add_argument("--timeout", type=request_timeout, default=120.0)
    analyze.add_argument("--output", required=True, type=Path, help="New .json bundle; a sibling .md is also written")
    publish = commands.add_parser("publish")
    publish.add_argument("--input", required=True, type=Path)
    publish.add_argument("--repo", required=True)
    publish.add_argument("--pr", required=True, type=int)
    publish.add_argument("--confirm-post", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "analyze":
        if (args.repo is not None) != (args.pr is not None):
            parser.error("--repo and --pr must be supplied together")
        if args.model is not None and (not args.model.strip() or not args.allow_model_upload):
            parser.error("--model requires a nonempty model ID and --allow-model-upload")
        if args.offline and args.allow_model_upload:
            parser.error("--allow-model-upload requires --model")
    elif not args.confirm_post:
        parser.error("Publishing requires --confirm-post after reviewing the report")
    try:
        guidelines = read_guidelines(GUIDELINES)
        if args.command == "analyze":
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
            model = text(args.model, 200) if args.model is not None else None
            analysis = None
            if model:
                raw = asyncio.run(request_analysis(
                    model_prompt(snapshot, guidelines), SYSTEM_PROMPT,
                    analysis_schema(snapshot, guidelines), model, args.timeout,
                    token=os.environ.get("COPILOT_GITHUB_TOKEN") or None,
                ))
                analysis = validate_analysis(raw, snapshot, guidelines)
            report = render_report(snapshot, guidelines, analysis, model)
            bundle = {
                "version": 1, "snapshot": snapshot.to_dict(),
                "guidelines_sha256": guidelines.sha256, "model": model,
                "analysis": analysis.to_dict() if analysis else None,
            }
            write_new_report(markdown, report)
            write_new_report(args.output, json.dumps(bundle, indent=2) + "\n")
            print(f"Advisory report written to {str(markdown)!r}; nothing was posted")
        else:
            bundle = read_object(args.input)
            if set(bundle) != {"version", "snapshot", "guidelines_sha256", "model", "analysis"} or type(bundle["version"]) is not int or bundle["version"] != 1:
                raise ReviewError("Invalid or unsupported report bundle")
            if bundle["guidelines_sha256"] != guidelines.sha256:
                raise ReviewError("Guidelines changed; regenerate the report before posting")
            data = bundle["snapshot"]
            if not isinstance(data, dict):
                raise ReviewError("Missing snapshot in report bundle")
            snapshot = snapshot_from_dict(data)
            if bundle["model"] is None or bundle["analysis"] is None:
                raise ReviewError("Offline evidence-only reports cannot be published as model reviews")
            model = text(bundle["model"], 200)
            analysis = validate_analysis(json.dumps(bundle["analysis"]), snapshot, guidelines)
            identifier = github_client(args.repo, args.pr).publish(snapshot, guidelines, analysis, model)
            print(f"Posted advisory COMMENT review {identifier}; no approval was submitted")
    except (ReviewError, SdkError, OSError, UnicodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("ERROR: interrupted; inspect the PR before repeating publication", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
