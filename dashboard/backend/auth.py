"""Optional static bearer-token auth for dashboard action endpoints and the
WebSocket. Auth is disabled when ``DASHBOARD_API_TOKEN`` is unset/empty (the lab
default), so existing behavior is unchanged unless a token is configured."""

from __future__ import annotations

import hmac

from fastapi import HTTPException


def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def verify_bearer(expected_token: str, authorization: str | None) -> None:
    """Raise HTTP 401 unless auth is disabled or the Authorization header carries
    the correct ``Bearer`` token. Never raises when ``expected_token`` is empty."""
    if not expected_token:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed bearer token")
    provided = authorization[len("Bearer ") :].strip()
    if not _constant_time_eq(provided, expected_token):
        raise HTTPException(status_code=401, detail="Invalid bearer token")


def ws_token_ok(expected_token: str, provided: str | None) -> bool:
    """Return whether a WebSocket connection is allowed. Always True when auth is
    disabled; otherwise the provided token (a query parameter) must match."""
    if not expected_token:
        return True
    return bool(provided) and _constant_time_eq(provided, expected_token)
