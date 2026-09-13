from fastapi import FastAPI

from app.models import QualificationResult

from .audit import AuditLog
from .control import evaluate_control
from .engine import evaluate_action
from .models import AgentAction, AuditEvent, Policy


app = FastAPI(
    title="AI Agent Control Gateway",
    version="0.3.0",
)

audit_log = AuditLog()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-agent-control-gateway",
        "version": "0.3.0",
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


@app.post("/api/control/evaluate")
def control_evaluate(
    action: AgentAction,
    policy: Policy,
    qualification: QualificationResult,
):
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