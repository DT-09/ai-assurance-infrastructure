from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Optional


def canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def evidence_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()


def verify_evidence(
    *,
    evidence_id: str,
    evidence_type: str,
    system_id: str,
    system_version: str,
    source: str,
    payload: Dict[str, Any],
    expected_hash: Optional[str] = None,
    content_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Independently verify an evidence record.

    Accepts either expected_hash or content_hash so the verifier
    matches the canonical EvidenceRecord schema.
    """

    actual_hash = evidence_hash(payload)
    expected = expected_hash or content_hash or ""

    valid = (
        bool(evidence_id)
        and bool(evidence_type)
        and bool(system_id)
        and bool(system_version)
        and bool(source)
        and bool(expected)
        and actual_hash == expected
    )

    return {
        "evidence_id": evidence_id,
        "valid": valid,
        "algorithm": "SHA-256",
        "expected_hash": expected,
        "actual_hash": actual_hash,
        "system_id": system_id,
        "system_version": system_version,
    }


def verify_passport_evidence(
    passport: Dict[str, Any],
    evidence_records: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Verify every evidence record referenced by an Assurance Passport.
    """

    assurance = passport.get("assurance") or {}
    expected_ids = list(
        assurance.get("evidence_ids") or []
    )

    records_by_id = {
        str(record.get("evidence_id")): record
        for record in evidence_records
        if record.get("evidence_id")
    }

    results = []

    for evidence_id in expected_ids:
        record = records_by_id.get(str(evidence_id))

        if record is None:
            results.append(
                {
                    "evidence_id": evidence_id,
                    "valid": False,
                    "reason": "evidence_not_found",
                }
            )
            continue

        result = verify_evidence(
            evidence_id=str(record["evidence_id"]),
            evidence_type=str(record["evidence_type"]),
            system_id=str(record["system_id"]),
            system_version=str(record["system_version"]),
            source=str(record["source"]),
            payload=dict(record.get("payload") or {}),
            content_hash=str(record["content_hash"]),
        )

        passport_system = passport.get("system") or {}

        if (
            result["system_id"] != passport_system.get("system_id")
            or result["system_version"]
            != passport_system.get("version")
        ):
            result["valid"] = False
            result["reason"] = "evidence_system_mismatch"

        results.append(result)

    valid = bool(results) and all(
        result["valid"]
        for result in results
    )

    if not expected_ids:
        valid = False

    return {
        "valid": valid,
        "evidence_count": len(expected_ids),
        "verified_count": sum(
            1
            for result in results
            if result["valid"]
        ),
        "results": results,
    }
