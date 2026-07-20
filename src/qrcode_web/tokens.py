"""Short-lived authenticated preview tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any


def request_fingerprint(request: dict[str, Any]) -> str:
    """Create a stable fingerprint of normalized render state.

    Parameters
    ----------
    request : dict[str, Any]
        Normalized render request.

    Returns
    -------
    str
        SHA-256 hexadecimal digest.
    """
    encoded = json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def issue_token(fingerprint: str, lifetime_seconds: int = 600) -> str:
    """Issue an HMAC-authenticated render token.

    Parameters
    ----------
    fingerprint : str
        Canonical render-state fingerprint.
    lifetime_seconds : int, default=600
        Token validity lifetime.

    Returns
    -------
    str
        URL-safe opaque token.
    """
    payload = {"exp": int(time.time()) + lifetime_seconds, "fp": fingerprint}
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    secret = os.environ["QR_RENDER_TOKEN_SECRET"].encode("utf-8")
    signature = hmac.new(secret, body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(body + signature).rstrip(b"=").decode("ascii")


def verify_token(token: str, fingerprint: str) -> bool:
    """Verify a render token against a normalized request fingerprint.

    Parameters
    ----------
    token : str
        Candidate opaque token.
    fingerprint : str
        Expected request fingerprint.

    Returns
    -------
    bool
        Whether the token is authentic, current, and matches the request.
    """
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        body, signature = raw[:-32], raw[-32:]
        secret = os.environ["QR_RENDER_TOKEN_SECRET"].encode("utf-8")
        expected = hmac.new(secret, body, hashlib.sha256).digest()
        payload = json.loads(body)
    except (ValueError, json.JSONDecodeError, KeyError):
        return False
    return bool(
        hmac.compare_digest(signature, expected)
        and payload.get("fp") == fingerprint
        and isinstance(payload.get("exp"), int)
        and payload["exp"] >= time.time()
    )
