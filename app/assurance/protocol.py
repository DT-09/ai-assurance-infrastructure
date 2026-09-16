from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from .enforcement import EnforcementResult


PROTOCOL_NAME = "AI Assurance Protocol"
PROTOCOL_VERSION = "1.0.0"


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def content_hash(value: Any) -> str:
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


class AssuranceProtocol:
    """
    Vendor-neutral machine-readable assurance protocol.

    The protocol defines the external language through which
    AI systems, platforms and enterprises can exchange assurance
    information.
    """

    VERSION = PROTOCOL_VERSION

    @staticmethod
    def manifest() -> Dict[str, Any]:
        return {
            "protocol": PROTOCOL_NAME,
            "version": PROTOCOL_VERSION,
            "capabilities": [
                "identity",
                "asset_registry",
                "dependencies",
                "evidence",
                "evaluation",
                "policy",
                "assurance",
                "trust_state",
                "provenance",
                "enforcement",
                "verification",
                "trust_passport",
                "public_verification",
                "protocol_conformance",
                "developer_sdk",
                "cli",
            ],
            "trust_states": [
                "ASSURED",
                "DEGRADED",
                "BLOCKED",
                "UNKNOWN",
                "EVALUATING",
                "STALE",
            ],
            "enforcement_decisions": ["ALLOW", "REVIEW", "DENY"],
            "endpoints": {
                "manifest": "/protocol.json",
                "schema": "/protocol/v1/schema.json",
                "specification": "/protocol",
                "verify_passport": "/v1/verify/passport",
                "conformance": "/v1/protocol/conformance",
            },
        }

    @staticmethod
    def envelope(
        kind: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        body = {
            "protocol": PROTOCOL_NAME,
            "protocol_version": PROTOCOL_VERSION,
            "kind": kind,
            "payload": payload,
        }

        body["integrity"] = {
            "algorithm": "SHA-256",
            "content_hash": content_hash(body),
        }

        return body

    @staticmethod
    def enforcement(
        result: EnforcementResult,
    ) -> Dict[str, Any]:

        return AssuranceProtocol.envelope(
            "enforcement.decision",
            result.to_dict(),
        )