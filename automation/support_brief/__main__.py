"""Draft a support-to-engineering brief; never create or publish an issue."""

import argparse
import asyncio
from pathlib import Path
import sys

from ..cli import request_timeout
from ..files import write_new_report
from ..sdk import SdkError, request_analysis
from .evidence import BriefError, read_evidence
from .report import SYSTEM_PROMPT, analysis_schema, model_prompt, render_report, validate_analysis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--model", help="Copilot model ID; enables an SDK call")
    parser.add_argument("--allow-model-upload", action="store_true")
    parser.add_argument("--timeout", type=request_timeout, default=120.0)
    args = parser.parse_args(argv)
    if args.model is not None and (not args.model.strip() or not args.allow_model_upload):
        parser.error("--model requires a nonempty model ID and --allow-model-upload")
    if args.offline and args.allow_model_upload:
        parser.error("--allow-model-upload is only valid with --model")
    try:
        if args.output.exists() or args.output.is_symlink():
            raise BriefError("Output already exists; choose a new path")
        if not args.output.parent.is_dir():
            raise BriefError("Output parent directory does not exist")
        evidence = read_evidence(args.input)
        analysis = None
        if args.model:
            raw = asyncio.run(request_analysis(
                model_prompt(evidence), SYSTEM_PROMPT, analysis_schema(evidence),
                args.model, args.timeout,
            ))
            analysis = validate_analysis(raw, evidence)
        write_new_report(args.output, render_report(evidence, analysis, args.model))
    except (BriefError, SdkError, OSError, UnicodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("ERROR: interrupted; brief generation did not complete", file=sys.stderr)
        return 130
    print(f"Unapproved brief written to {str(args.output)!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
