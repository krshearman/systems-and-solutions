"""Validate complete unified patches before assigning changed-line evidence."""

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
import re

MAX_FILES = 25
MAX_PATCH = 50_000
MAX_ADDED_LINES = 1000
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SHA = re.compile(r"[0-9a-f]{40}")
HUNK = re.compile(r"@@ -([0-9]{1,9})(?:,([0-9]{1,9}))? \+([0-9]{1,9})(?:,([0-9]{1,9}))? @@.*")


class ReviewError(ValueError):
    """Unavailable evidence, invalid output, or unsafe review configuration."""


def integer(value: object, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ReviewError(f"Expected an integer greater than or equal to {minimum}")
    return value


def commit_sha(value: object) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ReviewError("Expected a full lowercase commit SHA")
    return value


def text(value: object, maximum: int = 600) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ReviewError(f"Expected nonempty text of at most {maximum} characters")
    if any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value):
        raise ReviewError("Text contains unsupported control characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ReviewError("Text contains invalid Unicode") from error
    return value


def repository_name(value: object) -> str:
    name = text(value, 200)
    if not REPOSITORY.fullmatch(name) or any(part in {".", ".."} for part in name.split("/")):
        raise ReviewError("Repository must be a GitHub.com owner/name")
    return name.lower()


def file_path(value: object) -> str:
    name = text(value, 512)
    if name.startswith("/") or "\\" in name or any(
        part in {"", ".", ".."} for part in name.split("/")
    ):
        raise ReviewError("Expected a relative repository path without traversal")
    return name


def added_lines(patch: str, additions: int, deletions: int) -> dict[int, str]:
    lines = patch.split("\n")
    if lines[-1] == "":
        lines.pop()
    added: dict[int, str] = {}
    deleted = 0
    old_end = new_end = 0
    index = 0
    while index < len(lines):
        match = HUNK.fullmatch(lines[index])
        if match is None:
            raise ReviewError("Missing or invalid unified-diff hunk header")
        old, old_count, new, new_count = (
            int(value) if value is not None else 1 for value in match.groups()
        )
        if (old_count and old < 1) or (new_count and new < 1) or old < old_end or new < new_end:
            raise ReviewError("Invalid or overlapping unified-diff ranges")
        old_end, new_end = old + old_count, new + new_count
        seen_old = seen_new = 0
        index += 1
        while index < len(lines) and not lines[index].startswith("@@"):
            line = lines[index]
            index += 1
            if line == "\\ No newline at end of file":
                continue
            if not line or line[0] not in " +-":
                raise ReviewError("Invalid unified-diff content")
            if line[0] == "+":
                added[new + seen_new] = line[1:]
            if line[0] == "-":
                deleted += 1
            seen_old += line[0] in " -"
            seen_new += line[0] in " +"
        if (seen_old, seen_new) != (old_count, new_count):
            raise ReviewError("Incomplete patch; hunk counts do not match")
    if len(added) != additions or deleted != deletions:
        raise ReviewError("Incomplete patch; additions/deletions do not match")
    return added


@dataclass(frozen=True)
class ChangedFile:
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str
    previous_filename: str | None

    @property
    def added(self) -> dict[int, str]:
        return added_lines(self.patch, self.additions, self.deletions)


@dataclass(frozen=True)
class Snapshot:
    repository: str
    number: int
    base_sha: str
    head_sha: str
    files: tuple[ChangedFile, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "repository": self.repository, "number": self.number,
            "base_sha": self.base_sha, "head_sha": self.head_sha,
            "files": [asdict(file) for file in self.files],
        }

    @property
    def line_evidence(self) -> dict[str, tuple[str, int, str]]:
        return {
            f"F{index}:L{line}": (file.filename, line, content)
            for index, file in enumerate(self.files, 1)
            for line, content in file.added.items()
        }


def snapshot_from_dict(data: dict[str, object]) -> Snapshot:
    if set(data) != {"repository", "number", "base_sha", "head_sha", "files"}:
        raise ReviewError("Snapshot has missing or unexpected fields")
    repository = repository_name(data["repository"])
    number = integer(data["number"], 1)
    base_sha, head_sha = commit_sha(data["base_sha"]), commit_sha(data["head_sha"])
    items = data["files"]
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_FILES:
        raise ReviewError(f"PR must contain 1 to {MAX_FILES} changed files")
    files: list[ChangedFile] = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {
            "filename", "status", "additions", "deletions", "patch", "previous_filename"
        }:
            raise ReviewError("Changed file has missing or unexpected fields")
        name = file_path(item["filename"])
        status = item["status"]
        if not isinstance(status, str) or status not in ("added", "modified", "removed", "renamed"):
            raise ReviewError("Unsupported change status")
        previous = item["previous_filename"]
        if status == "renamed":
            previous = file_path(previous)
        elif previous is not None:
            raise ReviewError("Only renamed files may specify a previous path")
        patch = item["patch"]
        if not isinstance(patch, str):
            raise ReviewError("Missing textual patch; binary or unavailable diffs are unsupported")
        try:
            patch.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ReviewError("Patch contains invalid Unicode") from error
        file = ChangedFile(
            name, status, integer(item["additions"]), integer(item["deletions"]), patch, previous
        )
        file.added
        files.append(file)
    if len({file.filename for file in files}) != len(files):
        raise ReviewError("Duplicate changed-file path")
    if sum(len(file.patch) for file in files) > MAX_PATCH:
        raise ReviewError(f"Combined patches exceed {MAX_PATCH} characters; nothing was truncated")
    if sum(file.additions for file in files) > MAX_ADDED_LINES:
        raise ReviewError(f"PR exceeds {MAX_ADDED_LINES} added lines")
    return Snapshot(repository, number, base_sha, head_sha, tuple(files))


def risk_factors(snapshot: Snapshot) -> list[tuple[str, int]]:
    paths = [
        path.lower() for file in snapshot.files
        for path in (file.filename, file.previous_filename) if path is not None
    ]
    names = [PurePosixPath(path).name for path in paths]
    factors: list[tuple[str, int]] = []
    if any(path.startswith(".github/workflows/") for path in paths):
        factors.append(("Workflow/credential execution boundary", 25))
    dependencies = {"pyproject.toml", "poetry.lock", "uv.lock", "package.json", "package-lock.json",
                    "yarn.lock", "pnpm-lock.yaml", "go.mod", "go.sum", "cargo.toml", "cargo.lock"}
    if any(name in dependencies or name.startswith("requirements") for name in names):
        factors.append(("Dependency manifest or lockfile", 20))
    if any(re.search(r"(^|[/_.-])(auth|authentication|authorization|permissions?|security|secrets?|tokens?)([/_.-]|$)", path) for path in paths):
        factors.append(("Authentication/security-named path", 25))
    if any(path.startswith(("infra/", "terraform/", "deploy/")) or path.endswith((".tf", ".bicep")) for path in paths):
        factors.append(("Infrastructure or deployment path", 15))
    changed = sum(file.additions + file.deletions for file in snapshot.files)
    if changed > 400:
        factors.append(("More than 400 changed lines", 20))
    elif changed > 100:
        factors.append(("More than 100 changed lines", 10))
    if len(snapshot.files) > 10:
        factors.append(("More than 10 changed files", 10))
    def tests(path: str) -> bool:
        return (
            path.startswith("tests/") or "/tests/" in path
            or PurePosixPath(path).name.startswith("test_")
            or ".test." in path or ".spec." in path
        )
    code = {".py", ".js", ".ts", ".tsx", ".cs", ".go", ".java", ".rb", ".rs", ".c", ".cpp", ".sh"}
    if any(PurePosixPath(path).suffix in code and not tests(path) for path in paths) and not any(tests(path) for path in paths):
        factors.append(("Code changed without a test-named file in the diff", 10))
    return factors


def risk_score(snapshot: Snapshot) -> int:
    return min(100, sum(weight for _, weight in risk_factors(snapshot)))
