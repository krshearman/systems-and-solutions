"""GitHub.com REST snapshots and advisory reviews; never check out PR code."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..json_data import decode_object
from .evidence import MAX_FILES, ReviewError, Snapshot, commit_sha, integer, repository_name, snapshot_from_dict
from .report import Analysis, Guidelines, finding_body, render_report


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self, repository: str, number: int, token: str):
        self.repository = repository_name(repository)
        self.number = integer(number, 1)
        if not token.strip():
            raise ReviewError("GitHub REST access requires GH_TOKEN or GITHUB_TOKEN")
        self.token = token
        self.prefix = f"/repos/{self.repository}"

    def request(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        request = Request(
            "https://api.github.com" + path,
            data=None if payload is None else json.dumps(payload).encode("utf-8"),
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "systems-and-solutions-pr-review",
            },
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=30) as response:
                raw = response.read(1_000_001)
        except HTTPError as error:
            raise ReviewError(
                f"GitHub {method} failed with HTTP {error.code}; check access and current PR state. "
                "Writes are not retried; inspect the PR before repeating a publication."
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise ReviewError(
                f"GitHub {method} failed ({type(error).__name__}); no retry was attempted. "
                "If publishing, inspect the PR before trying again."
            ) from error
        if len(raw) > 1_000_000:
            raise ReviewError("GitHub response exceeds 1000000 bytes; evidence is incomplete")
        return decode_object(raw.decode("utf-8"), "GitHub response", ReviewError)

    def metadata(self) -> tuple[str, str, int]:
        data = self.request("GET", f"{self.prefix}/pulls/{self.number}")
        if data.get("state") != "open":
            raise ReviewError("PR must be open")
        base, head = data.get("base"), data.get("head")
        if not isinstance(base, dict) or not isinstance(head, dict):
            raise ReviewError("GitHub returned incomplete PR references")
        repo = base.get("repo")
        if not isinstance(repo, dict) or repository_name(repo.get("full_name")).casefold() != self.repository.casefold():
            raise ReviewError("PR does not belong to the selected base repository")
        base_sha, head_sha = commit_sha(base.get("sha")), commit_sha(head.get("sha"))
        count = integer(data.get("changed_files"), 1)
        if count > MAX_FILES:
            raise ReviewError(f"PR exceeds {MAX_FILES} changed files")
        return base_sha, head_sha, count

    def snapshot(self) -> Snapshot:
        before = self.metadata()
        base, head, count = before
        data = self.request("GET", f"{self.prefix}/compare/{base}...{head}?per_page=1")
        files = data.get("files")
        if not isinstance(files, list) or len(files) != count:
            raise ReviewError("Compare result is missing changed files; no partial review is allowed")
        canonical = []
        for file in files:
            if not isinstance(file, dict):
                raise ReviewError("GitHub returned an invalid changed file")
            canonical.append({key: file.get(key) for key in (
                "filename", "status", "additions", "deletions", "patch", "previous_filename"
            )})
        snapshot = snapshot_from_dict({
            "repository": self.repository, "number": self.number,
            "base_sha": base, "head_sha": head, "files": canonical,
        })
        if self.metadata() != before:
            raise ReviewError("PR changed during evidence collection; collect a fresh snapshot")
        return snapshot

    def publish(
        self, snapshot: Snapshot, guidelines: Guidelines, analysis: Analysis, model: str
    ) -> int:
        if snapshot.repository.casefold() != self.repository.casefold() or snapshot.number != self.number:
            raise ReviewError("Report belongs to a different PR")
        body = render_report(snapshot, guidelines, analysis, model)
        if len(body.encode("utf-8")) > 60_000:
            raise ReviewError("Review body exceeds 60000 bytes; publication was not attempted")
        if self.snapshot().to_dict() != snapshot.to_dict():
            raise ReviewError("Report is stale or its evidence was modified; analyze the PR again")
        comments = [
            {
                "path": snapshot.line_evidence[finding.evidence][0],
                "line": snapshot.line_evidence[finding.evidence][1],
                "side": "RIGHT",
                "body": finding_body(finding),
            }
            for finding in analysis.findings if finding.confidence >= 8
        ]
        if self.metadata()[:2] != (snapshot.base_sha, snapshot.head_sha):
            raise ReviewError("PR references changed immediately before publication")
        payload: dict[str, object] = {
            "commit_id": snapshot.head_sha, "event": "COMMENT", "body": body,
        }
        if comments:
            payload["comments"] = comments
        result = self.request("POST", f"{self.prefix}/pulls/{self.number}/reviews", payload)
        identifier = result.get("id")
        if type(identifier) is not int or identifier < 1:
            raise ReviewError("GitHub returned an unexpected review response; inspect the PR before retrying")
        return identifier
