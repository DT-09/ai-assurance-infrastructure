from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from .config import DATABASE_URL, DB_PATH

SCHEMA_VERSION = 11


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Store:
    """Durable control-plane store.

    SQLite is the default local/edge backend. PostgreSQL is supported through
    DATABASE_URL for hosted deployments. All writes are transactional and the
    outbox/audit tables provide a durable event boundary.
    """

    def __init__(self, path: Path | str | None = None):
        url = DATABASE_URL
        if path is not None:
            url = f"sqlite:///{Path(path).resolve()}"
        elif url.startswith("sqlite"):
            Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        engine_kwargs = {
            "future": True,
            "pool_pre_ping": True,
            "connect_args": {"check_same_thread": False} if url.startswith("sqlite") else {},
        }
        # SQLite database files must not be retained by SQLAlchemy's connection
        # pool. This is especially important on Windows, where an open pooled
        # handle prevents deletion of temporary .db files.
        if url.startswith("sqlite"):
            engine_kwargs["poolclass"] = NullPool
        self.engine: Engine = create_engine(url, **engine_kwargs)
        self.url = url
        self.init()

    def connect(self):
        return self.engine.connect()

    def init(self):
        if self.url.startswith("sqlite"):
            with self.engine.begin() as c:
                c.execute(text("PRAGMA journal_mode=WAL"))
                c.execute(text("PRAGMA foreign_keys=ON"))
        with self.engine.begin() as c:
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS system_meta (key VARCHAR(120) PRIMARY KEY, value TEXT NOT NULL)
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS organizations (
                id VARCHAR(80) PRIMARY KEY, name VARCHAR(200) NOT NULL, created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            )
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL,
                key_hash VARCHAR(64) NOT NULL UNIQUE, key_prefix VARCHAR(24) NOT NULL,
                scopes_json TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, last_used_at TEXT,
                FOREIGN KEY(organization_id) REFERENCES organizations(id)
            )
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS assets (
                id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL,
                name VARCHAR(200) NOT NULL, asset_type VARCHAR(80) NOT NULL, owner TEXT,
                environment VARCHAR(80) NOT NULL, criticality VARCHAR(20) NOT NULL,
                metadata_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(organization_id) REFERENCES organizations(id)
            )
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS versions (
                id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL,
                asset_id VARCHAR(100) NOT NULL, version VARCHAR(120) NOT NULL,
                model_ref TEXT, runtime_ref TEXT, metadata_json TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(asset_id, version), FOREIGN KEY(asset_id) REFERENCES assets(id)
            )
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS dependencies (
                id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL,
                source_asset_id VARCHAR(100) NOT NULL, target_ref TEXT NOT NULL,
                dependency_type VARCHAR(80) NOT NULL, criticality VARCHAR(20) NOT NULL,
                metadata_json TEXT NOT NULL, created_at TEXT NOT NULL,
                FOREIGN KEY(source_asset_id) REFERENCES assets(id)
            )
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS evidence (
                id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL,
                asset_id VARCHAR(100) NOT NULL, version_id VARCHAR(100), evidence_type VARCHAR(120) NOT NULL,
                source TEXT NOT NULL, result VARCHAR(30) NOT NULL, payload_json TEXT NOT NULL,
                provenance_hash VARCHAR(64) NOT NULL, previous_hash VARCHAR(64), occurred_at TEXT NOT NULL,
                recorded_at TEXT NOT NULL, FOREIGN KEY(asset_id) REFERENCES assets(id)
            )
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL,
                asset_id VARCHAR(100) NOT NULL, version_id VARCHAR(100), evaluation_type VARCHAR(120) NOT NULL,
                reliability REAL NOT NULL, critical_failures INTEGER NOT NULL,
                human_review_rate REAL NOT NULL, tool_failures INTEGER NOT NULL,
                evidence_ids_json TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL,
                FOREIGN KEY(asset_id) REFERENCES assets(id)
            )
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS policies (
                id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL,
                name VARCHAR(200) NOT NULL, version VARCHAR(80) NOT NULL, rules_json TEXT NOT NULL,
                created_at TEXT NOT NULL, UNIQUE(organization_id, name, version),
                FOREIGN KEY(organization_id) REFERENCES organizations(id)
            )
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS decisions (
                id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL,
                asset_id VARCHAR(100) NOT NULL, action VARCHAR(40) NOT NULL, decision VARCHAR(20) NOT NULL,
                reasons_json TEXT NOT NULL, context_json TEXT NOT NULL, created_at TEXT NOT NULL,
                FOREIGN KEY(asset_id) REFERENCES assets(id)
            )
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS trust_states (
                id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL,
                asset_id VARCHAR(100) NOT NULL, state VARCHAR(20) NOT NULL, score REAL NOT NULL,
                evidence_state VARCHAR(40) NOT NULL, dependency_state VARCHAR(40) NOT NULL,
                policy_state VARCHAR(40) NOT NULL, reliability REAL NOT NULL, critical_failures INTEGER NOT NULL,
                human_review_rate REAL NOT NULL, reasons_json TEXT NOT NULL, computed_at TEXT NOT NULL,
                epoch INTEGER NOT NULL, state_hash VARCHAR(64) NOT NULL,
                FOREIGN KEY(asset_id) REFERENCES assets(id)
            )
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL,
                event_type VARCHAR(120) NOT NULL, entity_type VARCHAR(80) NOT NULL, entity_id VARCHAR(100) NOT NULL,
                payload_json TEXT NOT NULL, previous_hash VARCHAR(64), event_hash VARCHAR(64) NOT NULL,
                request_id VARCHAR(100), created_at TEXT NOT NULL
            )
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS outbox (
                id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL,
                event_type VARCHAR(120) NOT NULL, aggregate_type VARCHAR(80) NOT NULL,
                aggregate_id VARCHAR(100) NOT NULL, payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL, published_at TEXT
            )
            """))
            c.execute(text("""
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                organization_id VARCHAR(80) NOT NULL, key_value VARCHAR(200) NOT NULL,
                request_hash VARCHAR(64) NOT NULL, response_json TEXT NOT NULL,
                status_code INTEGER NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(organization_id, key_value)
            )
            """))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_assets_org ON assets(organization_id)"))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_evidence_asset ON evidence(asset_id)"))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_eval_asset ON evaluations(asset_id)"))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_trust_asset ON trust_states(asset_id, epoch)"))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_org ON audit_log(organization_id, created_at)"))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox(published_at, created_at)"))
            c.execute(text("""CREATE TABLE IF NOT EXISTS directory_users (id VARCHAR(120) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL, user_name VARCHAR(255) NOT NULL, payload_json TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(organization_id,user_name))"""))
            c.execute(text("""CREATE TABLE IF NOT EXISTS service_integrations (id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL, provider VARCHAR(100) NOT NULL, config_json TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""))
            c.execute(text("""CREATE TABLE IF NOT EXISTS runtime_decisions (id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL, asset_id VARCHAR(100) NOT NULL, action VARCHAR(80) NOT NULL, decision VARCHAR(20) NOT NULL, latency_ms REAL NOT NULL, context_json TEXT NOT NULL, created_at TEXT NOT NULL)"""))
            c.execute(text("""CREATE TABLE IF NOT EXISTS slo_samples (id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80), success INTEGER NOT NULL, latency_ms REAL NOT NULL, created_at TEXT NOT NULL)"""))
            c.execute(text("""CREATE TABLE IF NOT EXISTS deployment_controls (id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL, asset_id VARCHAR(100) NOT NULL, environment VARCHAR(80) NOT NULL, desired_state VARCHAR(30) NOT NULL, enforcement VARCHAR(30) NOT NULL, updated_at TEXT NOT NULL, UNIQUE(organization_id,asset_id,environment))"""))
            c.execute(text("""CREATE TABLE IF NOT EXISTS policy_bindings (
                id VARCHAR(100) PRIMARY KEY, organization_id VARCHAR(80) NOT NULL,
                asset_id VARCHAR(100) NOT NULL, policy_id VARCHAR(100) NOT NULL,
                version_id VARCHAR(100), environment VARCHAR(80),
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(organization_id, asset_id, policy_id, version_id, environment)
            )"""))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_policy_bindings_asset ON policy_bindings(organization_id,asset_id)"))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_runtime_org ON runtime_decisions(organization_id,created_at)"))
            c.execute(text("CREATE INDEX IF NOT EXISTS idx_directory_org ON directory_users(organization_id)"))
            c.execute(text("""INSERT INTO system_meta(key,value) VALUES ('schema_version', :v)
                         ON CONFLICT(key) DO UPDATE SET value=:v"""), {"v": str(SCHEMA_VERSION)})
        self.ensure_local_org()

    def _id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:20]}"

    def ensure_local_org(self):
        with self.engine.begin() as c:
            exists = c.execute(text("SELECT 1 FROM organizations WHERE id='org_local'" )).first()
            if not exists:
                c.execute(text("INSERT INTO organizations VALUES ('org_local','Local Workspace',:t,'{}')"), {"t": now_iso()})

    def organization(self, org_id: str):
        with self.engine.connect() as c:
            r = c.execute(text("SELECT * FROM organizations WHERE id=:id"), {"id": org_id}).mappings().first()
        return dict(r) if r else None

    def create_organization(self, name: str, metadata: dict[str, Any] | None = None):
        oid = self._id("org")
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO organizations VALUES (:id,:name,:t,:m)"), {"id":oid,"name":name,"t":now_iso(),"m":canonical_json(metadata or {})})
        return self.organization(oid)

    @staticmethod
    def hash_api_key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def create_api_key(self, organization_id: str, scopes: list[str] | None = None) -> dict[str, Any]:
        raw = "aai_" + secrets.token_urlsafe(32)
        kid = self._id("key")
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO api_keys VALUES (:id,:o,:h,:p,:s,1,:t,NULL)"), {
                "id": kid, "o": organization_id, "h": self.hash_api_key(raw), "p": raw[:12],
                "s": canonical_json(scopes or ["control:read", "control:write"]), "t": now_iso()
            })
        return {"id": kid, "api_key": raw, "key_prefix": raw[:12], "scopes": scopes or ["control:read", "control:write"]}

    def revoke_api_key(self, org_id, key_id):
        with self.engine.begin() as c:c.execute(text("UPDATE api_keys SET active=0 WHERE id=:id AND organization_id=:o"),{"id":key_id,"o":org_id})
        self.audit(org_id,"credential.revoked","api_key",key_id,{"key_id":key_id})
        return {"revoked":True,"key_id":key_id}

    def api_keys(self, org_id):
        with self.engine.connect() as c: rows=c.execute(text("SELECT id,key_prefix,scopes_json,active,created_at,last_used_at FROM api_keys WHERE organization_id=:o ORDER BY created_at DESC"),{"o":org_id}).mappings().all()
        return [{**dict(r),"scopes":json.loads(r["scopes_json"])} for r in rows]

    def authenticate(self, raw_key: str):
        key_hash = self.hash_api_key(raw_key)
        with self.engine.begin() as c:
            r = c.execute(text("SELECT * FROM api_keys WHERE key_hash=:h AND active=1"), {"h": key_hash}).mappings().first()
            if r:
                c.execute(text("UPDATE api_keys SET last_used_at=:t WHERE id=:id"), {"t": now_iso(), "id": r["id"]})
                return {"organization_id": r["organization_id"], "key_id": r["id"], "scopes": json.loads(r["scopes_json"])}
        return None

    def audit(self, org_id: str, event_type: str, entity_type: str, entity_id: str, payload: Any, request_id: str | None = None):
        with self.engine.begin() as c:
            prev = c.execute(text("SELECT event_hash FROM audit_log WHERE organization_id=:o ORDER BY created_at DESC LIMIT 1"), {"o":org_id}).scalar()
            body = {"organization_id":org_id,"event_type":event_type,"entity_type":entity_type,"entity_id":entity_id,"payload":payload,"previous_hash":prev}
            event_hash = hashlib.sha256(canonical_json(body).encode()).hexdigest()
            c.execute(text("INSERT INTO audit_log VALUES (:id,:o,:et,:ty,:eid,:p,:ph,:eh,:rid,:t)"), {
                "id":self._id("aud"),"o":org_id,"et":event_type,"ty":entity_type,"eid":entity_id,
                "p":canonical_json(payload),"ph":prev,"eh":event_hash,"rid":request_id,"t":now_iso()
            })
            c.execute(text("INSERT INTO outbox VALUES (:id,:o,:et,:ty,:aid,:p,:t,NULL)"), {
                "id":self._id("evt"),"o":org_id,"et":event_type,"ty":entity_type,"aid":entity_id,"p":canonical_json(payload),"t":now_iso()
            })
        return event_hash

    def idempotent_get(self, org_id: str, key: str):
        with self.engine.connect() as c:
            r = c.execute(text("SELECT * FROM idempotency_keys WHERE organization_id=:o AND key_value=:k"), {"o":org_id,"k":key}).mappings().first()
        if not r: return None
        return {"request_hash":r["request_hash"],"response":json.loads(r["response_json"]),"status_code":r["status_code"]}

    def idempotent_put(self, org_id: str, key: str, request_hash: str, response: Any, status_code: int):
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO idempotency_keys VALUES (:o,:k,:h,:r,:s,:t)"), {
                "o":org_id,"k":key,"h":request_hash,"r":canonical_json(response),"s":status_code,"t":now_iso()
            })

    def _row(self, r, json_fields=()):
        d = dict(r)
        for f in json_fields:
            key = f + "_json"
            if key in d:
                d[f] = json.loads(d.pop(key))
        return d

    def create_asset(self, org_id, data, request_id=None):
        aid,t = self._id("ast"),now_iso()
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO assets VALUES (:id,:o,:n,:at,:ow,:e,:c,:m,:t,:t2)"), {
                "id":aid,"o":org_id,"n":data.name,"at":data.asset_type,"ow":data.owner,"e":data.environment,
                "c":data.criticality,"m":canonical_json(data.metadata),"t":t,"t2":t})
        self.audit(org_id,"asset.created","asset",aid,data.model_dump(),request_id)
        return self.get_asset(org_id,aid)

    def get_asset(self, org_id, aid):
        with self.engine.connect() as c:
            r=c.execute(text("SELECT * FROM assets WHERE id=:id AND organization_id=:o"),{"id":aid,"o":org_id}).mappings().first()
        return self._row(r,("metadata",)) if r else None

    def list_assets(self, org_id):
        with self.engine.connect() as c:
            rows=c.execute(text("SELECT * FROM assets WHERE organization_id=:o ORDER BY created_at DESC"),{"o":org_id}).mappings().all()
        return [self._row(r,("metadata",)) for r in rows]

    def create_version(self, org_id, aid, data, request_id=None):
        vid,t=self._id("ver"),now_iso()
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO versions VALUES (:id,:o,:a,:v,:m,:r,:md,:t)"),{"id":vid,"o":org_id,"a":aid,"v":data.version,"m":data.model_ref,"r":data.runtime_ref,"md":canonical_json(data.metadata),"t":t})
        self.audit(org_id,"version.created","version",vid,{"asset_id":aid,**data.model_dump()},request_id)
        return self.get_version(org_id,vid)

    def get_version(self, org_id, vid):
        with self.engine.connect() as c:r=c.execute(text("SELECT * FROM versions WHERE id=:id AND organization_id=:o"),{"id":vid,"o":org_id}).mappings().first()
        return self._row(r,("metadata",)) if r else None

    def versions(self, org_id, aid):
        with self.engine.connect() as c:rows=c.execute(text("SELECT * FROM versions WHERE asset_id=:a AND organization_id=:o ORDER BY created_at DESC"),{"a":aid,"o":org_id}).mappings().all()
        return [self._row(r,("metadata",)) for r in rows]

    def add_dependency(self, org_id, data, request_id=None):
        did,t=self._id("dep"),now_iso()
        with self.engine.begin() as c:c.execute(text("INSERT INTO dependencies VALUES (:id,:o,:s,:t,:dt,:c,:m,:at)"),{"id":did,"o":org_id,"s":data.source_asset_id,"t":data.target_ref,"dt":data.dependency_type,"c":data.criticality,"m":canonical_json(data.metadata),"at":t})
        self.audit(org_id,"dependency.created","dependency",did,data.model_dump(),request_id)
        return self.get_dependency(org_id,did)

    def get_dependency(self, org_id,did):
        with self.engine.connect() as c:r=c.execute(text("SELECT * FROM dependencies WHERE id=:id AND organization_id=:o"),{"id":did,"o":org_id}).mappings().first()
        return self._row(r,("metadata",)) if r else None

    def dependencies(self, org_id, aid):
        with self.engine.connect() as c:rows=c.execute(text("SELECT * FROM dependencies WHERE source_asset_id=:a AND organization_id=:o ORDER BY created_at DESC"),{"a":aid,"o":org_id}).mappings().all()
        return [self._row(r,("metadata",)) for r in rows]

    def all_dependencies(self, org_id):
        with self.engine.connect() as c:rows=c.execute(text("SELECT * FROM dependencies WHERE organization_id=:o"),{"o":org_id}).mappings().all()
        return [self._row(r,("metadata",)) for r in rows]

    def add_evidence(self, org_id, data, request_id=None):
        eid,t=self._id("evd"),now_iso(); occurred=data.occurred_at or t
        with self.engine.begin() as c:
            prev=c.execute(text("SELECT provenance_hash FROM evidence WHERE organization_id=:o AND asset_id=:a ORDER BY recorded_at DESC LIMIT 1"),{"o":org_id,"a":data.asset_id}).scalar()
            body={"asset_id":data.asset_id,"version_id":data.version_id,"evidence_type":data.evidence_type,"source":data.source,"result":data.result,"payload":data.payload,"occurred_at":occurred,"previous_hash":prev}
            ph=hashlib.sha256(canonical_json(body).encode()).hexdigest()
            c.execute(text("INSERT INTO evidence VALUES (:id,:o,:a,:v,:et,:s,:r,:p,:h,:ph,:oc,:rc)"),{"id":eid,"o":org_id,"a":data.asset_id,"v":data.version_id,"et":data.evidence_type,"s":data.source,"r":data.result,"p":canonical_json(data.payload),"h":ph,"ph":prev,"oc":occurred,"rc":t})
        self.audit(org_id,"evidence.recorded","evidence",eid,{**data.model_dump(),"provenance_hash":ph,"previous_hash":prev},request_id)
        return self.get_evidence(org_id,eid)

    def get_evidence(self, org_id,eid):
        with self.engine.connect() as c:r=c.execute(text("SELECT * FROM evidence WHERE id=:id AND organization_id=:o"),{"id":eid,"o":org_id}).mappings().first()
        return self._row(r,("payload",)) if r else None

    def evidence(self, org_id, aid):
        with self.engine.connect() as c:rows=c.execute(text("SELECT * FROM evidence WHERE asset_id=:a AND organization_id=:o ORDER BY recorded_at DESC"),{"a":aid,"o":org_id}).mappings().all()
        return [self._row(r,("payload",)) for r in rows]

    def add_evaluation(self, org_id, data, request_id=None):
        eid,t=self._id("eval"),now_iso()
        with self.engine.begin() as c:c.execute(text("INSERT INTO evaluations VALUES (:id,:o,:a,:v,:et,:rel,:cf,:hr,:tf,:ei,:d,:t)"),{"id":eid,"o":org_id,"a":data.asset_id,"v":data.version_id,"et":data.evaluation_type,"rel":data.reliability,"cf":data.critical_failures,"hr":data.human_review_rate,"tf":data.tool_failures,"ei":canonical_json(data.evidence_ids),"d":canonical_json(data.details),"t":t})
        self.audit(org_id,"evaluation.recorded","evaluation",eid,data.model_dump(),request_id)
        return self.get_evaluation(org_id,eid)

    def get_evaluation(self, org_id,eid):
        with self.engine.connect() as c:r=c.execute(text("SELECT * FROM evaluations WHERE id=:id AND organization_id=:o"),{"id":eid,"o":org_id}).mappings().first()
        return self._row(r,("evidence_ids","details")) if r else None

    def evaluations(self, org_id,aid):
        with self.engine.connect() as c:rows=c.execute(text("SELECT * FROM evaluations WHERE asset_id=:a AND organization_id=:o ORDER BY created_at DESC"),{"a":aid,"o":org_id}).mappings().all()
        return [self._row(r,("evidence_ids","details")) for r in rows]

    def create_policy(self, org_id,data,request_id=None):
        pid,t=self._id("pol"),now_iso()
        with self.engine.begin() as c:c.execute(text("INSERT INTO policies VALUES (:id,:o,:n,:v,:r,:t)"),{"id":pid,"o":org_id,"n":data.name,"v":data.version,"r":canonical_json(data.rules),"t":t})
        self.audit(org_id,"policy.created","policy",pid,data.model_dump(),request_id)
        return self.policy(org_id,pid)

    def policy(self,org_id,pid):
        with self.engine.connect() as c:r=c.execute(text("SELECT * FROM policies WHERE id=:id AND organization_id=:o"),{"id":pid,"o":org_id}).mappings().first()
        return self._row(r,("rules",)) if r else None

    def policies(self,org_id):
        with self.engine.connect() as c:rows=c.execute(text("SELECT * FROM policies WHERE organization_id=:o ORDER BY created_at DESC"),{"o":org_id}).mappings().all()
        return [self._row(r,("rules",)) for r in rows]

    def bind_policy(self, org_id, asset_id, policy_id, version_id=None, environment=None, request_id=None):
        if not self.get_asset(org_id, asset_id):
            raise KeyError("Asset not found")
        if not self.policy(org_id, policy_id):
            raise KeyError("Policy not found")
        bid,t=self._id("bind"),now_iso()
        with self.engine.begin() as c:
            existing=c.execute(text("""SELECT id FROM policy_bindings
                WHERE organization_id=:o AND asset_id=:a AND policy_id=:p
                  AND COALESCE(version_id,'')=COALESCE(:v,'')
                  AND COALESCE(environment,'')=COALESCE(:e,'')"""),
                {"o":org_id,"a":asset_id,"p":policy_id,"v":version_id,"e":environment}).scalar()
            if existing:
                bid=existing
                c.execute(text("UPDATE policy_bindings SET updated_at=:t WHERE id=:id AND organization_id=:o"),
                          {"t":t,"id":bid,"o":org_id})
            else:
                c.execute(text("""INSERT INTO policy_bindings
                    VALUES (:id,:o,:a,:p,:v,:e,:t,:t)"""),
                          {"id":bid,"o":org_id,"a":asset_id,"p":policy_id,"v":version_id,"e":environment,"t":t})
        self.audit(org_id,"policy.bound","policy_binding",bid,
                   {"asset_id":asset_id,"policy_id":policy_id,"version_id":version_id,"environment":environment},request_id)
        return self.policy_bindings(org_id, asset_id)

    def policy_bindings(self, org_id, asset_id):
        with self.engine.connect() as c:
            rows=c.execute(text("SELECT * FROM policy_bindings WHERE organization_id=:o AND asset_id=:a ORDER BY updated_at DESC"),
                           {"o":org_id,"a":asset_id}).mappings().all()
        return [dict(r) for r in rows]

    def effective_policy(self, org_id, asset_id, environment=None):
        for binding in self.policy_bindings(org_id, asset_id):
            if binding.get("environment") and environment and binding["environment"] != environment:
                continue
            policy=self.policy(org_id,binding["policy_id"])
            if policy:
                return policy
        return None

    def control_plane_snapshot(self, org_id, asset_id=None):
        assets=self.list_assets(org_id)
        if asset_id:
            assets=[a for a in assets if a["id"]==asset_id]
        rows=[]
        for asset in assets:
            versions=self.versions(org_id,asset["id"])
            trust=self.latest_trust(org_id,asset["id"])
            rows.append({
                "asset":asset,
                "versions":versions,
                "dependencies":self.dependencies(org_id,asset["id"]),
                "evidence_count":len(self.evidence(org_id,asset["id"])),
                "evaluation_count":len(self.evaluations(org_id,asset["id"])),
                "trust":trust,
                "policy_bindings":self.policy_bindings(org_id,asset["id"]),
                "deployment_control":self.deployment_control(org_id,asset["id"],asset.get("environment","production"))
            })
        return rows

    def add_decision(self,org_id,asset_id,action,decision,reasons,context,request_id=None):
        did,t=self._id("dec"),now_iso()
        with self.engine.begin() as c:c.execute(text("INSERT INTO decisions VALUES (:id,:o,:a,:ac,:d,:r,:c,:t)"),{"id":did,"o":org_id,"a":asset_id,"ac":action,"d":decision,"r":canonical_json(reasons),"c":canonical_json(context),"t":t})
        self.audit(org_id,"decision.issued","decision",did,{"asset_id":asset_id,"action":action,"decision":decision,"reasons":reasons,"context":context},request_id)
        return {"id":did,"asset_id":asset_id,"action":action,"decision":decision,"reasons":reasons,"context":context,"created_at":t}

    def save_trust(self,org_id,trust,request_id=None):
        tid,t=self._id("trs"),trust["computed_at"]
        payload={k:v for k,v in trust.items() if k!="state_hash"}
        sh=hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        with self.engine.begin() as c:c.execute(text("INSERT INTO trust_states VALUES (:id,:o,:a,:s,:sc,:es,:ds,:ps,:r,:cf,:hr,:re,:ct,:ep,:h)"),{"id":tid,"o":org_id,"a":trust["asset_id"],"s":trust["state"],"sc":trust["score"],"es":trust["evidence_state"],"ds":trust["dependency_state"],"ps":trust["policy_state"],"r":trust["reliability"],"cf":trust["critical_failures"],"hr":trust["human_review_rate"],"re":canonical_json(trust["reasons"]),"ct":t,"ep":trust["epoch"],"h":sh})
        trust={**trust,"state_hash":sh}
        self.audit(org_id,"trust.changed","trust_state",tid,trust,request_id)
        return trust

    def latest_trust(self,org_id,aid):
        with self.engine.connect() as c:r=c.execute(text("SELECT * FROM trust_states WHERE asset_id=:a AND organization_id=:o ORDER BY epoch DESC LIMIT 1"),{"a":aid,"o":org_id}).mappings().first()
        return self._row(r,("reasons",)) if r else None

    def audit_events(self,org_id,limit=100):
        with self.engine.connect() as c:rows=c.execute(text("SELECT * FROM audit_log WHERE organization_id=:o ORDER BY created_at DESC LIMIT :n"),{"o":org_id,"n":limit}).mappings().all()
        return [self._row(r,("payload",)) for r in rows]

    def verify_audit_chain(self,org_id):
        with self.engine.connect() as c:rows=c.execute(text("SELECT * FROM audit_log WHERE organization_id=:o ORDER BY created_at ASC"),{"o":org_id}).mappings().all()
        prev=None
        for r in rows:
            body={"organization_id":org_id,"event_type":r["event_type"],"entity_type":r["entity_type"],"entity_id":r["entity_id"],"payload":json.loads(r["payload_json"]),"previous_hash":r["previous_hash"]}
            expected=hashlib.sha256(canonical_json(body).encode()).hexdigest()
            if r["previous_hash"]!=prev or not hmac.compare_digest(expected,r["event_hash"]):
                return {"valid":False,"events_checked":len(rows),"failed_event_id":r["id"]}
            prev=r["event_hash"]
        return {"valid":True,"events_checked":len(rows),"failed_event_id":None}

    def pending_outbox(self,org_id,limit=100):
        with self.engine.connect() as c:rows=c.execute(text("SELECT * FROM outbox WHERE organization_id=:o AND published_at IS NULL ORDER BY created_at LIMIT :n"),{"o":org_id,"n":limit}).mappings().all()
        return [self._row(r,("payload",)) for r in rows]

    def record_runtime_decision(self, org_id, asset_id, action, decision, latency_ms, context, request_id=None):
        rid,t=self._id("run"),now_iso()
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO runtime_decisions VALUES (:id,:o,:a,:ac,:d,:l,:c,:t)"),{"id":rid,"o":org_id,"a":asset_id,"ac":action,"d":decision,"l":latency_ms,"c":canonical_json(context),"t":t})
        self.audit(org_id,"runtime.decision","runtime_decision",rid,{"asset_id":asset_id,"action":action,"decision":decision,"latency_ms":latency_ms},request_id)
        return {"id":rid,"asset_id":asset_id,"action":action,"decision":decision,"latency_ms":latency_ms,"created_at":t}

    def runtime_decisions(self, org_id, limit=100):
        with self.engine.connect() as c: rows=c.execute(text("SELECT * FROM runtime_decisions WHERE organization_id=:o ORDER BY created_at DESC LIMIT :n"),{"o":org_id,"n":limit}).mappings().all()
        return [self._row(r,("context",)) for r in rows]

    def upsert_deployment_control(self, org_id, asset_id, environment, desired_state, enforcement):
        cid,t=self._id("ctl"),now_iso()
        with self.engine.begin() as c:
            existing=c.execute(text("SELECT id FROM deployment_controls WHERE organization_id=:o AND asset_id=:a AND environment=:e"),{"o":org_id,"a":asset_id,"e":environment}).scalar()
            if existing: c.execute(text("UPDATE deployment_controls SET desired_state=:s,enforcement=:f,updated_at=:t WHERE id=:id"),{"s":desired_state,"f":enforcement,"t":t,"id":existing}); cid=existing
            else: c.execute(text("INSERT INTO deployment_controls VALUES (:id,:o,:a,:e,:s,:f,:t)"),{"id":cid,"o":org_id,"a":asset_id,"e":environment,"s":desired_state,"f":enforcement,"t":t})
        self.audit(org_id,"deployment.control.changed","deployment_control",cid,{"asset_id":asset_id,"environment":environment,"desired_state":desired_state,"enforcement":enforcement})
        return self.deployment_control(org_id,asset_id,environment)

    def deployment_control(self,org_id,asset_id,environment):
        with self.engine.connect() as c:r=c.execute(text("SELECT * FROM deployment_controls WHERE organization_id=:o AND asset_id=:a AND environment=:e"),{"o":org_id,"a":asset_id,"e":environment}).mappings().first()
        return dict(r) if r else None

    def directory_users(self,org_id):
        with self.engine.connect() as c: rows=c.execute(text("SELECT * FROM directory_users WHERE organization_id=:o ORDER BY created_at"),{"o":org_id}).mappings().all()
        return [self._row(r,("payload",)) for r in rows]

    def upsert_directory_user(self,org_id,user_id,user_name,payload):
        t=now_iso()
        with self.engine.begin() as c:
            exists=c.execute(text("SELECT id FROM directory_users WHERE id=:id"),{"id":user_id}).scalar()
            if exists: c.execute(text("UPDATE directory_users SET user_name=:u,payload_json=:p,updated_at=:t,active=1 WHERE id=:id AND organization_id=:o"),{"u":user_name,"p":canonical_json(payload),"t":t,"id":user_id,"o":org_id})
            else: c.execute(text("INSERT INTO directory_users VALUES (:id,:o,:u,:p,1,:t,:t)"),{"id":user_id,"o":org_id,"u":user_name,"p":canonical_json(payload),"t":t})
        return self.directory_user(org_id,user_id)

    def directory_user(self,org_id,user_id):
        with self.engine.connect() as c:r=c.execute(text("SELECT * FROM directory_users WHERE id=:id AND organization_id=:o"),{"id":user_id,"o":org_id}).mappings().first()
        return self._row(r,("payload",)) if r else None

    def delete_directory_user(self,org_id,user_id):
        with self.engine.begin() as c:c.execute(text("UPDATE directory_users SET active=0,updated_at=:t WHERE id=:id AND organization_id=:o"),{"t":now_iso(),"id":user_id,"o":org_id})

    def add_slo_sample(self,org_id,success,latency_ms):
        sid,t=self._id("slo"),now_iso()
        with self.engine.begin() as c:c.execute(text("INSERT INTO slo_samples VALUES (:id,:o,:s,:l,:t)"),{"id":sid,"o":org_id,"s":1 if success else 0,"l":latency_ms,"t":t})

    def slo_report(self,org_id=None,limit=10000):
        q="SELECT success,latency_ms FROM slo_samples WHERE (organization_id=:o OR organization_id IS NULL) ORDER BY created_at DESC LIMIT :n"; params={"o":org_id,"n":limit}
        with self.engine.connect() as c: rows=c.execute(text(q),params).mappings().all()
        if not rows:return {"availability":1.0,"latency_p95_ms":0.0,"sample_count":0}
        vals=sorted(float(r["latency_ms"]) for r in rows); idx=min(len(vals)-1,max(0,int(len(vals)*.95)-1)); return {"availability":sum(int(r["success"]) for r in rows)/len(rows),"latency_p95_ms":vals[idx],"sample_count":len(rows)}

    def pending_outbox_all(self,limit=100):
        with self.engine.connect() as c: rows=c.execute(text("SELECT * FROM outbox WHERE published_at IS NULL ORDER BY created_at LIMIT :n"),{"n":limit}).mappings().all()
        return [self._row(r,("payload",)) for r in rows]

    def mark_outbox_published(self,event_id):
        with self.engine.begin() as c:c.execute(text("UPDATE outbox SET published_at=:t WHERE id=:id"),{"t":now_iso(),"id":event_id})
