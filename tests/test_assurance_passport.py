from app.assurance.passport import AssurancePassport, verify_passport


def make_passport():
    return AssurancePassport(
        passport_id="passport_test_001",
        assurance_id="assurance_test_001",
        system_id="refund-agent",
        system_version="1.0.0",
        environment="production",
        verdict="ASSURED",
        metrics={
            "reliability": 99.0,
            "critical_failures": 0,
            "latency_p95_ms": 800,
        },
        policy_id="production-v1",
        evaluation_ids=["eval_001"],
        evidence_ids=["ev_001"],
        reasons=[],
        engine_version="assurance-core-1.0.0",
    )


def test_passport_has_integrity_hash():
    passport = make_passport().to_dict()

    assert passport["integrity"]["algorithm"] == "SHA-256"
    assert len(passport["integrity"]["content_hash"]) == 64
    assert verify_passport(passport)


def test_passport_detects_tampering():
    passport = make_passport().to_dict()

    passport["assurance"]["metrics"]["reliability"] = 20.0

    assert not verify_passport(passport)


def test_passport_round_trip():
    original = make_passport()

    restored = AssurancePassport.from_json(original.to_json())

    assert restored.passport_id == original.passport_id
    assert restored.assurance_id == original.assurance_id
    assert restored.system_id == original.system_id
    assert restored.verdict == original.verdict
    assert restored.metrics == original.metrics


def test_passport_is_deterministic():
    first = make_passport()

    second = AssurancePassport.from_dict(first.to_dict())

    assert first.content_hash() == second.content_hash()
