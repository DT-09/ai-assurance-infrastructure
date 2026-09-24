from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .database import connect_database

STRIPE_API = "https://api.stripe.com/v1"


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    description: str
    monthly_usd: int | None
    price_env: str | None
    max_assets: int | None
    max_evaluations_month: int | None
    features: tuple[str, ...]


PLANS: dict[str, Plan] = {
    "developer": Plan(
        "developer", "Developer", "Public protocol and local verification.", 0, None,
        3, 100, ("Protocol v1", "CLI", "Passport verification", "3 registered assets"),
    ),
    "production": Plan(
        "production", "Production Assurance Sprint", "One production AI workflow assessed, controlled and evidenced.", 10000, "STRIPE_PRICE_PRODUCTION",
        25, 5000, (
            "AI estate discovery", "agent identity + authority mapping", "production trace ingestion",
            "adversarial assurance", "policy/risk decisioning", "runtime authorization",
            "human approval gates", "evidence + tamper verification", "release/deployment gate",
            "change-impact reassessment", "incident + remediation workflow", "assurance passport",
            "implementation handoff", "30-day assurance history",
        ),
    ),
}



def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BillingStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._initialize()

    def _initialize(self) -> None:
        with connect_database(self.db_path) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS billing_accounts (
                    organization_id TEXT PRIMARY KEY,
                    plan TEXT NOT NULL DEFAULT 'developer',
                    status TEXT NOT NULL DEFAULT 'active',
                    customer_id TEXT,
                    subscription_id TEXT,
                    checkout_session_id TEXT,
                    current_period_end TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS billing_usage (
                    organization_id TEXT NOT NULL,
                    period TEXT NOT NULL,
                    evaluations INTEGER NOT NULL DEFAULT 0,
                    assets_created INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (organization_id, period)
                )
                """
            )

    def ensure_account(self, organization_id: str) -> dict[str, Any]:
        with connect_database(self.db_path) as db:
            row = db.execute(
                "SELECT * FROM billing_accounts WHERE organization_id = ?", (organization_id,)
            ).fetchone()
            if row:
                return dict(row)
            now = _now()
            db.execute(
                """INSERT INTO billing_accounts
                (organization_id, plan, status, created_at, updated_at)
                VALUES (?, 'developer', 'active', ?, ?)""",
                (organization_id, now, now),
            )
            row = db.execute(
                "SELECT * FROM billing_accounts WHERE organization_id = ?", (organization_id,)
            ).fetchone()
            return dict(row)

    def get_account(self, organization_id: str) -> dict[str, Any]:
        return self.ensure_account(organization_id)

    def update(self, organization_id: str, **fields: Any) -> dict[str, Any]:
        allowed = {
            "plan", "status", "customer_id", "subscription_id",
            "checkout_session_id", "current_period_end",
        }
        fields = {k: v for k, v in fields.items() if k in allowed}
        if not fields:
            return self.get_account(organization_id)
        fields["updated_at"] = _now()
        with connect_database(self.db_path) as db:
            self.ensure_account(organization_id)
            assignments = ", ".join(f"{key} = ?" for key in fields)
            values = list(fields.values()) + [organization_id]
            db.execute(
                f"UPDATE billing_accounts SET {assignments} WHERE organization_id = ?",
                values,
            )
        return self.get_account(organization_id)

    def increment_usage(self, organization_id: str, metric: str, amount: int = 1) -> dict[str, Any]:
        if metric not in {"evaluations", "assets_created"}:
            raise ValueError("Unsupported usage metric")
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        with connect_database(self.db_path) as db:
            db.execute(
                "INSERT OR IGNORE INTO billing_usage(organization_id, period) VALUES (?, ?)",
                (organization_id, period),
            )
            db.execute(
                f"UPDATE billing_usage SET {metric} = {metric} + ? WHERE organization_id = ? AND period = ?",
                (amount, organization_id, period),
            )
            row = db.execute(
                "SELECT * FROM billing_usage WHERE organization_id = ? AND period = ?",
                (organization_id, period),
            ).fetchone()
        return dict(row)

    def usage(self, organization_id: str) -> dict[str, Any]:
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        with connect_database(self.db_path) as db:
            row = db.execute(
                "SELECT * FROM billing_usage WHERE organization_id = ? AND period = ?",
                (organization_id, period),
            ).fetchone()
        return dict(row) if row else {
            "organization_id": organization_id, "period": period,
            "evaluations": 0, "assets_created": 0,
        }


class StripeBilling:
    def __init__(self, store: BillingStore):
        self.store = store
        self.secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
        self.success_url = os.getenv("STRIPE_SUCCESS_URL", "https://example.com/access.html?billing=success")
        self.cancel_url = os.getenv("STRIPE_CANCEL_URL", "https://example.com/console?billing=cancelled")

    @property
    def configured(self) -> bool:
        return bool(self.secret_key)

    def _price_id(self, plan: Plan) -> str | None:
        return os.getenv(plan.price_env, "").strip() if plan.price_env else None

    def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        if not self.secret_key:
            raise RuntimeError("Stripe is not configured. Set STRIPE_SECRET_KEY.")
        response = httpx.post(
            STRIPE_API + path,
            data=data,
            headers={"Authorization": f"Bearer {self.secret_key}"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def create_checkout(self, organization_id: str, email: str, plan_key: str) -> dict[str, Any]:
        plan = PLANS.get(plan_key)
        if not plan:
            raise ValueError("Unknown plan")
        if plan.monthly_usd == 0:
            return {"checkout_required": False, "plan": plan_key, "url": None}
        price_id = self._price_id(plan)
        if not price_id:
            raise RuntimeError(f"Stripe price is not configured for plan '{plan_key}'.")

        account = self.store.get_account(organization_id)
        customer_id = account.get("customer_id")
        if not customer_id:
            customer = self._post("/customers", {
                "email": email,
                "metadata[organization_id]": organization_id,
            })
            customer_id = customer["id"]
            self.store.update(organization_id, customer_id=customer_id)

        session = self._post("/checkout/sessions", {
            "mode": "payment",
            "customer": customer_id,
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
            "success_url": self.success_url + ("&" if "?" in self.success_url else "?") + "session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": self.cancel_url,
            "allow_promotion_codes": "true",
            "metadata[organization_id]": organization_id,
            "metadata[plan]": plan_key,
        })
        self.store.update(
            organization_id,
            checkout_session_id=session.get("id"),
            plan=plan_key,
            status="checkout_pending",
        )
        return {"checkout_required": True, "plan": plan_key, "session_id": session.get("id"), "url": session.get("url")}

    def verify_webhook(self, payload: bytes, signature: str, tolerance: int = 300) -> bool:
        if not self.webhook_secret:
            return False
        parts: dict[str, list[str]] = {}
        for item in signature.split(","):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            parts.setdefault(key, []).append(value)
        timestamps = parts.get("t", [])
        signatures = parts.get("v1", [])
        if not timestamps or not signatures:
            return False
        try:
            timestamp = int(timestamps[0])
        except ValueError:
            return False
        if abs(int(time.time()) - timestamp) > tolerance:
            return False
        signed = f"{timestamp}.".encode() + payload
        expected = hmac.new(self.webhook_secret.encode(), signed, hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(expected, value) for value in signatures)

    def handle_webhook(self, event: dict[str, Any]) -> dict[str, Any]:
        event_type = event.get("type", "")
        obj = ((event.get("data") or {}).get("object") or {})
        metadata = obj.get("metadata") or {}
        organization_id = metadata.get("organization_id")
        if not organization_id and event_type.startswith("customer.subscription"):
            customer_id = obj.get("customer")
            if customer_id:
                # Customer metadata is not included reliably on subscription events;
                # resolve it through our local account table.
                account = self._find_by_customer(customer_id)
                organization_id = account.get("organization_id") if account else None
        if not organization_id:
            return {"handled": False, "reason": "missing_organization_id", "type": event_type}

        if event_type == "checkout.session.completed":
            self.store.update(
                organization_id,
                plan=metadata.get("plan", "developer"),
                status="active",
                customer_id=obj.get("customer"),
                subscription_id=obj.get("subscription"),
            )
        elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
            plan_key = metadata.get("plan") or self._plan_from_subscription(obj)
            self.store.update(
                organization_id,
                plan=plan_key or "developer",
                status=obj.get("status", "active"),
                customer_id=obj.get("customer"),
                subscription_id=obj.get("id"),
                current_period_end=(
                    datetime.fromtimestamp(obj["current_period_end"], timezone.utc).isoformat()
                    if obj.get("current_period_end") else None
                ),
            )
        elif event_type == "customer.subscription.deleted":
            self.store.update(organization_id, status="cancelled", plan="developer", subscription_id=None)
        else:
            return {"handled": False, "reason": "event_not_consumed", "type": event_type}
        return {"handled": True, "type": event_type, "organization_id": organization_id}

    def _find_by_customer(self, customer_id: str) -> Optional[dict[str, Any]]:
        with connect_database(self.store.db_path) as db:
            row = db.execute(
                "SELECT * FROM billing_accounts WHERE customer_id = ?", (customer_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _plan_from_subscription(obj: dict[str, Any]) -> str:
        items = ((obj.get("items") or {}).get("data") or [])
        price = ((items[0] if items else {}).get("price") or {}).get("id")
        for key, plan in PLANS.items():
            if plan.price_env and price and os.getenv(plan.price_env, "") == price:
                return key
        return "developer"
