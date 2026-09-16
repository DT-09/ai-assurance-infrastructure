from __future__ import annotations

from typing import Any

from app.assurance.passport import verify_passport
from app.assurance.protocol import PROTOCOL_NAME, PROTOCOL_VERSION

REQUIRED_ENVELOPE_FIELDS = {"protocol", "protocol_version", "kind", "payload", "integrity"}
REQUIRED_INTEGRITY_FIELDS = {"algorithm", "content_hash"}
TRUST_STATES = {"ASSURED", "DEGRADED", "BLOCKED", "UNKNOWN", "EVALUATING", "STALE"}
ENFORCEMENT_DECISIONS = {"ALLOW", "REVIEW", "DENY"}


def validate_envelope(value: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return {"valid": False, "errors": ["envelope must be an object"]}
    missing = REQUIRED_ENVELOPE_FIELDS - set(value)
    errors.extend(f"missing:{field}" for field in sorted(missing))
    if value.get("protocol") != PROTOCOL_NAME:
        errors.append("protocol_mismatch")
    if value.get("protocol_version") != PROTOCOL_VERSION:
        errors.append("protocol_version_mismatch")
    integrity = value.get("integrity")
    if not isinstance(integrity, dict):
        errors.append("integrity must be an object")
    else:
        errors.extend(f"missing:integrity.{field}" for field in sorted(REQUIRED_INTEGRITY_FIELDS - set(integrity)))
        if integrity.get("algorithm") != "SHA-256":
            errors.append("unsupported_integrity_algorithm")
        content_hash = integrity.get("content_hash")
        if not isinstance(content_hash, str) or len(content_hash) != 64:
            errors.append("invalid_content_hash")
    if "payload" in value and not isinstance(value["payload"], dict):
        errors.append("payload must be an object")
    return {"valid": not errors, "errors": errors}


def validate_trust_state(state: str) -> bool:
    return state in TRUST_STATES


def validate_enforcement_decision(decision: str) -> bool:
    return decision in ENFORCEMENT_DECISIONS


def validate_passport(value: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return {"valid": False, "errors": ["passport must be an object"]}
    if value.get("passport_version") != "1.0.0":
        errors.append("passport_version_mismatch")
    if not verify_passport(value):
        errors.append("integrity_verification_failed")
    assurance = value.get("assurance")
    if isinstance(assurance, dict) and assurance.get("verdict") not in TRUST_STATES:
        errors.append("invalid_assurance_verdict")
    elif not isinstance(assurance, dict):
        errors.append("assurance must be an object")
    return {"valid": not errors, "errors": errors}


def conformance_report(value: Any) -> dict[str, Any]:
    envelope = validate_envelope(value)
    passport = None
    if isinstance(value, dict) and value.get("kind") == "passport.issue":
        passport = validate_passport(value.get("payload"))
    valid = envelope["valid"] and (passport is None or passport["valid"])
    return {
        "protocol": PROTOCOL_NAME,
        "protocol_version": PROTOCOL_VERSION,
        "conformant": valid,
        "envelope": envelope,
        "passport": passport,
    }
