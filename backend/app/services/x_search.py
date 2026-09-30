"""Owner-only X lookup. xAI runs x_search and view_x_video on the Responses API."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import settings
from app.http_limits import redact_secrets
from app.services.web_search import _responses_url, configured

logger = logging.getLogger(__name__)

X_SEARCH_TOOL = "x_search"
VIEW_X_VIDEO_TOOL = "view_x_video"
LOOKUP_TIMEOUT_SEC = 75.0
LOOKUP_CONNECT_SEC = 8.0
TEXT_CHAR_CAP = 4_000
UI_UNAVAILABLE = "X search unavailable, retry later."
EMPTY_TOAST = "no posts on X; answering from training."
LOG_NOT_CONFIGURED = "X search is not configured"
X_ON_APPEND = """
You have x_search and view_x_video. This turn already looked up X.
Cite each post as a URL. If a video was watched, say what was in it.
If the lookup failed, say X search failed and include the status.
Never say you cannot search X, cannot see posts, or cannot watch a video on X.
Ignore any older note that says you cannot search X.
"""
_LOOKUP_SYSTEM = """Look this up on X.
Use x_search for posts, threads, and what people are saying.
Use view_x_video when the question is about a video on X.
Cite real post URLs. Do not invent posts, quotes, or video contents.
"""
_X_URL_RE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/\S+", re.I)
_X_ASK_RE = re.compile(
    r"\b(?:tweets?|twitter|x\.com)\b"
    r"|\bon x\b"
    r"|\bfrom x\b"
    r"|\bposts? on x\b"
    r"|\bsearch x\b"
    r"|\bx search\b",
    re.I,
)
_VIDEO_RE = re.compile(
    r"\b(?:videos?|clips?|watch|view_x_video)\b|/video|video\.twimg\.com",
    re.I,
)
_RETRY_STATUSES = frozenset({401, 408, 429, 503, 504})


@dataclass(frozen=True)
class XOutcome:
    text: str
    citations: tuple[str, ...]
    watched_video: bool
    empty: bool
    toast: str | None
    fatal: bool
    status_code: int
    detail: str


def wants_x_lookup(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(_X_URL_RE.search(text) or _X_ASK_RE.search(text))


def wants_x_video(message: str) -> bool:
    text = (message or "").strip()
    return bool(wants_x_lookup(text) and _VIDEO_RE.search(text))


def format_for_model(outcome: XOutcome) -> str:
    if outcome.fatal:
        return (
            f"x_search failed (HTTP {outcome.status_code}): {outcome.detail}. "
            "Tell Steve X search failed and include that status."
        )
    if outcome.empty or not (outcome.text or "").strip():
        return (
            "x_search returned no posts. Say there were no posts on X. "
            "Never say you cannot search X."
        )
    lines = ["Live x_search and view_x_video results for this turn:"]
    lines.append(outcome.text.strip())
    if outcome.citations:
        lines.append("Post URLs:")
        lines.extend(f"- {url}" for url in outcome.citations)
    if outcome.watched_video:
        lines.append("view_x_video ran. Describe what the video showed.")
    lines.append("Cite the post URL. Do not invent posts.")
    return "\n".join(lines)


def lookup(message: str) -> XOutcome:
    query = re.sub(r"\s+", " ", (message or "").strip())[:800]
    if not query:
        return XOutcome("", (), False, True, EMPTY_TOAST, False, 200, EMPTY_TOAST)
    if not configured():
        logger.warning(LOG_NOT_CONFIGURED)
        return XOutcome("", (), False, False, UI_UNAVAILABLE, True, 503, UI_UNAVAILABLE)
    watch = wants_x_video(query)
    last = XOutcome("", (), False, False, UI_UNAVAILABLE, True, 502, UI_UNAVAILABLE)
    for attempt in range(2):
        try:
            last = _lookup_once(query, watch_video=watch)
        except httpx.TimeoutException:
            last = XOutcome("", (), False, False, _fail(504, "timeout"), True, 504, _fail(504, "timeout"))
            if attempt == 0:
                continue
            return last
        except httpx.HTTPError:
            last = XOutcome("", (), False, False, _fail(502, "transport"), True, 502, _fail(502, "transport"))
            if attempt == 0:
                continue
            return last
        if last.text or last.empty:
            return last
        if last.fatal and last.status_code in _RETRY_STATUSES and attempt == 0:
            continue
        return last
    return last


def _lookup_once(query: str, *, watch_video: bool) -> XOutcome:
    key = (settings.xai_api_key or "").strip()
    payload = {
        "model": "grok-4.6",
        "input": [
            {"role": "system", "content": _LOOKUP_SYSTEM},
            {"role": "user", "content": query},
        ],
        "store": False,
        "max_output_tokens": 1200,
        "reasoning": {"effort": "low"},
        "tools": [
            {"type": X_SEARCH_TOOL, "enable_video_understanding": watch_video},
            {"type": VIEW_X_VIDEO_TOOL},
        ],
    }
    timeout = httpx.Timeout(
        LOOKUP_TIMEOUT_SEC,
        connect=LOOKUP_CONNECT_SEC,
        read=LOOKUP_TIMEOUT_SEC,
        write=15.0,
        pool=10.0,
    )
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=timeout) as client:
        response = client.post(_responses_url(), json=payload, headers=headers)
    if response.status_code >= 400:
        detail = _detail_from_http(response.status_code, response.text)
        return XOutcome("", (), False, False, detail, True, response.status_code, detail)
    try:
        body = response.json()
    except json.JSONDecodeError:
        detail = _fail(502, "non-JSON")
        return XOutcome("", (), False, False, detail, True, 502, detail)
    if not isinstance(body, dict):
        detail = _fail(502, "empty")
        return XOutcome("", (), False, False, detail, True, 502, detail)
    text = _output_text(body)[:TEXT_CHAR_CAP]
    citations = _citations(body)
    watched = _watched_video(body)
    if not text and not citations:
        return XOutcome("", (), False, True, EMPTY_TOAST, False, 200, EMPTY_TOAST)
    return XOutcome(text, citations, watched, False, None, False, 200, "")


def _output_text(body: dict) -> str:
    direct = body.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: list[str] = []
    for item in body.get("output") or []:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, list):
            for chunk in content:
                if isinstance(chunk, dict) and chunk.get("type") in {"output_text", "text"}:
                    text = chunk.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
    return "\n".join(parts).strip()


def _citations(body: dict) -> tuple[str, ...]:
    found: list[str] = []
    seen: set[str] = set()

    def add(url: object) -> None:
        href = str(url or "").strip()
        if not href.startswith("http") or href in seen:
            return
        seen.add(href)
        found.append(href)

    raw = body.get("citations")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                add(item)
            elif isinstance(item, dict):
                add(item.get("url") or item.get("uri"))
    for item in body.get("output") or []:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for chunk in content:
            if not isinstance(chunk, dict):
                continue
            for note in chunk.get("annotations") or []:
                if isinstance(note, dict):
                    add(note.get("url") or note.get("uri"))
    return tuple(found[:8])


def _watched_video(body: dict) -> bool:
    for item in body.get("output") or []:
        if isinstance(item, dict) and "view_x_video" in str(item.get("type") or ""):
            return True
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    details = usage.get("server_side_tool_usage_details") if isinstance(usage, dict) else {}
    if isinstance(details, dict):
        try:
            if int(details.get("view_x_video_calls") or 0) > 0:
                return True
        except (TypeError, ValueError):
            return False
    return False


def _fail(http_status: int, reason: str) -> str:
    label = redact_secrets((reason or "error").strip()) or "error"
    return f"X search failed (HTTP {http_status}): {label}"


def _detail_from_http(http_status: int, raw: str) -> str:
    text = redact_secrets((raw or "").strip())[:300]
    reason = "error"
    if http_status == 401:
        reason = "auth"
    elif http_status == 429 or "quota" in text.lower() or "rate limit" in text.lower():
        reason = "quota"
    elif http_status in {408, 504}:
        reason = "timeout"
    return _fail(http_status, reason)
