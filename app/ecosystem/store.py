from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text

from app.config import DATABASE_URL


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def dumps(value: Any) -> str:
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def loads(value: str | None) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}


class EcosystemStore:
    """Persistent registry for the AAI ecosystem and Assurance Exchange."""

    def __init__(self, database_url: str | None = None):
        self.url = database_url or DATABASE_URL
        kwargs = {
            "future": True,
            "pool_pre_ping": True,
        }
        if self.url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        self.engine = create_engine(self.url, **kwargs)
        self.init()

    def close(self) -> None:
        self.engine.dispose()

    def init(self) -> None:
        with self.engine.begin() as c:
            c.execute(text("""
                CREATE TABLE IF NOT EXISTS ecosystem_participants (
                    id VARCHAR(100) PRIMARY KEY,
                    organization_id VARCHAR(80),
                    kind VARCHAR(40) NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    website TEXT,
                    description TEXT,
                    status VARCHAR(30) NOT NULL DEFAULT 'active',
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(organization_id)
                )
            """))
            c.execute(text("""
                CREATE TABLE IF NOT EXISTS ecosystem_artifacts (
                    id VARCHAR(100) PRIMARY KEY,
                    participant_id VARCHAR(100) NOT NULL,
                    kind VARCHAR(60) NOT NULL,
                    name VARCHAR(240) NOT NULL,
                    version VARCHAR(100) NOT NULL,
                    visibility VARCHAR(20) NOT NULL DEFAULT 'public',
                    manifest_json TEXT NOT NULL,
                    content_hash VARCHAR(64) NOT NULL,
                    downloads INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(participant_id, kind, name, version),
                    FOREIGN KEY(participant_id) REFERENCES ecosystem_participants(id)
                )
            """))
            c.execute(text("""
                CREATE TABLE IF NOT EXISTS ecosystem_integrations (
                    id VARCHAR(100) PRIMARY KEY,
                    participant_id VARCHAR(100) NOT NULL,
                    provider VARCHAR(160) NOT NULL,
                    integration_type VARCHAR(80) NOT NULL,
                    protocol_version VARCHAR(40) NOT NULL,
                    conformance_status VARCHAR(30) NOT NULL DEFAULT 'self_declared',
                    capabilities_json TEXT NOT NULL,
                    endpoint TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(participant_id, provider, integration_type),
                    FOREIGN KEY(participant_id) REFERENCES ecosystem_participants(id)
                )
            """))
            c.execute(text("""
                CREATE TABLE IF NOT EXISTS ecosystem_relationships (
                    id VARCHAR(100) PRIMARY KEY,
                    from_participant_id VARCHAR(100) NOT NULL,
                    to_participant_id VARCHAR(100) NOT NULL,
                    relation VARCHAR(80) NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(from_participant_id, to_participant_id, relation),
                    FOREIGN KEY(from_participant_id) REFERENCES ecosystem_participants(id),
                    FOREIGN KEY(to_participant_id) REFERENCES ecosystem_participants(id)
                )
            """))
            c.execute(text("""
                CREATE TABLE IF NOT EXISTS ecosystem_signals (
                    id VARCHAR(100) PRIMARY KEY,
                    participant_id VARCHAR(100) NOT NULL,
                    signal_type VARCHAR(80) NOT NULL,
                    value REAL NOT NULL,
                    source VARCHAR(200) NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(participant_id) REFERENCES ecosystem_participants(id)
                )
            """))
            c.execute(text("""
                CREATE TABLE IF NOT EXISTS ecosystem_conformance (
                    id VARCHAR(100) PRIMARY KEY,
                    participant_id VARCHAR(100) NOT NULL,
                    artifact_id VARCHAR(100),
                    protocol_version VARCHAR(40) NOT NULL,
                    checks_json TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    score REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(participant_id) REFERENCES ecosystem_participants(id),
                    FOREIGN KEY(artifact_id) REFERENCES ecosystem_artifacts(id)
                )
            """))
            c.execute(text("""
                CREATE TABLE IF NOT EXISTS ecosystem_events (
                    id VARCHAR(100) PRIMARY KEY,
                    event_type VARCHAR(120) NOT NULL,
                    actor_participant_id VARCHAR(100),
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(actor_participant_id) REFERENCES ecosystem_participants(id)
                )
            """))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_ecosystem_artifacts_kind ON ecosystem_artifacts(kind, visibility)"))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_ecosystem_integrations_provider ON ecosystem_integrations(provider)"))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_ecosystem_signals_participant ON ecosystem_signals(participant_id, created_at)"))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_ecosystem_events_created ON ecosystem_events(created_at)"))

    def participant_for_org(self, organization_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as c:
            row = c.execute(text("SELECT * FROM ecosystem_participants WHERE organization_id=:org"), {"org": organization_id}).mappings().first()
        return self._participant(row) if row else None

    def create_participant(self, organization_id: str, kind: str, name: str, website: str | None, description: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
        existing = self.participant_for_org(organization_id)
        if existing:
            return existing
        pid = "eco_" + uuid.uuid4().hex[:18]
        ts = now_iso()
        with self.engine.begin() as c:
            c.execute(text("""
                INSERT INTO ecosystem_participants
                (id, organization_id, kind, name, website, description, status, metadata_json, created_at, updated_at)
                VALUES (:id,:org,:kind,:name,:website,:description,'active',:metadata,:created,:updated)
            """), {"id": pid, "org": organization_id, "kind": kind, "name": name, "website": website, "description": description, "metadata": dumps(metadata), "created": ts, "updated": ts})
            self._event_tx(c, "participant.registered", pid, {"participant_id": pid, "kind": kind, "name": name})
        return self.get_participant(pid)

    def get_participant(self, participant_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as c:
            row = c.execute(text("SELECT * FROM ecosystem_participants WHERE id=:id"), {"id": participant_id}).mappings().first()
        return self._participant(row) if row else None

    def list_participants(self, kind: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM ecosystem_participants WHERE status='active'"
        params: dict[str, Any] = {}
        if kind:
            q += " AND kind=:kind"
            params["kind"] = kind
        q += " ORDER BY created_at ASC"
        with self.engine.connect() as c:
            rows = c.execute(text(q), params).mappings().all()
        return [self._participant(r) for r in rows]

    def create_artifact(self, participant_id: str, kind: str, name: str, version: str, visibility: str, manifest: dict[str, Any], content_hash: str) -> dict[str, Any]:
        aid = "artifact_" + uuid.uuid4().hex[:18]
        ts = now_iso()
        with self.engine.begin() as c:
            c.execute(text("""
                INSERT INTO ecosystem_artifacts
                (id, participant_id, kind, name, version, visibility, manifest_json, content_hash, downloads, created_at, updated_at)
                VALUES (:id,:participant,:kind,:name,:version,:visibility,:manifest,:hash,0,:created,:updated)
            """), {"id": aid, "participant": participant_id, "kind": kind, "name": name, "version": version, "visibility": visibility, "manifest": dumps(manifest), "hash": content_hash, "created": ts, "updated": ts})
            self._event_tx(c, "artifact.published", participant_id, {"artifact_id": aid, "kind": kind, "name": name, "version": version})
        return self.get_artifact(aid)

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as c:
            row = c.execute(text("SELECT * FROM ecosystem_artifacts WHERE id=:id"), {"id": artifact_id}).mappings().first()
        return self._artifact(row) if row else None

    def list_artifacts(self, kind: str | None = None, participant_id: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM ecosystem_artifacts WHERE visibility='public'"
        params: dict[str, Any] = {}
        if kind:
            q += " AND kind=:kind"; params["kind"] = kind
        if participant_id:
            q += " AND participant_id=:participant"; params["participant"] = participant_id
        q += " ORDER BY created_at DESC"
        with self.engine.connect() as c:
            rows = c.execute(text(q), params).mappings().all()
        return [self._artifact(r) for r in rows]

    def increment_download(self, artifact_id: str) -> dict[str, Any] | None:
        with self.engine.begin() as c:
            c.execute(text("UPDATE ecosystem_artifacts SET downloads=downloads+1, updated_at=:updated WHERE id=:id AND visibility='public'"), {"id": artifact_id, "updated": now_iso()})
        return self.get_artifact(artifact_id)

    def add_integration(self, participant_id: str, provider: str, integration_type: str, protocol_version: str, conformance_status: str, capabilities: list[str], endpoint: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
        iid = "integration_" + uuid.uuid4().hex[:18]
        ts = now_iso()
        with self.engine.begin() as c:
            c.execute(text("""
                INSERT INTO ecosystem_integrations
                (id, participant_id, provider, integration_type, protocol_version, conformance_status, capabilities_json, endpoint, metadata_json, created_at, updated_at)
                VALUES (:id,:participant,:provider,:type,:protocol,:status,:capabilities,:endpoint,:metadata,:created,:updated)
                ON CONFLICT(participant_id, provider, integration_type) DO UPDATE SET
                    protocol_version=excluded.protocol_version,
                    conformance_status=excluded.conformance_status,
                    capabilities_json=excluded.capabilities_json,
                    endpoint=excluded.endpoint,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
            """), {"id": iid, "participant": participant_id, "provider": provider, "type": integration_type, "protocol": protocol_version, "status": conformance_status, "capabilities": dumps(capabilities), "endpoint": endpoint, "metadata": dumps(metadata), "created": ts, "updated": ts})
            self._event_tx(c, "integration.registered", participant_id, {"provider": provider, "integration_type": integration_type, "protocol_version": protocol_version})
        with self.engine.connect() as c:
            row = c.execute(text("SELECT * FROM ecosystem_integrations WHERE participant_id=:p AND provider=:v AND integration_type=:t"), {"p": participant_id, "v": provider, "t": integration_type}).mappings().first()
        return self._integration(row)

    def list_integrations(self, provider: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM ecosystem_integrations"
        params: dict[str, Any] = {}
        if provider:
            q += " WHERE provider=:provider"; params["provider"] = provider
        q += " ORDER BY created_at DESC"
        with self.engine.connect() as c:
            rows = c.execute(text(q), params).mappings().all()
        return [self._integration(r) for r in rows]

    def upsert_relationship(self, from_id: str, to_id: str, relation: str, metadata: dict[str, Any]) -> dict[str, Any]:
        rid = "rel_" + uuid.uuid4().hex[:18]
        ts = now_iso()
        with self.engine.begin() as c:
            c.execute(text("""
                INSERT INTO ecosystem_relationships
                (id, from_participant_id, to_participant_id, relation, metadata_json, created_at)
                VALUES (:id,:f,:t,:relation,:metadata,:created)
                ON CONFLICT(from_participant_id, to_participant_id, relation) DO UPDATE SET metadata_json=excluded.metadata_json
            """), {"id": rid, "f": from_id, "t": to_id, "relation": relation, "metadata": dumps(metadata), "created": ts})
        with self.engine.connect() as c:
            row = c.execute(text("SELECT * FROM ecosystem_relationships WHERE from_participant_id=:f AND to_participant_id=:t AND relation=:r"), {"f": from_id, "t": to_id, "r": relation}).mappings().first()
        return self._relationship(row)

    def graph(self) -> dict[str, Any]:
        participants = self.list_participants()
        with self.engine.connect() as c:
            rows = c.execute(text("SELECT * FROM ecosystem_relationships ORDER BY created_at ASC")).mappings().all()
        return {"nodes": [{"id": p["id"], "name": p["name"], "kind": p["kind"]} for p in participants], "edges": [self._relationship(r) for r in rows]}

    def add_signal(self, participant_id: str, signal_type: str, value: float, source: str, metadata: dict[str, Any]) -> dict[str, Any]:
        sid = "signal_" + uuid.uuid4().hex[:18]
        ts = now_iso()
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO ecosystem_signals (id,participant_id,signal_type,value,source,metadata_json,created_at) VALUES (:id,:p,:type,:value,:source,:metadata,:created)"), {"id": sid, "p": participant_id, "type": signal_type, "value": float(value), "source": source, "metadata": dumps(metadata), "created": ts})
        return {"id": sid, "participant_id": participant_id, "signal_type": signal_type, "value": float(value), "source": source, "metadata": metadata, "created_at": ts}

    def signals(self, participant_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            rows = c.execute(text("SELECT * FROM ecosystem_signals WHERE participant_id=:p ORDER BY created_at DESC"), {"p": participant_id}).mappings().all()
        return [{"id": r["id"], "participant_id": r["participant_id"], "signal_type": r["signal_type"], "value": r["value"], "source": r["source"], "metadata": loads(r["metadata_json"]), "created_at": r["created_at"]} for r in rows]

    def reputation(self, participant_id: str) -> dict[str, Any]:
        signals = self.signals(participant_id)
        weights = {"conformance": 0.35, "published_artifact": 0.20, "integration": 0.15, "adoption": 0.20, "verified_signal": 0.10}
        grouped: dict[str, list[float]] = {}
        for s in signals:
            grouped.setdefault(s["signal_type"], []).append(float(s["value"]))
        components = {}
        score = 0.0
        for kind, weight in weights.items():
            vals = grouped.get(kind, [])
            component = max(0.0, min(100.0, sum(vals) / len(vals))) if vals else 0.0
            components[kind] = component
            score += component * weight
        return {"participant_id": participant_id, "score": round(score, 2), "components": components, "signal_count": len(signals), "method": "weighted_mean_v1"}

    def record_conformance(self, participant_id: str, artifact_id: str | None, protocol_version: str, checks: list[dict[str, Any]], passed: bool, score: float) -> dict[str, Any]:
        cid = "conf_" + uuid.uuid4().hex[:18]
        ts = now_iso()
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO ecosystem_conformance (id,participant_id,artifact_id,protocol_version,checks_json,passed,score,created_at) VALUES (:id,:p,:a,:v,:checks,:passed,:score,:created)"), {"id": cid, "p": participant_id, "a": artifact_id, "v": protocol_version, "checks": dumps(checks), "passed": int(bool(passed)), "score": float(score), "created": ts})
            self._event_tx(c, "conformance.recorded", participant_id, {"conformance_id": cid, "passed": bool(passed), "score": float(score)})
        return {"id": cid, "participant_id": participant_id, "artifact_id": artifact_id, "protocol_version": protocol_version, "checks": checks, "passed": bool(passed), "score": float(score), "created_at": ts}

    def conformance(self, participant_id: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM ecosystem_conformance"
        params: dict[str, Any] = {}
        if participant_id:
            q += " WHERE participant_id=:p"; params["p"] = participant_id
        q += " ORDER BY created_at DESC"
        with self.engine.connect() as c:
            rows = c.execute(text(q), params).mappings().all()
        return [{"id": r["id"], "participant_id": r["participant_id"], "artifact_id": r["artifact_id"], "protocol_version": r["protocol_version"], "checks": loads(r["checks_json"]), "passed": bool(r["passed"]), "score": r["score"], "created_at": r["created_at"]} for r in rows]

    def stats(self) -> dict[str, Any]:
        with self.engine.connect() as c:
            participants = c.execute(text("SELECT COUNT(*) FROM ecosystem_participants WHERE status='active'")).scalar_one()
            artifacts = c.execute(text("SELECT COUNT(*) FROM ecosystem_artifacts WHERE visibility='public'")).scalar_one()
            integrations = c.execute(text("SELECT COUNT(*) FROM ecosystem_integrations")).scalar_one()
            relationships = c.execute(text("SELECT COUNT(*) FROM ecosystem_relationships")).scalar_one()
            conformance = c.execute(text("SELECT COUNT(*) FROM ecosystem_conformance")).scalar_one()
            passed = c.execute(text("SELECT COUNT(*) FROM ecosystem_conformance WHERE passed=1")).scalar_one()
            signals = c.execute(text("SELECT COUNT(*) FROM ecosystem_signals")).scalar_one()
        return {"participants": participants, "public_artifacts": artifacts, "integrations": integrations, "relationships": relationships, "conformance_runs": conformance, "passed_conformance_runs": passed, "signals": signals}

    def _event_tx(self, c, event_type: str, actor: str | None, payload: dict[str, Any]) -> None:
        c.execute(text("INSERT INTO ecosystem_events (id,event_type,actor_participant_id,payload_json,created_at) VALUES (:id,:type,:actor,:payload,:created)"), {"id": "event_" + uuid.uuid4().hex[:18], "type": event_type, "actor": actor, "payload": dumps(payload), "created": now_iso()})

    @staticmethod
    def _participant(r) -> dict[str, Any]:
        return {"id": r["id"], "organization_id": r["organization_id"], "kind": r["kind"], "name": r["name"], "website": r["website"], "description": r["description"], "status": r["status"], "metadata": loads(r["metadata_json"]), "created_at": r["created_at"], "updated_at": r["updated_at"]}

    @staticmethod
    def _artifact(r) -> dict[str, Any]:
        return {"id": r["id"], "participant_id": r["participant_id"], "kind": r["kind"], "name": r["name"], "version": r["version"], "visibility": r["visibility"], "manifest": loads(r["manifest_json"]), "content_hash": r["content_hash"], "downloads": r["downloads"], "created_at": r["created_at"], "updated_at": r["updated_at"]}

    @staticmethod
    def _integration(r) -> dict[str, Any]:
        return {"id": r["id"], "participant_id": r["participant_id"], "provider": r["provider"], "integration_type": r["integration_type"], "protocol_version": r["protocol_version"], "conformance_status": r["conformance_status"], "capabilities": loads(r["capabilities_json"]), "endpoint": r["endpoint"], "metadata": loads(r["metadata_json"]), "created_at": r["created_at"], "updated_at": r["updated_at"]}

    @staticmethod
    def _relationship(r) -> dict[str, Any]:
        return {"id": r["id"], "from_participant_id": r["from_participant_id"], "to_participant_id": r["to_participant_id"], "relation": r["relation"], "metadata": loads(r["metadata_json"]), "created_at": r["created_at"]}
