from fastapi import FastAPI, HTTPException

from app.models import QualificationResult

from .audit import AuditLog
from .control import evaluate_control
from .engine import evaluate_action
from .models import AgentAction, AuditEvent, Policy
from .registry import QualificationRegistry


app = FastAPI(
    title="AI Agent Control Gateway",
    version="0.4.0",
)

audit_log = AuditLog()
registry = QualificationRegistry()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-agent-control-gateway",
        "version": "0.4.0",
    }


@app.post("/api/gateway/evaluate")
def evaluate(
    action: AgentAction,
    policy: Policy,
):
    result = evaluate_action(
        action=action,
        policy=policy,
    )

    audit_log.record(
        AuditEvent(
            agent_id=action.agent_id,
            tool=action.tool,
            action=action.action,
            decision=result.decision,
            reason=result.reason,
        )
    )

    return result


@app.post("/api/agents/{agent_id}/qualification")
def set_qualification(
    agent_id: str,
    qualification: QualificationResult,
):
    registry.set(
        agent_id=agent_id,
        result=qualification,
    )

    return {
        "status": "stored",
        "agent_id": agent_id,
        "verdict": qualification.verdict,
    }


@app.get("/api/agents/{agent_id}")
def get_agent(agent_id: str):
    qualification = registry.get(agent_id)

    if qualification is None:
        raise HTTPException(
            status_code=404,
            detail=f"No qualification record found for agent '{agent_id}'",
        )

    return {
        "agent_id": agent_id,
        "qualification": qualification,
    }


@app.get("/api/agents")
def get_agents():
    records = registry.all()

    return {
        "agents": [
            {
                "agent_id": agent_id,
                "verdict": qualification.verdict,
            }
            for agent_id, qualification in records.items()
        ],
        "count": len(records),
    }


@app.post("/api/control/evaluate")
def control_evaluate(
    action: AgentAction,
    policy: Policy,
):
    qualification = registry.get(action.agent_id)

    if qualification is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No qualification record found for agent "
                f"'{action.agent_id}'"
            ),
        )

    result = evaluate_control(
        action=action,
        policy=policy,
        qualification=qualification,
    )

    audit_log.record(
        AuditEvent(
            agent_id=action.agent_id,
            tool=action.tool,
            action=action.action,
            decision=result.decision,
            reason=result.reason,
        )
    )

    return result


@app.get("/api/gateway/audit")
def audit():
    return {
        "events": audit_log.all(),
        "count": len(audit_log.events),
    }