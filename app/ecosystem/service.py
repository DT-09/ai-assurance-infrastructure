from __future__ import annotations

import hashlib
import json
from typing import Any

from app.assurance.protocol import PROTOCOL_NAME, PROTOCOL_VERSION, AssuranceProtocol, canonical_json

from .store import EcosystemStore


ARTIFACT_KINDS = {
    "adapter", "policy", "evaluator", "benchmark", "schema",
    "attestation_verifier", "integration_kit", "dataset", "control_pack",
}
PARTICIPANT_KINDS = {"enterprise", "ai_lab", "platform", "integrator", "assurance_provider", "developer", "research", "other"}


class EcosystemService:
    """Business rules for the public AAI ecosystem and Assurance Exchange."""

    def __init__(self, store: EcosystemStore | None = None):
        self.store = store or EcosystemStore()

    def register_participant(self, organization_id: str, data: dict[str, Any]) -> dict[str, Any]:
        kind = str(data.get("kind", "other"))
        if kind not in PARTICIPANT_KINDS:
            raise ValueError("unsupported participant kind")
        name = str(data.get("name", "")).strip()
        if not name:
            raise ValueError("participant name is required")
        return self.store.create_participant(organization_id, kind, name, data.get("website"), data.get("description"), data.get("metadata") or {})

    def publish_artifact(self, participant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        kind = str(data.get("kind", ""))
        if kind not in ARTIFACT_KINDS:
            raise ValueError("unsupported artifact kind")
        name = str(data.get("name", "")).strip()
        version = str(data.get("version", "")).strip()
        if not name or not version:
            raise ValueError("artifact name and version are required")
        manifest = dict(data.get("manifest") or {})
        manifest.setdefault("protocol", PROTOCOL_NAME)
        manifest.setdefault("protocol_version", PROTOCOL_VERSION)
        content_hash = str(data.get("content_hash") or hashlib.sha256(canonical_json(manifest).encode()).hexdigest())
        if len(content_hash) != 64:
            raise ValueError("content_hash must be a SHA-256 hex digest")
        visibility = str(data.get("visibility", "public"))
        if visibility not in {"public", "private"}:
            raise ValueError("visibility must be public or private")
        return self.store.create_artifact(participant_id, kind, name, version, visibility, manifest, content_hash)

    def register_integration(self, participant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        provider = str(data.get("provider", "")).strip()
        integration_type = str(data.get("integration_type", "")).strip()
        if not provider or not integration_type:
            raise ValueError("provider and integration_type are required")
        protocol_version = str(data.get("protocol_version", PROTOCOL_VERSION))
        status = str(data.get("conformance_status", "self_declared"))
        if status not in {"self_declared", "verified", "certified", "deprecated"}:
            raise ValueError("invalid conformance_status")
        return self.store.add_integration(participant_id, provider, integration_type, protocol_version, status, list(data.get("capabilities") or []), data.get("endpoint"), data.get("metadata") or {})

    def conformance(self, participant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        protocol_version = str(data.get("protocol_version", PROTOCOL_VERSION))
        payload = data.get("envelope")
        checks: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            report = self._validate_envelope(payload, protocol_version)
            checks.extend(report["checks"])
            passed = report["passed"]
            score = report["score"]
        else:
            checks = [{"check": "envelope_present", "passed": False, "reason": "envelope must be supplied"}]
            passed, score = False, 0.0
        return self.store.record_conformance(participant_id, data.get("artifact_id"), protocol_version, checks, passed, score)

    def _validate_envelope(self, envelope: dict[str, Any], expected_version: str) -> dict[str, Any]:
        checks = []
        checks.append({"check": "protocol_name", "passed": envelope.get("protocol") == PROTOCOL_NAME})
        checks.append({"check": "protocol_version", "passed": envelope.get("protocol_version") == expected_version})
        checks.append({"check": "kind", "passed": isinstance(envelope.get("kind"), str) and bool(envelope.get("kind"))})
        checks.append({"check": "payload_object", "passed": isinstance(envelope.get("payload"), dict)})
        integrity = envelope.get("integrity")
        checks.append({"check": "integrity_algorithm", "passed": isinstance(integrity, dict) and integrity.get("algorithm") == "SHA-256"})
        checks.append({"check": "integrity_hash", "passed": self._hash_valid(envelope)})
        passed_count = sum(1 for c in checks if c["passed"])
        score = round(100.0 * passed_count / len(checks), 2)
        return {"checks": checks, "passed": passed_count == len(checks), "score": score}

    @staticmethod
    def _hash_valid(envelope: dict[str, Any]) -> bool:
        integrity = envelope.get("integrity")
        if not isinstance(integrity, dict) or integrity.get("algorithm") != "SHA-256":
            return False
        supplied = integrity.get("content_hash")
        if not isinstance(supplied, str) or len(supplied) != 64:
            return False
        body = {k: v for k, v in envelope.items() if k != "integrity"}
        canonical = canonical_json(body)
        expected = hashlib.sha256(canonical.encode()).hexdigest()
        return supplied == expected

    def public_manifest(self) -> dict[str, Any]:
        return {
            "name": "AI Assurance Infrastructure Ecosystem",
            "ecosystem_version": "1.0.0",
            "protocol": PROTOCOL_NAME,
            "protocol_version": PROTOCOL_VERSION,
            "purpose": "Interoperable registry and exchange for AI assurance integrations, artifacts, conformance and trust signals.",
            "participant_kinds": sorted(PARTICIPANT_KINDS),
            "artifact_kinds": sorted(ARTIFACT_KINDS),
            "public_surfaces": {
                "participants": "/public/ecosystem/participants",
                "artifacts": "/public/ecosystem/artifacts",
                "integrations": "/public/ecosystem/integrations",
                "graph": "/public/ecosystem/graph",
                "conformance": "/public/ecosystem/conformance",
                "stats": "/public/ecosystem/stats",
            },
            "machine_readable": True,
        }

    def exchange(self) -> dict[str, Any]:
        artifacts = self.store.list_artifacts()
        by_kind: dict[str, int] = {}
        for artifact in artifacts:
            by_kind[artifact["kind"]] = by_kind.get(artifact["kind"], 0) + 1
        return {
            "name": "AI Assurance Exchange",
            "version": "1.0.0",
            "protocol": PROTOCOL_NAME,
            "protocol_version": PROTOCOL_VERSION,
            "artifact_kinds": sorted(ARTIFACT_KINDS),
            "artifact_counts": by_kind,
            "artifacts": artifacts,
            "consumption": "public artifacts are machine-readable and content-hash addressable",
        }

    def overview(self) -> dict[str, Any]:
        stats = self.store.stats()
        participants = self.store.list_participants()
        artifacts = self.store.list_artifacts()
        integrations = self.store.list_integrations()
        conformance = self.store.conformance()
        return {
            "manifest": self.public_manifest(),
            "stats": stats,
            "participants": participants,
            "artifacts": artifacts,
            "integrations": integrations,
            "conformance": conformance,
            "graph": self.store.graph(),
        }
