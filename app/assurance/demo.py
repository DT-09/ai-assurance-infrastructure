import json

from app.assurance.engine import AssuranceEngine
from app.assurance.evidence import EvidenceStore
from app.assurance.evaluation import EvaluationEngine
from app.assurance.models import Policy, PolicyRule, SystemRecord
from app.assurance.policy import PolicyEngine
from app.assurance.registry import AssuranceRegistry


def main():
    registry = AssuranceRegistry()
    evidence_store = EvidenceStore()
    evaluation_engine = EvaluationEngine()
    policy_engine = PolicyEngine()
    assurance_engine = AssuranceEngine(
        policy_engine=policy_engine
    )

    system = SystemRecord(
        system_id="refund-agent",
        name="Refund Agent",
        system_type="agent",
        version="1.0.0",
        environment="staging",
        model="example-model",
    )

    registry.register(system)

    evidence = evidence_store.create(
        evidence_id="ev_demo_001",
        evidence_type="execution",
        system_id=system.system_id,
        system_version=system.version,
        source="demo",
        payload={
            "cases": 100,
            "successful_cases": 98,
            "critical_failures": 0,
        },
    )

    evaluation = evaluation_engine.evaluate_metrics(
        evaluation_id="eval_demo_001",
        system_id=system.system_id,
        system_version=system.version,
        evaluation_type="reliability",
        metrics={
            "reliability": 98.0,
            "critical_failures": 0.0,
            "latency_p95_ms": 820.0,
        },
        evidence_ids=[evidence.evidence_id],
    )

    policy = Policy(
        policy_id="policy_default_v1",
        name="Production AI Agent Policy",
        rules=[
            PolicyRule(
                metric="reliability",
                operator=">=",
                threshold=95.0,
                description="Reliability must be at least 95%",
            ),
            PolicyRule(
                metric="critical_failures",
                operator="==",
                threshold=0.0,
                description="Critical failures must equal zero",
            ),
            PolicyRule(
                metric="latency_p95_ms",
                operator="<=",
                threshold=2000.0,
                severity="warning",
                description="P95 latency should remain below 2000 ms",
            ),
        ],
    )

    record = assurance_engine.issue(
        system=system,
        evaluations=[evaluation],
        policy=policy,
    )

    print(json.dumps(
        record.model_dump(mode="json"),
        indent=2,
    ))


if __name__ == "__main__":
    main()

