from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Callable

from .models import ActionRequest, AuthorityContract, RuntimeDecision, RuntimeDecisionRecord


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


class RuntimeGateway:
    """Deterministic policy boundary for consequential AI actions."""

    VERSION = "runtime-gateway-2.0.0"

    def __init__(self, store=None):
        self.store = store
        self._contracts: dict[tuple[str, str], AuthorityContract] = {}
        self._approvals: set[str] = set()

    def register_contract(self, contract: AuthorityContract) -> dict[str, Any]:
        if not contract.agent_id or not contract.version:
            raise ValueError("agent_id and version are required")
        key = (contract.agent_id, contract.version)
        self._contracts[key] = contract
        if self.store:
            self.store.save_contract(contract)
        return {"registered": True, "contract_hash": digest(contract.to_dict()), "contract": contract.to_dict()}

    def get_contract(self, agent_id: str, version: str) -> AuthorityContract | None:
        value = self._contracts.get((agent_id, version))
        if value is not None:
            return value
        if self.store:
            value = self.store.get_contract(agent_id, version)
            if value is not None:
                self._contracts[(agent_id, version)] = value
        return value

    def authorize(self, request: ActionRequest, *, approval_id: str | None = None) -> RuntimeDecisionRecord:
        contract = self.get_contract(request.agent_id, request.agent_version)
        reasons: list[str] = []
        if not contract:
            decision = RuntimeDecision.BLOCK
            reasons.append("No registered authority contract exists for this agent version.")
            contract_hash = digest({"missing": [request.agent_id, request.agent_version]})
            policy_version = "none"
        else:
            contract_hash = digest(contract.to_dict())
            policy_version = contract.contract_version
            action = request.action.lower()
            tool = request.tool.lower()
            if action in contract.denied_actions:
                reasons.append(f"Action '{request.action}' is explicitly denied.")
            if contract.allowed_actions and action not in contract.allowed_actions:
                reasons.append(f"Action '{request.action}' is outside declared authority.")
            if contract.allowed_tools and tool not in contract.allowed_tools:
                reasons.append(f"Tool '{request.tool}' is outside declared authority.")
            if request.data_classes and contract.allowed_data_classes and not request.data_classes.issubset(contract.allowed_data_classes):
                reasons.append("Requested data classification exceeds the agent's declared data boundary.")
            if request.destination and contract.allowed_destinations and request.destination.lower() not in contract.allowed_destinations:
                reasons.append(f"Destination '{request.destination}' is outside the declared egress boundary.")
            if contract.max_transaction_usd is not None and request.amount_usd is not None and request.amount_usd > contract.max_transaction_usd:
                reasons.append(f"Transaction amount ${request.amount_usd:,.2f} exceeds autonomous limit ${contract.max_transaction_usd:,.2f}.")
            approval_needed = action in contract.approval_required_for or (contract.max_transaction_usd is not None and request.amount_usd is not None and request.amount_usd > contract.max_transaction_usd)
            if reasons:
                decision = RuntimeDecision.BLOCK
            elif approval_needed and approval_id not in self._approvals:
                decision = RuntimeDecision.REQUIRE_APPROVAL
                reasons.append("A named human approval is required before execution.")
            else:
                decision = RuntimeDecision.ALLOW
        evidence_payload = {"request": request.to_dict(), "decision": decision.value, "reasons": reasons, "contract_hash": contract_hash, "policy_version": policy_version}
        record = RuntimeDecisionRecord(
            decision_id="dec_" + uuid.uuid4().hex,
            decision=decision,
            action=request,
            reasons=reasons,
            policy_version=policy_version,
            contract_hash=contract_hash,
            evidence_hash=digest(evidence_payload),
        )
        if self.store:
            self.store.save_decision(record)
        return record

    def approve(self, decision_id: str, approver: str) -> dict[str, Any]:
        if not approver.strip():
            raise ValueError("approver is required")
        self._approvals.add(decision_id)
        if self.store:
            self.store.save_approval(decision_id, approver)
        return {"approved": True, "decision_id": decision_id, "approver": approver}

    def execute(self, request: ActionRequest, executor: Callable[[ActionRequest], Any], *, approval_id: str | None = None) -> dict[str, Any]:
        first = self.authorize(request, approval_id=approval_id)
        if first.decision != RuntimeDecision.ALLOW:
            return {"executed": False, "decision": first.to_dict()}
        try:
            result = executor(request)
            outcome = {"status": "executed", "result": result}
        except Exception as exc:
            outcome = {"status": "failed", "error": str(exc)}
        if self.store:
            self.store.save_outcome(first.decision_id, outcome)
        return {"executed": outcome["status"] == "executed", "decision": first.to_dict(), "outcome": outcome}


def generate_attack_paths(contract: AuthorityContract) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []
    if "email" in contract.allowed_tools and contract.allowed_data_classes & {"pii", "financial", "secret"}:
        paths.append({"id": "EGRESS-001", "name": "Sensitive data → external email", "risk": "critical", "precondition": "sensitive data reaches external destination"})
    if "payments" in contract.allowed_tools and contract.max_transaction_usd is not None:
        paths.append({"id": "AUTH-001", "name": "Payment authority escalation", "risk": "critical", "precondition": "transaction exceeds autonomous limit"})
    if "crm" in contract.allowed_tools:
        paths.append({"id": "DATA-001", "name": "CRM data boundary crossing", "risk": "high", "precondition": "agent requests data outside declared classification"})
    if contract.approval_required_for:
        paths.append({"id": "HUMAN-001", "name": "Approval bypass", "risk": "high", "precondition": "consequential action attempted without approval"})
    if not contract.denied_actions:
        paths.append({"id": "AUTH-DRIFT-001", "name": "Undeclared action expansion", "risk": "high", "precondition": "agent attempts an action outside allow-list"})
    return paths
