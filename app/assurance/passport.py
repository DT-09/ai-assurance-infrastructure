from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


PASSPORT_VERSION = "1.0.0"


def _canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AssurancePassport:
    """
    Portable, machine-readable representation of an AI system's
    assurance state.

    The passport contains the assurance decision and references the
    underlying evaluations and evidence. Its canonical representation
    is hashed so independent consumers can verify its integrity.
    """

    def __init__(
        self,
        *,
        passport_id: str,
        assurance_id: str,
        system_id: str,
        system_version: str,
        environment: str,
        verdict: str,
        metrics: Dict[str, Any],
        policy_id: Optional[str],
        evaluation_ids: List[str],
        evidence_ids: List[str],
        reasons: List[str],
        engine_version: str,
        created_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.passport_id = passport_id
        self.assurance_id = assurance_id
        self.system_id = system_id
        self.system_version = system_version
        self.environment = environment
        self.verdict = verdict
        self.metrics = metrics
        self.policy_id = policy_id
        self.evaluation_ids = evaluation_ids
        self.evidence_ids = evidence_ids
        self.reasons = reasons
        self.engine_version = engine_version
        self.created_at = (
            created_at.isoformat()
            if isinstance(created_at, datetime)
            else str(created_at)
            if created_at is not None
            else _now()
        )
        self.metadata = metadata or {}

    def payload(self) -> Dict[str, Any]:
        """
        Return the canonical passport payload excluding the integrity hash.
        """
        return {
            "passport_version": PASSPORT_VERSION,
            "passport_id": self.passport_id,
            "assurance_id": self.assurance_id,
            "system": {
                "system_id": self.system_id,
                "version": self.system_version,
                "environment": self.environment,
            },
            "assurance": {
                "verdict": self.verdict,
                "metrics": self.metrics,
                "policy_id": self.policy_id,
                "evaluation_ids": self.evaluation_ids,
                "evidence_ids": self.evidence_ids,
                "reasons": self.reasons,
            },
            "engine_version": self.engine_version,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def content_hash(self) -> str:
        """
        SHA-256 hash of the canonical passport payload.
        """
        return _sha256(_canonical_json(self.payload()))

    def to_dict(self) -> Dict[str, Any]:
        """
        Return the complete portable passport.
        """
        result = self.payload()
        result["integrity"] = {
            "algorithm": "SHA-256",
            "content_hash": self.content_hash(),
        }
        return result

    def to_json(self) -> str:
        """
        Serialize the passport deterministically.
        """
        return _canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssurancePassport":
        # Canonical Passport format is flattened.
        # Keep compatibility with the older nested representation.

        if "system" in data and "assurance" in data:
            system = data.get("system") or {}
            assurance = data.get("assurance") or {}

            return cls(
                passport_id=str(data["passport_id"]),
                assurance_id=str(data["assurance_id"]),
                system_id=str(system["system_id"]),
                system_version=str(system["version"]),
                environment=str(system["environment"]),
                verdict=str(assurance["verdict"]),
                metrics=dict(assurance.get("metrics") or {}),
                policy_id=assurance.get("policy_id"),
                evaluation_ids=list(assurance.get("evaluation_ids") or []),
                evidence_ids=list(assurance.get("evidence_ids") or []),
                reasons=list(assurance.get("reasons") or []),
                engine_version=str(data["engine_version"]),
                created_at=str(data["created_at"]),
                metadata=dict(data.get("metadata") or {}),
            )

        return cls(
            passport_id=str(data["passport_id"]),
            assurance_id=str(data["assurance_id"]),
            system_id=str(data["system_id"]),
            system_version=str(data["system_version"]),
            environment=str(data["environment"]),
            verdict=str(data["verdict"]),
            metrics=dict(data.get("metrics") or {}),
            policy_id=data.get("policy_id"),
            evaluation_ids=list(data.get("evaluation_ids") or []),
            evidence_ids=list(data.get("evidence_ids") or []),
            reasons=list(data.get("reasons") or []),
            engine_version=str(data["engine_version"]),
            created_at=str(data["created_at"]),
            metadata=dict(data.get("metadata") or {}),
        )

    @classmethod
    def from_json(cls, raw: str) -> "AssurancePassport":
        return cls.from_dict(json.loads(raw))


def verify_passport(data: Dict[str, Any]) -> bool:
    """
    Independently verify the passport's integrity hash.

    Returns False for malformed or tampered passports.
    """
    try:
        integrity = data.get("integrity") or {}
        expected_hash = integrity.get("content_hash")

        if not expected_hash:
            return False

        payload = dict(data)
        payload.pop("integrity", None)

        actual_hash = _sha256(_canonical_json(payload))

        return (
            integrity.get("algorithm") == "SHA-256"
            and expected_hash == actual_hash
        )
    except (TypeError, ValueError, KeyError):
        return False
