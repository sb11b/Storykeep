"""Voice realtime: mint ephemeral xAI realtime client secrets.

Never log the API key or the returned token.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

XAI_REALTIME_SECRETS_URL = "https://api.x.ai/v1/realtime/client_secrets"
DEFAULT_EXPIRY_SECONDS = 300


def _require_key() -> str:
    key = (settings.xai_api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voice realtime is off until XAI_API_KEY is set on the server.",
        )
    return key


def mint_realtime_client_secret(*, expires_after_seconds: int = DEFAULT_EXPIRY_SECONDS) -> dict[str, object]:
    """POST to xAI to mint a short-lived realtime client secret.

    Returns a dict with exactly two keys:
        - "value": the client_secret.value string
        - "expires_at": the client_secret.expires_at string (ISO 8601)
    """
    key = _require_key()
    payload = {"expires_after": {"seconds": expires_after_seconds}}

    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = client.post(
                XAI_REALTIME_SECRETS_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="xAI realtime secrets service timed out.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach the xAI realtime secrets service.",
        ) from exc

    if response.status_code >= 400:
        _raise_for_realtime_error(response)

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="xAI realtime secrets returned unreadable data.",
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="xAI realtime secrets returned an unexpected response.",
        )

    # Read top-level fields first
    value = data.get("value")
    expires_at = data.get("expires_at")

    # Fall back to nested client_secret only if it is a dict
    if not isinstance(value, str) or not value or not isinstance(expires_at, int):
        nested = data.get("client_secret")
        if isinstance(nested, dict):
            if not isinstance(value, str) or not value:
                value = nested.get("value")
            if not isinstance(expires_at, int):
                expires_at = nested.get("expires_at")

    if not isinstance(value, str) or not value or not isinstance(expires_at, int):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="xAI realtime secrets returned an unexpected response.",
        )

    return {
        "value": value,
        "expires_at": expires_at,
    }


def _raise_for_realtime_error(response: httpx.Response) -> None:
    try:
        body = response.json()
    except ValueError:
        body = None

    if isinstance(body, dict):
        err = body.get("error") or body.get("detail") or body.get("message")
        if isinstance(err, dict):
            err = err.get("message") or str(err)
        if isinstance(err, str) and err.strip():
            detail = err.strip()[:240]
        else:
            detail = "xAI realtime secrets request failed."
    else:
        detail = "xAI realtime secrets request failed."

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=detail,
    )
