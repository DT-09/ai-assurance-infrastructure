from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import Depends, HTTPException, Request

from .config import ENVIRONMENT, SIGNING_SECRET


ACTIVE_STATUSES = {"active", "trialing", "past_due"}
PAID_PLANS = {"growth", "enterprise"}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _ub64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_entitlement(organization_id: str, plan: str, email: str, ttl_seconds: int = 86400) -> str:
    payload = {"sub": organization_id, "plan": plan, "email": email.lower().strip(), "iat": int(time.time()), "exp": int(time.time()) + ttl_seconds, "scope": "paid_workspace"}
    body = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    sig = hmac.new(SIGNING_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"aai_ent_{body}.{sig}"


def verify_entitlement(token: str) -> dict[str, Any] | None:
    if not token.startswith("aai_ent_") or "." not in token:
        return None
    raw = token[len("aai_ent_"):]
    body, sig = raw.rsplit(".", 1)
    expected = hmac.new(SIGNING_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig): return None
    try: payload = json.loads(_ub64(body))
    except Exception: return None
    if payload.get("scope") != "paid_workspace" or int(payload.get("exp", 0)) <= int(time.time()): return None
    return payload


def paid_identity(request: Request) -> dict[str, Any]:
    if ENVIRONMENT == "development" and os.getenv("AAI_DEV_BYPASS_PAID", "true").lower() == "true":
        return {"organization_id":"org_local","plan":"enterprise","scopes":["control:read","control:write","admin:keys","admin:identity","paid:workspace"],"paid_bypass":True}
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        payload = verify_entitlement(auth[7:].strip())
        if payload:
            return {"organization_id":payload["sub"],"plan":payload["plan"],"scopes":["control:read","control:write","admin:keys","admin:identity","paid:workspace"],"entitlement":payload}
    raise HTTPException(status_code=402, detail={"code":"paid_workspace_required","message":"Active Growth or Enterprise entitlement required.","upgrade":"/pricing.html"})


def require_paid():
    return Depends(paid_identity)
