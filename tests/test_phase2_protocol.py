import json
from pathlib import Path

from app.assurance.passport import AssurancePassport
from app.assurance.protocol import AssuranceProtocol
from protocol.v1.conformance import conformance_report, validate_envelope


def make_passport():
    return AssurancePassport(
        passport_id="p_phase2",
        assurance_id="a_phase2",
        system_id="agent_phase2",
        system_version="1.0.0",
        environment="production",
        verdict="ASSURED",
        metrics={"reliability": 99.0},
        policy_id="policy_1",
        evaluation_ids=["eval_1"],
        evidence_ids=["evidence_1"],
        reasons=["passed"],
        engine_version="3.2.0",
    ).to_dict()


def test_protocol_manifest_is_machine_readable():
    manifest = AssuranceProtocol.manifest()
    assert manifest["protocol"] == "AI Assurance Protocol"
    assert manifest["version"] == "1.0.0"
    assert "trust_passport" in manifest["capabilities"]


def test_envelope_conformance():
    envelope = AssuranceProtocol.envelope("identity.asset", {"system_id": "agent_1"})
    report = conformance_report(envelope)
    assert report["conformant"] is True
    assert validate_envelope(envelope)["valid"] is True


def test_passport_conformance_accepts_valid_passport():
    passport = make_passport()
    envelope = AssuranceProtocol.envelope("passport.issue", passport)
    report = conformance_report(envelope)
    assert report["conformant"] is True


def test_passport_conformance_rejects_tampering():
    passport = make_passport()
    passport["assurance"]["verdict"] = "BLOCKED"
    envelope = AssuranceProtocol.envelope("passport.issue", passport)
    # The envelope remains internally consistent, but the passport payload is
    # now invalid because its own integrity field no longer matches.
    report = conformance_report(envelope)
    assert report["conformant"] is False


def test_example_file_exists():
    path = Path("protocol/v1/examples/passport.issue.json")
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["kind"] == "passport.issue"
