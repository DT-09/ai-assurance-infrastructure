from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from .billing import BillingStore, PLANS, StripeBilling
from .control_plane.identity import IdentityStore

router = APIRouter(prefix="/v1/billing", tags=["Billing"])


class CheckoutRequest(BaseModel):
    plan: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=3, max_length=320)


def _billing(request: Request) -> BillingStore:
    return request.app.state.billing_store


def _stripe(request: Request) -> StripeBilling:
    return request.app.state.stripe_billing


def require_identity(request: Request, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> str:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    organization_id = request.app.state.identity_store.authenticate(x_api_key)
    if organization_id is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    return organization_id


@router.get("/plans")
def plans():
    return {
        "currency": "USD",
        "plans": [
            {
                "key": plan.key,
                "name": plan.name,
                "description": plan.description,
                "monthly_usd": plan.monthly_usd,
                "max_assets": plan.max_assets,
                "max_evaluations_month": plan.max_evaluations_month,
                "features": list(plan.features),
            }
            for plan in PLANS.values()
        ],
    }


@router.get("/account")
def account(request: Request, organization_id: str = Depends(require_identity)):
    store = _billing(request)
    account = store.get_account(organization_id)
    usage = store.usage(organization_id)
    plan = PLANS.get(account["plan"], PLANS["developer"])
    return {"account": account, "usage": usage, "plan": {
        "key": plan.key, "name": plan.name, "max_assets": plan.max_assets,
        "max_evaluations_month": plan.max_evaluations_month,
    }}


@router.post("/checkout")
def checkout(payload: CheckoutRequest, request: Request, organization_id: str = Depends(require_identity)):
    plan = PLANS.get(payload.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan")
    try:
        result = _stripe(request).create_checkout(organization_id, payload.email, payload.plan)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return result


@router.post("/webhook")
async def webhook(request: Request, stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature")):
    payload = await request.body()
    if not stripe_signature or not _stripe(request).verify_webhook(payload, stripe_signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    try:
        event = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    return _stripe(request).handle_webhook(event)


@router.get("/health")
def billing_health(request: Request):
    return {"status": "ok", "stripe_configured": _stripe(request).configured}
