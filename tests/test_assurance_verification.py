from app.assurance.passport import AssurancePassport
from app.assurance.verification import (
    evidence_hash,
    verify_evidence,
    verify_passport_evidence,
)


def make_evidence():
    payload = {
        "input": "Customer received a damaged product",
        "output": "REFUND_APPROVED",
        "reliability": 100.0,
    }

    return {
        "evidence_id": "ev_test_001",
        "evidence_type": "evaluation",
        "system_id": "refund-agent",
        "system_version": "1.0.0",
        "source": "integration_test",
        "payload": payload,
        "content_hash": evidence_hash(payload),
    }


def make_passport():
    return AssurancePassport(
        passport_id="passport_test_001",
        assurance_id="assurance_test_001",
        system_id="refund-agent",
        system_version="1.0.0",
        environment="production",
        verdict="ASSURED",
        metrics={"reliability": 100.0},
        policy_id="production-v1",
        evaluation_ids=["eval_test_001"],
        evidence_ids=["ev_test_001"],
        reasons=[],
        engine_version="assurance-core-1.0.0",
    ).to_dict()


def test_evidence_hash_is_deterministic():
    payload = {"b": 2, "a": 1}

    assert evidence_hash(payload) == evidence_hash(
        {"a": 1, "b": 2}
    )


def test_valid_evidence_verifies():
    evidence = make_evidence()

    result = verify_evidence(**evidence)

    assert result["valid"] is True
    assert result["algorithm"] == "SHA-256"


def test_tampered_evidence_fails():
    evidence = make_evidence()

    evidence["payload"]["reliability"] = 20.0

    result = verify_evidence(**evidence)

    assert result["valid"] is False
    assert result["actual_hash"] != result["expected_hash"]


def test_passport_evidence_verifies():
    passport = make_passport()
    evidence = make_evidence()

    result = verify_passport_evidence(
        passport,
        [evidence],
    )

    assert result["valid"] is True
    assert result["evidence_count"] == 1
    assert result["verified_count"] == 1


def test_missing_passport_evidence_fails():
    passport = make_passport()

    result = verify_passport_evidence(
        passport,
        [],
    )

    assert result["valid"] is False
    assert result["verified_count"] == 0


def test_wrong_system_evidence_fails():
    passport = make_passport()
    evidence = make_evidence()

    evidence["system_id"] = "different-agent"

    result = verify_passport_evidence(
        passport,
        [evidence],
    )

    assert result["valid"] is False
