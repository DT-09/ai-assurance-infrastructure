from __future__ import annotations

from app.assurance.protocol import AssuranceProtocol
from app.ecosystem import EcosystemService, EcosystemStore


def make_store(tmp_path):
    store = EcosystemStore(f"sqlite:///{(tmp_path / 'ecosystem.db').as_posix()}")
    return store


def test_participant_registration_is_idempotent(tmp_path):
    store = make_store(tmp_path)
    service = EcosystemService(store)
    first = service.register_participant("org-1", {"kind": "platform", "name": "Platform A"})
    second = service.register_participant("org-1", {"kind": "platform", "name": "Platform A"})
    assert first["id"] == second["id"]
    assert store.stats()["participants"] == 1
    store.close()


def test_exchange_artifact_is_content_addressable(tmp_path):
    store = make_store(tmp_path)
    service = EcosystemService(store)
    participant = service.register_participant("org-1", {"kind": "developer", "name": "Developer A"})
    artifact = service.publish_artifact(participant["id"], {"kind": "adapter", "name": "provider-adapter", "version": "1.0.0", "manifest": {"capabilities": ["identity", "evidence"]}})
    assert len(artifact["content_hash"]) == 64
    assert artifact["visibility"] == "public"
    assert store.list_artifacts("adapter")[0]["id"] == artifact["id"]
    store.close()


def test_private_artifact_is_not_public(tmp_path):
    store = make_store(tmp_path)
    service = EcosystemService(store)
    participant = service.register_participant("org-1", {"kind": "enterprise", "name": "Enterprise A"})
    service.publish_artifact(participant["id"], {"kind": "control_pack", "name": "internal", "version": "1", "visibility": "private", "manifest": {}})
    assert store.list_artifacts() == []
    store.close()


def test_conformance_accepts_protocol_envelope(tmp_path):
    store = make_store(tmp_path)
    service = EcosystemService(store)
    participant = service.register_participant("org-1", {"kind": "integrator", "name": "Integrator A"})
    envelope = AssuranceProtocol.envelope("evidence.record", {"evidence_id": "ev-1", "result": "pass"})
    result = service.conformance(participant["id"], {"envelope": envelope})
    assert result["passed"] is True
    assert result["score"] == 100.0
    store.close()


def test_conformance_rejects_tampered_envelope(tmp_path):
    store = make_store(tmp_path)
    service = EcosystemService(store)
    participant = service.register_participant("org-1", {"kind": "integrator", "name": "Integrator A"})
    envelope = AssuranceProtocol.envelope("evidence.record", {"evidence_id": "ev-1"})
    envelope["payload"]["evidence_id"] = "tampered"
    result = service.conformance(participant["id"], {"envelope": envelope})
    assert result["passed"] is False
    assert result["score"] < 100.0
    store.close()


def test_relationship_graph_and_reputation(tmp_path):
    store = make_store(tmp_path)
    service = EcosystemService(store)
    a = service.register_participant("org-a", {"kind": "platform", "name": "Platform A"})
    b = service.register_participant("org-b", {"kind": "assurance_provider", "name": "Provider B"})
    store.upsert_relationship(a["id"], b["id"], "integrates_with", {"protocol": "1.0.0"})
    store.add_signal(a["id"], "integration", 90, "verified", {})
    store.add_signal(a["id"], "conformance", 100, "protocol_suite", {})
    graph = store.graph()
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1
    reputation = store.reputation(a["id"])
    assert 0 < reputation["score"] <= 100
    store.close()


def test_download_counter(tmp_path):
    store = make_store(tmp_path)
    service = EcosystemService(store)
    participant = service.register_participant("org-1", {"kind": "developer", "name": "Developer A"})
    artifact = service.publish_artifact(participant["id"], {"kind": "schema", "name": "schema", "version": "1", "manifest": {}})
    assert artifact["downloads"] == 0
    downloaded = store.increment_download(artifact["id"])
    assert downloaded["downloads"] == 1
    store.close()
