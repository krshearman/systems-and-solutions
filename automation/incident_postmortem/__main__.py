"""Generate an evidence-linked draft post-mortem from sanitized incident logs."""

import argparse
import asyncio
from pathlib import Path
import sys
from ..files import write_new_report
from ..cli import request_timeout

from .logs import IncidentError, read_evidence
from .report import render_report
from .sdk import analyze_with_copilot


def check_output(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise IncidentError("Output already exists; choose a new path")
    if not path.parent.is_dir():
        raise IncidentError("Output parent directory does not exist")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--format", required=True, choices=("text", "jsonl"))
    parser.add_argument("--output", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true", help="Evidence-only report; no model call")
    mode.add_argument("--model", help="Copilot model ID; enables SDK analysis")
    parser.add_argument(
        "--allow-model-upload", action="store_true",
        help="Confirm these logs are sanitized and approved for sending to Copilot",
    )
    parser.add_argument("--timeout", type=request_timeout, default=120.0)
    args = parser.parse_args(argv)
    if args.model is not None and (not args.model.strip() or not args.allow_model_upload):
        parser.error("--model requires a nonempty model ID and --allow-model-upload")
    if args.offline and args.allow_model_upload:
        parser.error("--allow-model-upload is only valid with --model")
    try:
        check_output(args.output)
        evidence = read_evidence(args.input, args.format)
        analysis = None
        if args.model:
            analysis = asyncio.run(
                analyze_with_copilot(evidence, args.model, args.timeout)
            )
        write_new_report(
            args.output, render_report(evidence, analysis, args.model)
        )
    except (IncidentError, OSError, UnicodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("ERROR: interrupted; report generation did not complete", file=sys.stderr)
        return 130
    print(f"Unapproved draft written to {str(args.output)!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
