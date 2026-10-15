"""Check the fixed demonstration contract without executing candidate code."""

import argparse
import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "examples/refactor_guard/after.py"
WORKSPACE = ROOT / "examples/refactor_guard/workspace.py"


class RefactorPolicyError(ValueError):
    """The candidate does not match the approved demonstration structure."""


def check_source(candidate: str, approved: str) -> None:
    try:
        candidate_tree = ast.parse(candidate, type_comments=True)
    except SyntaxError as error:
        raise RefactorPolicyError(
            f"Invalid candidate syntax on line {error.lineno}: {error.msg}"
        ) from error

    approved_tree = ast.parse(approved, type_comments=True)
    if ast.dump(candidate_tree, include_attributes=False) != ast.dump(
        approved_tree, include_attributes=False
    ):
        raise RefactorPolicyError(
            "Candidate differs from the approved modernization. Only the two "
            "documented helper replacements are allowed; compare before.py "
            "and after.py. Formatting and ordinary comments are ignored."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "candidate",
        nargs="?",
        type=Path,
        default=WORKSPACE,
        help="Python file to inspect; defaults to the demo workspace",
    )
    args = parser.parse_args(argv)
    try:
        check_source(
            args.candidate.read_text(encoding="utf-8"),
            APPROVED.read_text(encoding="utf-8"),
        )
    except (OSError, UnicodeError, SyntaxError, RefactorPolicyError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print(f"PASS: {args.candidate} matches the approved modernization.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
