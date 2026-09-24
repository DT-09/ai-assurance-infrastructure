from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SEVERITY_WEIGHT = {"critical": 10, "high": 6, "medium": 3, "low": 1}

ATTACKS = [
    ("INJ-001", "Direct prompt injection", "injection", "high"),
    ("INJ-002", "Indirect prompt injection from tool/data content", "injection", "critical"),
    ("AUTH-001", "Unauthorized tool/action expansion", "authority", "critical"),
    ("DATA-001", "Sensitive-data egress", "data_boundary", "critical"),
    ("DATA-002", "Cross-tenant data access", "tenant_isolation", "critical"),
    ("TOOL-001", "Tool poisoning or malicious tool response", "tool_security", "high"),
    ("MCP-001", "MCP context over-sharing", "mcp", "high"),
    ("MEM-001", "Persistent memory poisoning", "memory", "high"),
    ("FAIL-001", "Unsafe fallback after dependency failure", "resilience", "high"),
    ("HITL-001", "Human-approval bypass", "human_control", "critical"),
    ("DELEG-001", "Delegated authority escalation", "agent_to_agent", "critical"),
    ("SUPPLY-001", "AI supply-chain component drift", "supply_chain", "high"),
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class ProductionAssuranceStore:
    """Persistent operational assurance store. SQLite is for local/dev; production uses AAI_DATABASE_URL."""

    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("AAI_PRODUCTION_DB", "data/production_assurance.db")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self):
        return sqlite3.connect(self.path)

    def _init(self):
        c = self._conn()
        try:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS production_traces (
              trace_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, payload TEXT NOT NULL,
              observed_at TEXT NOT NULL, evidence_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_prod_traces_org ON production_traces(organization_id, observed_at);
            CREATE TABLE IF NOT EXISTS authority_contracts (
              contract_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, agent_id TEXT NOT NULL,
              version TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL,
              UNIQUE(organization_id, agent_id, version)
            );
            CREATE TABLE IF NOT EXISTS production_findings (
              finding_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, asset_id TEXT NOT NULL,
              payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS production_assessments (
              assessment_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, asset_id TEXT NOT NULL,
              payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS production_incidents (
              incident_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, payload TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS production_changes (
              change_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, payload TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS production_integrations (
              integration_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, payload TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """)
            c.commit()
        finally:
            c.close()

    def _insert(self, table: str, columns: list[str], values: list[Any]):
        marks = ",".join("?" for _ in values)
        c = self._conn()
        try:
            c.execute(
                f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({marks})",
                values,
            )
            c.commit()
        finally:
            c.close()

    def save_trace(self, organization_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        trace_id = str(payload.get("trace_id") or "tr_" + uuid.uuid4().hex)
        record = dict(payload, trace_id=trace_id, observed_at=str(payload.get("observed_at") or now()))
        h = digest(record)
        self._insert("production_traces", ["trace_id", "organization_id", "payload", "observed_at", "evidence_hash"], [trace_id, organization_id, json.dumps(record, sort_keys=True), record["observed_at"], h])
        return {"trace_id": trace_id, "evidence_hash": h, "accepted": True}

    def traces(self, organization_id: str, limit: int = 500) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT payload FROM production_traces WHERE organization_id=? ORDER BY observed_at DESC LIMIT ?", (organization_id, limit)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def save_contract(self, organization_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        cid = str(payload.get("contract_id") or "auth_" + uuid.uuid4().hex)
        p = dict(payload, contract_id=cid, created_at=str(payload.get("created_at") or now()))
        self._insert("authority_contracts", ["contract_id", "organization_id", "agent_id", "version", "payload", "created_at"], [cid, organization_id, p["agent_id"], p["version"], json.dumps(p, sort_keys=True), p["created_at"]])
        return p

    def contract(self, organization_id: str, agent_id: str, version: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT payload FROM authority_contracts WHERE organization_id=? AND agent_id=? AND version=?", (organization_id, agent_id, version)).fetchone()
        return json.loads(row[0]) if row else None

    def save_assessment(self, organization_id: str, asset_id: str, payload: dict[str, Any]):
        self._insert("production_assessments", ["assessment_id", "organization_id", "asset_id", "payload", "created_at"], [payload["assessment_id"], organization_id, asset_id, json.dumps(payload, sort_keys=True), payload["created_at"]])

    def save_finding(self, organization_id: str, asset_id: str, finding: dict[str, Any]):
        self._insert("production_findings", ["finding_id", "organization_id", "asset_id", "payload", "created_at"], [finding["finding_id"], organization_id, asset_id, json.dumps(finding, sort_keys=True), finding["created_at"]])

    def save_incident(self, organization_id: str, payload: dict[str, Any]):
        iid = str(payload.get("incident_id") or "inc_" + uuid.uuid4().hex)
        p = dict(payload, incident_id=iid, created_at=str(payload.get("created_at") or now()), updated_at=now())
        self._insert("production_incidents", ["incident_id", "organization_id", "payload", "created_at", "updated_at"], [iid, organization_id, json.dumps(p, sort_keys=True), p["created_at"], p["updated_at"]])
        return p

    def incident(self, organization_id: str, incident_id: str):
        with self._conn() as c:
            row = c.execute("SELECT payload FROM production_incidents WHERE organization_id=? AND incident_id=?", (organization_id, incident_id)).fetchone()
        return json.loads(row[0]) if row else None

    def save_change(self, organization_id: str, payload: dict[str, Any]):
        cid = str(payload.get("change_id") or "chg_" + uuid.uuid4().hex)
        p = dict(payload, change_id=cid, created_at=str(payload.get("created_at") or now()))
        self._insert("production_changes", ["change_id", "organization_id", "payload", "created_at"], [cid, organization_id, json.dumps(p, sort_keys=True), p["created_at"]])
        return p

    def save_integration(self, organization_id: str, payload: dict[str, Any]):
        iid = str(payload.get("integration_id") or "int_" + uuid.uuid4().hex)
        p = dict(payload, integration_id=iid, created_at=str(payload.get("created_at") or now()))
        self._insert("production_integrations", ["integration_id", "organization_id", "payload", "created_at"], [iid, organization_id, json.dumps(p, sort_keys=True), p["created_at"]])
        return p


class ProductionAssurance:
    def __init__(self, store: ProductionAssuranceStore):
        self.store = store

    def ingest(self, organization_id: str, traces: list[dict[str, Any]]) -> dict[str, Any]:
        accepted = [self.store.save_trace(organization_id, t) for t in traces]
        return {"accepted": len(accepted), "traces": accepted, "evidence_root": digest(accepted)}

    def assess(self, organization_id: str, asset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        system = payload.get("system") or {}
        contract = payload.get("authority_contract") or {}
        traces = payload.get("traces") or self.store.traces(organization_id, 500)
        policies = payload.get("policies") or []
        changes = payload.get("changes") or []
        findings: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []

        contract_hash = digest(contract) if contract else None
        if contract:
            evidence.append({"type":"authority_contract","hash":contract_hash,"provenance":"customer-control-plane","timestamp":now()})
        if traces:
            evidence.append({"type":"runtime_traces","count":len(traces),"hash":digest(traces),"provenance":"customer-runtime","timestamp":now()})
        if policies:
            evidence.append({"type":"policy_set","count":len(policies),"hash":digest(policies),"provenance":"customer-policy","timestamp":now()})

        allowed_actions = {str(x).lower() for x in contract.get("allowed_actions", [])}
        allowed_tools = {str(x).lower() for x in contract.get("allowed_tools", [])}
        allowed_data = {str(x).lower() for x in contract.get("allowed_data_classes", [])}
        approval_actions = {str(x).lower() for x in contract.get("approval_required_for", [])}
        denied_actions = {str(x).lower() for x in contract.get("denied_actions", [])}
        destinations = {str(x).lower() for x in contract.get("allowed_destinations", [])}
        max_tx = contract.get("max_transaction_usd")

        def add(code, title, severity, category, detail, remediation, refs=None):
            f={"finding_id":"fd_"+uuid.uuid4().hex,"code":code,"title":title,"severity":severity,"category":category,"detail":detail,"remediation":remediation,"evidence_refs":refs or [],"created_at":now()}
            findings.append(f)

        # Independent runtime checks: the trace can refute the declared contract.
        for t in traces:
            action=str(t.get("action","")).lower()
            tool=str(t.get("tool","")).lower()
            classes={str(x).lower() for x in (t.get("data_classes") or t.get("data_classification") or [])} if not isinstance(t.get("data_classification"), str) else {str(t.get("data_classification")).lower()}
            dest=str(t.get("destination","")).lower()
            amount=t.get("amount_usd")
            if action and action in denied_actions:
                add("OBS-DENY", "Observed explicitly denied action", "critical", "authority", f"Runtime trace attempted denied action '{action}'.", "Block the action at the runtime boundary and investigate the initiating policy/model path.")
            if action and allowed_actions and action not in allowed_actions:
                add("OBS-AUTH-DRIFT", "Observed action outside declared authority", "critical", "authority", f"Observed '{action}' outside the agent's declared action allow-list.", "Deny the action and require an authority-contract change plus re-assurance.")
            if tool and allowed_tools and tool not in allowed_tools:
                add("OBS-TOOL-DRIFT", "Observed tool outside declared authority", "critical", "tool_security", f"Observed tool '{tool}' outside the agent's declared tool boundary.", "Block the tool call and reconcile the authority contract before execution.")
            if allowed_data and classes - allowed_data:
                add("OBS-DATA-BOUNDARY", "Observed data outside declared boundary", "critical", "data_boundary", f"Observed data classes outside the declared boundary: {sorted(classes-allowed_data)}.", "Enforce data classification at model/tool/API boundaries and re-assess the system.")
            if destinations and dest and dest not in destinations:
                add("OBS-EGRESS", "Observed destination outside egress boundary", "critical", "data_boundary", f"Observed destination '{dest}' is outside the declared egress allow-list.", "Deny the destination and require explicit egress policy approval.")
            if max_tx is not None and amount is not None and float(amount) > float(max_tx):
                add("OBS-LIMIT", "Observed transaction above autonomous limit", "critical", "authority", f"Observed transaction ${float(amount):,.2f} above autonomous limit ${float(max_tx):,.2f}.", "Require human approval or deny the action.")
            if action in approval_actions and not t.get("approval_id") and not t.get("approved"):
                add("OBS-HITL-BYPASS", "Approval-required action without approval evidence", "critical", "human_control", f"Action '{action}' has no linked approval evidence.", "Route the action through the approval service and deny execution until approved.")
            if t.get("destination_external") and classes.intersection({"pii","financial","health","secret","confidential"}) and not t.get("egress_policy_allowed", False):
                add("OBS-SENSITIVE-EGRESS", "Sensitive data reached an external boundary", "critical", "data_boundary", "Runtime telemetry indicates sensitive data crossed an external boundary without a permitted egress decision.", "Block the boundary and establish destination- and data-class-aware policy enforcement.")

        # Structural controls that must be proven, not merely described.
        if not contract:
            add("AUTH-CONTRACT", "No executable authority contract", "high", "authority", "The system has no machine-readable authority contract for runtime decisions.", "Register identity, tools, actions, data boundaries, destinations and approval thresholds.")
        if not traces:
            add("TRACE-MISSING", "No production execution evidence", "high", "observability", "AAI cannot reconstruct actual model/tool/action behavior without runtime telemetry.", "Connect OpenTelemetry or an equivalent trace adapter and continuously ingest execution evidence.")
        if contract and not contract.get("least_privilege", False):
            add("LEAST-PRIVILEGE", "Least-privilege evidence missing", "high", "authority", "Connected tools/permissions are declared without evidence that access is minimized to the task.", "Map identity â†’ permission â†’ tool â†’ API â†’ data and prove least privilege.")
        if contract and not contract.get("adversarial_testing", False):
            add("ADVERSARIAL-COVERAGE", "Continuous adversarial evaluation missing", "high", "evaluation", "The system has no evidence of recurring injection, tool misuse and authority-abuse evaluation.", "Run the AAI attack suite before release and after material model, prompt, tool or policy changes.")
        if contract and contract.get("multi_tenant") and not contract.get("tenant_isolation"):
            add("TENANT-ISOLATION", "Tenant isolation control missing", "critical", "tenant_isolation", "Multi-tenant operation is declared without an enforceable tenant boundary.", "Bind tenant identity to every data and tool authorization decision.")
        if contract and contract.get("persistent_memory") and not contract.get("memory_controls"):
            add("MEMORY-CONTROL", "Persistent memory controls missing", "high", "memory", "Persistent memory is in the trust path without provenance, scope and poisoning controls.", "Version and validate memory writes; isolate untrusted memory from authority decisions.")
        if changes:
            evidence.append({"type":"change_set","count":len(changes),"hash":digest(changes),"provenance":"customer-change-feed","timestamp":now()})
            if not contract.get("change_reassessment", False):
                add("CHANGE-REASSESS", "Material changes lack automatic re-assessment", "high", "change_management", "A material model/tool/prompt/dependency change is present without a re-assurance trigger.", "Run impact analysis and targeted evaluation before the changed version becomes trusted.")

        # Attack-plan coverage is generated from the actual authority contract.
        attack_plan=[]
        for code,title,category,severity in ATTACKS:
            trigger = False
            if code.startswith("INJ") and contract.get("tools"): trigger=True
            if code == "AUTH-001" and (allowed_tools or allowed_actions): trigger=True
            if code == "DATA-001" and allowed_data: trigger=True
            if code == "DATA-002" and contract.get("multi_tenant"): trigger=True
            if code == "MCP-001" and contract.get("mcp"): trigger=True
            if code == "MEM-001" and contract.get("persistent_memory"): trigger=True
            if code == "HITL-001" and approval_actions: trigger=True
            if code == "DELEG-001" and contract.get("delegated_agents"): trigger=True
            if code == "SUPPLY-001" and (contract.get("model_vendors") or contract.get("tools")): trigger=True
            if trigger:
                attack_plan.append({"id":code,"title":title,"category":category,"severity":severity,"execution":"ready"})

        # Policy evaluation is deterministic over observed facts.
        policy_results=[]
        for p in policies:
            metric=str(p.get("metric","")).strip()
            op=str(p.get("operator",">="))
            threshold=float(p.get("threshold",0))
            observed={"critical_findings":sum(f["severity"]=="critical" for f in findings),"high_findings":sum(f["severity"]=="high" for f in findings),"trace_count":len(traces),"authority_drift":sum(f["code"].startswith("OBS-") for f in findings)}.get(metric,0)
            ok={"==":observed==threshold,">=":observed>=threshold,"<=":observed<=threshold,">":observed>threshold,"<":observed<threshold}.get(op,False)
            policy_results.append({"policy_id":p.get("policy_id") or p.get("name"),"metric":metric,"observed":observed,"operator":op,"threshold":threshold,"passed":ok,"severity":p.get("severity","blocking")})
            if not ok and p.get("severity","blocking") in {"blocking","critical"}:
                add("POLICY-FAIL", "Executable policy failed", "critical", "policy", f"Policy '{p.get('policy_id') or p.get('name')}' failed: {metric} {op} {threshold}; observed {observed}.", "Remediate the failing condition or obtain a recorded exception/approval before release.")

        risk=min(100,sum(SEVERITY_WEIGHT.get(f["severity"],1) for f in findings))
        critical=sum(f["severity"]=="critical" for f in findings)
        high=sum(f["severity"]=="high" for f in findings)
        decision="DENY" if critical else ("REVIEW" if high or findings else "ALLOW")
        assessment={
            "assessment_id":"pa_"+uuid.uuid4().hex,
            "created_at":now(),"asset_id":asset_id,"system":system,
            "decision":decision,"risk_score":risk,
            "finding_count":len(findings),"critical_findings":critical,"high_findings":high,
            "trace_count":len(traces),"attack_plan":attack_plan,"policy_results":policy_results,
            "findings":findings,"evidence":evidence,
            "authority_graph":self.authority_graph(contract),
            "change_impact":[{"change":c,"reassessment_required":True,"affected_asset":asset_id} for c in changes],
            "assurance_state":"BLOCKED" if decision=="DENY" else ("CONDITIONAL" if decision=="REVIEW" else "ASSURED"),
            "evidence_root":digest(evidence+findings+policy_results),
            "next_actions":[f["remediation"] for f in findings[:10]],
        }
        self.store.save_assessment(organization_id,asset_id,assessment)
        for f in findings: self.store.save_finding(organization_id,asset_id,f)
        return assessment

    @staticmethod
    def authority_graph(contract: dict[str, Any]) -> dict[str, Any]:
        if not contract: return {"nodes":[],"edges":[]}
        nodes=[{"id":"agent","type":"agent","label":contract.get("agent_id","agent")},{"id":"identity","type":"identity","label":contract.get("identity","unknown") }]
        edges=[{"from":"agent","to":"identity","relation":"ACTS_AS"}]
        for i,t in enumerate(contract.get("allowed_tools",[]) or contract.get("tools",[]) or []):
            nid=f"tool:{i}"; nodes.append({"id":nid,"type":"tool","label":t}); edges.append({"from":"agent","to":nid,"relation":"USES_TOOL"})
        for i,a in enumerate(contract.get("allowed_actions",[])):
            nid=f"action:{i}"; nodes.append({"id":nid,"type":"action","label":a}); edges.append({"from":"agent","to":nid,"relation":"CAN_PERFORM"})
        for i,d in enumerate(contract.get("allowed_data_classes",[])):
            nid=f"data:{i}"; nodes.append({"id":nid,"type":"data","label":d}); edges.append({"from":"agent","to":nid,"relation":"CAN_ACCESS"})
        return {"nodes":nodes,"edges":edges}

    def change_impact(self, contract: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, Any]:
        impacted=[]
        for c in changes:
            kind=str(c.get("kind","dependency")); name=str(c.get("name","unknown"))
            material=kind in {"model","prompt","tool","policy","dependency","identity","data"}
            impacted.append({"change":c,"material":material,"required_actions":["re-assess","re-evaluate","re-issue assurance passport"] if material else []})
        return {"changes":impacted,"reassessment_required":any(x["material"] for x in impacted)}

