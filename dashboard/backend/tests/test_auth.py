"""Bearer-token auth helpers (WP4)."""

import pytest
from auth import verify_bearer, ws_token_ok
from fastapi import HTTPException


def test_disabled_allows_everything():
    # Empty expected token => auth disabled => never raises, always ok.
    verify_bearer("", None)
    verify_bearer("", "Bearer whatever")
    assert ws_token_ok("", None) is True
    assert ws_token_ok("", "anything") is True


def test_correct_token_passes():
    verify_bearer("s3cret", "Bearer s3cret")
    assert ws_token_ok("s3cret", "s3cret") is True


def test_missing_header_rejected():
    with pytest.raises(HTTPException) as exc:
        verify_bearer("s3cret", None)
    assert exc.value.status_code == 401


def test_malformed_header_rejected():
    with pytest.raises(HTTPException) as exc:
        verify_bearer("s3cret", "s3cret")  # missing "Bearer " prefix
    assert exc.value.status_code == 401


def test_wrong_token_rejected():
    with pytest.raises(HTTPException) as exc:
        verify_bearer("s3cret", "Bearer nope")
    assert exc.value.status_code == 401
    assert ws_token_ok("s3cret", "nope") is False
    assert ws_token_ok("s3cret", None) is False
