from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException, status

from app.config import settings
from app.http_limits import redact_secrets
from app.services.demo_lock import is_locked

logger = logging.getLogger(__name__)

API_ROOT = "https://api.github.com"
TIMEOUT_SEC = 25.0
STATUS_TOOL_NAME = "github_status"
DISPATCH_TOOL_NAME = "github_dispatch_workflow"
GITHUB_TOOL_NAMES = frozenset({STATUS_TOOL_NAME, DISPATCH_TOOL_NAME})

GITHUB_ON_APPEND = """
You have live GitHub ops for Storykeep's repo (Steve's ship twin — read + trigger CI, not a git client).
- **github_status**: commits, open PRs, workflow runs on sb11b/Storykeep-.
- **github_dispatch_workflow**: trigger a GitHub Actions workflow on a branch (default main) when Steve asks to run CI/build workflow — requires Actions write on the token.
- You cannot `git push` or edit files from chat; Steve pushes in Cursor, then deploy Railway or dispatch CI from here.
- Cite SHAs and workflow results from tool output only. Tokens stay server-side.
"""

GITHUB_OFF_APPEND = """
GitHub tools exist (github_status) but GITHUB_TOKEN is not set on the Storykeep Railway service yet.
Tell Steve to add a fine-grained PAT value in Railway → storykeep service → Variables — never paste secrets into chat.
Once set, call github_status when he asks about commits, PRs, or CI.
Do not say the only tool is web_search; you also have calendar/mail/chats when connected.
"""

_STATUS_RE = re.compile(
    r"\b(?:github(?:\s+repo|\s+status)?|"
    r"pull request|pull requests|\bpr\b|\bprs\b|"
    r"commit(?:s)?|branch(?:es)?|"
    r"workflow|ci(?:\s+status)?|"
    r"what(?:'s|\s+is)\s+(?:on|in)\s+github|"
    r"latest(?:\s+push|\s+commit)?|"
    r"storykeep(?:\s+repo|\s+github)|"
    r"dispatch(?:\s+workflow)?|run(?:\s+the)?\s+ci|trigger(?:\s+the)?\s+workflow|"
    r"ship(?:\s+loop|\s+it)?)\b",
    re.I,
)
_SETUP_RE = re.compile(
    r"\b(?:GITHUB_TOKEN|github\s+(?:pat|token|fine[- ]grained)|"
    r"github\s+variables?|personal access token)\b",
    re.I,
)

GITHUB_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": STATUS_TOOL_NAME,
        "description": (
            "Fetch Storykeep GitHub repo status: default branch, recent commits, open pull requests, "
            "and latest workflow runs."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}

GITHUB_DISPATCH_TOOL = {
    "type": "function",
    "function": {
        "name": DISPATCH_TOOL_NAME,
        "description": (
            "Trigger a GitHub Actions workflow on sb11b/Storykeep-. Use when Steve asks to run CI or dispatch a workflow."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "Workflow file name (e.g. deploy.yml) or workflow id",
                },
                "ref": {"type": "string", "description": "Git ref/branch to run on", "default": "main"},
            },
            "required": ["workflow_id"],
        },
    },
}

GITHUB_TOOLS = [GITHUB_STATUS_TOOL, GITHUB_DISPATCH_TOOL]


@dataclass(frozen=True)
class GitHubOutcome:
    ok: bool
    text: str
    status_code: int = 200


def _token() -> str:
    return (settings.github_token or "").strip()


def _repo() -> str:
    return (settings.github_repo or "sb11b/Storykeep-").strip().strip("/")


def configured() -> bool:
    return bool(_token())


def owner_can_use(user: object | None) -> bool:
    return configured() and not is_locked(user)


def reject_demo(user: object) -> None:
    if is_locked(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="GitHub is not enabled on this account")


def wants_github_setup(message: str) -> bool:
    return bool(_SETUP_RE.search(message or ""))


def wants_github(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(_STATUS_RE.search(text)) or wants_github_setup(text)


def is_github_tool(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    fn = item.get("function") if isinstance(item.get("function"), dict) else {}
    name = str(fn.get("name") or item.get("name") or "").strip()
    return name in GITHUB_TOOL_NAMES


def _headers() -> dict[str, str]:
    token = _token()
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _post(path: str, payload: dict[str, Any]) -> tuple[int, Any]:
    token = _token()
    if not token:
        return 503, {"message": "GitHub token not configured"}
    url = f"{API_ROOT}{path}"
    try:
        with httpx.Client(timeout=TIMEOUT_SEC) as client:
            response = client.post(url, headers=_headers(), json=payload)
    except httpx.TimeoutException:
        return 504, {"message": "GitHub API timeout"}
    except httpx.HTTPError as exc:
        return 502, {"message": f"GitHub transport error: {exc}"}
    if response.status_code == 204:
        return 204, {}
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {"message": response.text[:300]}
    return response.status_code, body


_BUGBOT_LOGINS = frozenset({"cursor[bot]", "cursor"})
_SEV_RE = re.compile(r"\*\*(Low|Medium|High|Critical)\s+Severity\*\*", re.I)
_TITLE_RE = re.compile(r"^###\s+(.+)$", re.M)
_DESC_RE = re.compile(r"<!-- DESCRIPTION START -->(.*?)<!-- DESCRIPTION END -->", re.S)
_COUNT_RE = re.compile(r"found\s+(\d+)\s+potential\s+issue", re.I)


def _bugbot_login(user: object) -> bool:
    if not isinstance(user, dict):
        return False
    return str(user.get("login") or "").strip().lower() in _BUGBOT_LOGINS


def parse_bugbot_comment(body: str) -> dict[str, str]:
    text = body or ""
    title = _TITLE_RE.search(text)
    severity = _SEV_RE.search(text)
    description = _DESC_RE.search(text)
    return {
        "title": title.group(1).strip() if title else "",
        "severity": severity.group(1).lower() if severity else "",
        "description": " ".join(description.group(1).split()) if description else "",
    }


def _resolved_comment_ids(pr_number: int) -> set[str]:
    repo = _repo()
    if "/" not in repo:
        return set()
    owner, name = repo.split("/", 1)
    query = """
    query($owner: String!, $name: String!, $number: Int!) {
      repository(owner: $owner, name: $name) {
        pullRequest(number: $number) {
          reviewThreads(first: 50) {
            nodes {
              isResolved
              comments(first: 10) { nodes { databaseId } }
            }
          }
        }
      }
    }
    """
    token = _token()
    if not token:
        return set()
    try:
        with httpx.Client(timeout=TIMEOUT_SEC) as client:
            response = client.post(
                f"{API_ROOT}/graphql",
                headers=_headers(),
                json={"query": query, "variables": {"owner": owner, "name": name, "number": pr_number}},
            )
        body = response.json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return set()
    if response.status_code >= 400 or not isinstance(body, dict):
        return set()
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    repository = data.get("repository") if isinstance(data.get("repository"), dict) else {}
    pull = repository.get("pullRequest") if isinstance(repository.get("pullRequest"), dict) else {}
    threads = pull.get("reviewThreads") if isinstance(pull.get("reviewThreads"), dict) else {}
    nodes = threads.get("nodes") if isinstance(threads.get("nodes"), list) else []
    resolved: set[str] = set()
    for thread in nodes:
        if not isinstance(thread, dict) or not thread.get("isResolved"):
            continue
        comments = thread.get("comments") if isinstance(thread.get("comments"), dict) else {}
        for comment in comments.get("nodes") or []:
            if isinstance(comment, dict) and comment.get("databaseId") is not None:
                resolved.add(str(comment["databaseId"]))
    return resolved


def bugbot_pull_review(pr_number: int) -> dict[str, Any] | None:
    """Posted Bugbot review on a pull request. None when Bugbot has not commented yet."""
    repo = _repo()
    status_code, reviews = _get(f"/repos/{repo}/pulls/{pr_number}/reviews?per_page=30")
    if status_code >= 400 or not isinstance(reviews, list):
        return None
    chosen = None
    for review in reviews:
        if not isinstance(review, dict) or not _bugbot_login(review.get("user")):
            continue
        if "BUGBOT_REVIEW" in (review.get("body") or ""):
            chosen = review
    status_code, comments = _get(f"/repos/{repo}/pulls/{pr_number}/comments?per_page=100")
    if status_code >= 400 or not isinstance(comments, list):
        comments = []
    findings: list[dict[str, Any]] = []
    for comment in comments:
        if not isinstance(comment, dict) or not _bugbot_login(comment.get("user")):
            continue
        parsed = parse_bugbot_comment(str(comment.get("body") or ""))
        if not parsed["title"]:
            continue
        line = comment.get("line") or comment.get("original_line")
        path = str(comment.get("path") or "").strip()
        findings.append(
            {
                "comment_id": str(comment.get("id") or ""),
                "resolution_status": "unresolved",
                "severity": parsed["severity"],
                "title": parsed["title"],
                "description": parsed["description"],
                "locations": [{"file": path, "start_line": line, "end_line": line}] if path else [],
            }
        )
    if chosen is None and not findings:
        return None
    summary = str((chosen or {}).get("body") or "")
    count = _COUNT_RE.search(summary)
    found = int(count.group(1)) if count else len(findings)
    resolved = _resolved_comment_ids(pr_number)
    for finding in findings:
        if finding["comment_id"] and finding["comment_id"] in resolved:
            finding["resolution_status"] = "resolved"
    return {
        "commit_sha": str((chosen or {}).get("commit_id") or ""),
        "pr_number": pr_number,
        "bugs_found": found,
        "cost_cents": None,
        "show_cost": False,
        "dry_run": False,
        "publication_status": "posted",
        "bugs": findings,
    }


def _get(path: str) -> tuple[int, Any]:
    token = _token()
    if not token:
        return 503, {"message": "GitHub token not configured"}
    url = f"{API_ROOT}{path}"
    try:
        with httpx.Client(timeout=TIMEOUT_SEC) as client:
            response = client.get(url, headers=_headers())
    except httpx.TimeoutException:
        return 504, {"message": "GitHub API timeout"}
    except httpx.HTTPError as exc:
        return 502, {"message": f"GitHub transport error: {exc}"}
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {"message": response.text[:300]}
    return response.status_code, body


def open_pull_request(*, head: str, base: str = "main", title: str, body: str = "") -> str | None:
    """Open a PR. CodeRabbit reviews it. Bugbot stays off. None when it cannot."""
    repo = _repo()
    owner = repo.split("/", 1)[0]
    head_name = (head or "").strip()
    base_name = (base or "main").strip() or "main"
    if head_name.startswith(f"{owner}:"):
        head_name = head_name.split(":", 1)[1]
    if not head_name or head_name == base_name:
        return None
    if not configured():
        return None
    status_code, payload = _post(
        f"/repos/{repo}/pulls",
        {
            "title": (title or f"Junior: {head_name}")[:240],
            "head": head_name,
            "base": base_name,
            "body": body or "Opened for review. CodeRabbit reviews this pull request. Bugbot is off.",
        },
    )
    if status_code in (200, 201) and isinstance(payload, dict):
        url = str(payload.get("html_url") or "").strip()
        if url:
            return url
    code, existing = _get(
        f"/repos/{repo}/pulls?state=open&base={quote(base_name, safe='')}&head={quote(owner + ':' + head_name, safe='')}"
    )
    if code == 200 and isinstance(existing, list):
        for item in existing:
            if isinstance(item, dict):
                url = str(item.get("html_url") or "").strip()
                if url:
                    return url
    logger.info("GitHub pull request was not opened for %s (HTTP %s)", head_name, status_code)
    return None


def _clip(text: str, limit: int = 120) -> str:
    one = " ".join((text or "").split())
    if len(one) <= limit:
        return one
    return one[: limit - 1].rstrip() + "…"


def fetch_status() -> GitHubOutcome:
    if not configured():
        return GitHubOutcome(False, GITHUB_OFF_APPEND.strip(), 503)
    repo = _repo()
    encoded = quote(repo, safe="/")
    status_code, repo_body = _get(f"/repos/{encoded}")
    if status_code >= 400:
        detail = redact_secrets(str(repo_body))[:300]
        return GitHubOutcome(False, f"GitHub repo lookup failed (HTTP {status_code}): {detail}", status_code)
    if not isinstance(repo_body, dict):
        return GitHubOutcome(False, "GitHub returned unexpected repo payload.", 502)
    default_branch = str(repo_body.get("default_branch") or "main")
    lines = [
        "GitHub status snapshot (live):",
        f"- Repo: {repo}",
        f"- Default branch: {default_branch}",
        f"- URL: {repo_body.get('html_url') or f'https://github.com/{repo}'}",
        f"- Open issues: {repo_body.get('open_issues_count')}",
    ]
    pushed = repo_body.get("pushed_at")
    if pushed:
        lines.append(f"- Last push: {pushed}")

    _, commits_body = _get(f"/repos/{encoded}/commits?per_page=5&sha={quote(default_branch, safe='')}")
    lines.append("- Recent commits:")
    if isinstance(commits_body, list) and commits_body:
        for item in commits_body[:5]:
            if not isinstance(item, dict):
                continue
            sha = str(item.get("sha") or "")[:7]
            commit = item.get("commit") if isinstance(item.get("commit"), dict) else {}
            message = _clip(str(commit.get("message") or ""))
            author = commit.get("author") if isinstance(commit.get("author"), dict) else {}
            when = author.get("date") or ""
            lines.append(f"  · {sha} {message} ({when})")
    else:
        lines.append("  · none")

    _, prs_body = _get(f"/repos/{encoded}/pulls?state=open&per_page=5")
    lines.append("- Open pull requests:")
    if isinstance(prs_body, list) and prs_body:
        for item in prs_body[:5]:
            if not isinstance(item, dict):
                continue
            number = item.get("number")
            title = _clip(str(item.get("title") or ""))
            head = item.get("head") if isinstance(item.get("head"), dict) else {}
            branch = head.get("ref") or "?"
            lines.append(f"  · #{number} {title} (head: {branch})")
    else:
        lines.append("  · none")

    _, runs_body = _get(f"/repos/{encoded}/actions/runs?per_page=3")
    lines.append("- Recent workflow runs:")
    runs = runs_body.get("workflow_runs") if isinstance(runs_body, dict) else None
    if isinstance(runs, list) and runs:
        for item in runs[:3]:
            if not isinstance(item, dict):
                continue
            name = _clip(str(item.get("name") or item.get("display_title") or "workflow"))
            conclusion = item.get("conclusion") or item.get("status") or "unknown"
            when = item.get("updated_at") or item.get("created_at") or ""
            lines.append(f"  · {name}: {conclusion} ({when})")
    else:
        lines.append("  · none")

    return GitHubOutcome(True, "\n".join(lines), 200)


def format_status_for_model(outcome: GitHubOutcome) -> str:
    prefix = "Live GitHub data for this turn:"
    if outcome.ok:
        return f"{prefix}\n{outcome.text}"
    return f"{prefix}\n{outcome.text}"


def dispatch_workflow(workflow_id: str, *, ref: str = "main") -> GitHubOutcome:
    if not configured():
        return GitHubOutcome(False, GITHUB_OFF_APPEND.strip(), 503)
    wf = (workflow_id or "").strip()
    if not wf:
        return GitHubOutcome(False, "workflow_id is required.", 400)
    branch = (ref or "main").strip() or "main"
    repo = _repo()
    encoded = quote(repo, safe="/")
    wf_encoded = quote(wf, safe="")
    status_code, body = _post(
        f"/repos/{encoded}/actions/workflows/{wf_encoded}/dispatches",
        {"ref": branch},
    )
    if status_code == 204:
        return GitHubOutcome(
            True,
            f"Dispatched workflow `{wf}` on `{branch}` for {repo}.",
            204,
        )
    detail = redact_secrets(str(body))[:300]
    return GitHubOutcome(False, f"GitHub workflow dispatch failed (HTTP {status_code}): {detail}", status_code)


def _parse_tool_args(arguments: str) -> dict[str, Any]:
    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def assemble_tool_calls(fragments: list[dict] | None) -> list[dict[str, Any]]:
    buckets: dict[int, dict[str, str]] = {}
    for item in fragments or []:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index") or 0)
        except (TypeError, ValueError):
            index = 0
        slot = buckets.setdefault(index, {"name": "", "arguments": ""})
        fn = item.get("function") if isinstance(item.get("function"), dict) else {}
        name = fn.get("name") or item.get("name")
        if isinstance(name, str) and name:
            slot["name"] = name
        args = fn.get("arguments") if isinstance(fn, dict) else item.get("arguments")
        if isinstance(args, str):
            slot["arguments"] += args
    calls: list[dict[str, Any]] = []
    for slot in buckets.values():
        name = slot.get("name") or ""
        if name not in GITHUB_TOOL_NAMES:
            continue
        calls.append({"name": name, **_parse_tool_args(slot.get("arguments") or "")})
    return calls


def assemble_tool_call(fragments: list[dict] | None) -> dict[str, Any] | None:
    calls = assemble_tool_calls(fragments)
    return calls[0] if calls else None


def execute_tool_call(call: dict[str, Any]) -> str:
    name = call.get("name")
    if name == STATUS_TOOL_NAME:
        return format_status_for_model(fetch_status())
    if name == DISPATCH_TOOL_NAME:
        outcome = dispatch_workflow(
            str(call.get("workflow_id") or ""),
            ref=str(call.get("ref") or "main"),
        )
        prefix = "GitHub workflow dispatch:"
        return f"{prefix}\n{outcome.text}"
    return "Unknown GitHub tool."
