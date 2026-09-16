from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .models import Policy, PolicyRule
from .policy import PolicyEngine
from .policy_store import PolicyStore


class PolicyService:
    """
    Control-plane service for policy-as-code.

    Responsibilities:
        - validate policies
        - persist policies
        - version policies
        - bind policies to AI assets
        - resolve the applicable policy
        - expose deterministic policy evaluation
    """

    VERSION = "policy-as-code-1.1.0"
    DEFAULT_POLICY_VERSION = "1.0.0"

    def __init__(
        self,
        store: Optional[PolicyStore] = None,
    ):
        self.store = store or PolicyStore()
        self.engine = PolicyEngine()

    @staticmethod
    def _id(
        prefix: str,
    ) -> str:
        return f"{prefix}_{uuid4().hex}"

    @staticmethod
    def _now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    def validate(
        self,
        policy: Policy,
    ) -> Policy:
        if not policy.policy_id:
            raise ValueError(
                "Policy ID is required"
            )

        if not policy.name.strip():
            raise ValueError(
                "Policy name is required"
            )

        if not policy.version.strip():
            raise ValueError(
                "Policy version is required"
            )

        if not policy.rules:
            raise ValueError(
                "Policy must contain at least one rule"
            )

        for rule in policy.rules:
            if not rule.metric.strip():
                raise ValueError(
                    "Policy rule metric is required"
                )

            self.engine.validate_rule(
                rule
            )

        return policy

    def create(
        self,
        name: str,
        version: str = DEFAULT_POLICY_VERSION,
        rules: Optional[List[PolicyRule]] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
        policy_id: Optional[str] = None,
    ) -> Policy:

        policy = Policy(
            policy_id=(
                policy_id
                or self._id("pol")
            ),
            name=name,
            version=version,
            rules=rules or [],
            metadata=metadata or {},
        )

        self.validate(policy)

        self.store.save(policy)

        return policy

    def save(
        self,
        policy: Policy,
    ) -> Policy:
        self.validate(policy)
        self.store.upsert(policy)
        return policy

    def get(
        self,
        policy_id: str,
    ) -> Optional[Policy]:
        return self.store.get(
            policy_id
        )

    def list(
        self,
    ) -> List[Policy]:
        return self.store.list()

    def bind(
        self,
        asset_id: str,
        policy_id: str,
        version_id: Optional[str] = None,
        environment: Optional[str] = None,
        binding_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        policy = self.store.get(
            policy_id
        )

        if policy is None:
            raise ValueError(
                "Policy not found"
            )

        binding = {
            "binding_id": (
                binding_id
                or self._id("pbind")
            ),
            "policy_id": policy_id,
            "asset_id": asset_id,
            "version_id": version_id,
            "environment": environment,
            "created_at": self._now(),
        }

        self.store.bind(
            binding_id=binding[
                "binding_id"
            ],
            policy_id=policy_id,
            asset_id=asset_id,
            version_id=version_id,
            environment=environment,
            created_at=binding[
                "created_at"
            ],
        )

        return binding

    def unbind(
        self,
        binding_id: str,
    ) -> bool:
        return self.store.unbind(
            binding_id
        )

    def resolve(
        self,
        asset_id: str,
        version_id: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> Optional[Policy]:

        return self.store.resolve(
            asset_id=asset_id,
            version_id=version_id,
            environment=environment,
        )

    def bindings(
        self,
        asset_id: Optional[str] = None,
        version_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        return self.store.list_bindings(
            asset_id=asset_id,
            version_id=version_id,
        )

    def evaluate(
        self,
        policy: Policy,
        metrics: Dict[str, float],
    ):
        self.validate(policy)

        return self.engine.evaluate(
            policy=policy,
            metrics=metrics,
        )