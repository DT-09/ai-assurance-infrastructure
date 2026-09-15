from app.assurance.engine import AssuranceEngine
from app.assurance.evaluation import EvaluationEngine
from app.assurance.evidence import EvidenceStore
from app.assurance.graph import AssuranceGraph
from app.assurance.models import Policy, PolicyRule, SystemRecord
from app.assurance.policy import PolicyEngine
from app.assurance.provenance import ProvenanceService
from app.assurance.registry import AssuranceRegistry
from app.assurance.store import AssuranceStore


def build_service(tmp_path):
    registry = AssuranceRegistry(
        db_path=str(tmp_path / "registry.db")
    )

    evidence_store = EvidenceStore(
        db_path=str(tmp_path / "evidence.db")
    )

    assurance_store = AssuranceStore(
        db_path=str(tmp_path / "assurance.db")
    )

    graph = AssuranceGraph(
        db_path=str(tmp_path / "graph.db")
    )

    policy_engine = PolicyEngine()

    evaluation_engine = EvaluationEngine(
        evidence_store=evidence_store
    )

    assurance_engine = AssuranceEngine(
        assurance_store=assurance_store
    )

    service = ProvenanceService(
        registry=registry,
        assurance_store=assurance_store,
        evidence_store=evidence_store,
        graph=graph,
    )

    return (
        registry,
        evidence_store,
        assurance_store,
        graph,
        policy_engine,
        evaluation_engine,
        assurance_engine,
        service,
    )


def create_assurance(
    registry,
    evidence_store,
    assurance_store,
    graph,
    policy_engine,
    evaluation_engine,
    assurance_engine,
    system_id,
    version,
    reliability,
    critical_failures,
):
    system = SystemRecord(
        system_id=system_id,
        name=f"Test Agent {version}",
        system_type="agent",
        version=version,
        environment="staging",
    )

    registry.register(system)

    evidence = evidence_store.create(
        evidence_id=f"ev_{system_id}_{version}",
        evidence_type="evaluation_input",
        system_id=system_id,
        system_version=version,
        source="test",
        payload={
            "reliability": reliability,
            "critical_failures": critical_failures,
        },
    )

    evaluation = evaluation_engine.evaluate_metrics(
        evaluation_id=f"eval_{system_id}_{version}",
        system_id=system_id,
        system_version=version,
        evaluation_type="workflow",
        metrics={
            "reliability": reliability,
            "critical_failures": critical_failures,
            "latency_p95_ms": 500,
        },
        evidence_ids=[evidence.evidence_id],
    )

    policy = Policy(
        policy_id="production-v1",
        name="Production AI Policy",
        version="1.0.0",
        rules=[
            PolicyRule(
                metric="reliability",
                operator=">=",
                threshold=95,
                severity="blocking",
            ),
            PolicyRule(
                metric="critical_failures",
                operator="==",
                threshold=0,
                severity="blocking",
            ),
        ],
    )

    assurance = assurance_engine.issue(
        system=system,
        evaluations=[evaluation],
        policy=policy,
    )

    graph.sync_assurance(
        system=system,
        assurance=assurance,
        evaluations=[evaluation],
        evidence=[evidence],
        policy=policy,
    )

    return assurance


def test_system_status_returns_latest_assurance(tmp_path):
    (
        registry,
        evidence_store,
        assurance_store,
        graph,
        policy_engine,
        evaluation_engine,
        assurance_engine,
        service,
    ) = build_service(tmp_path)

    create_assurance(
        registry,
        evidence_store,
        assurance_store,
        graph,
        policy_engine,
        evaluation_engine,
        assurance_engine,
        "provenance-agent",
        "1.0.0",
        98,
        0,
    )

    result = service.get_system_status(
        "provenance-agent"
    )

    assert result["status"] == "ASSURED"
    assert result["system_version"] == "1.0.0"
    assert result["assurance_id"].startswith("asr_")
    assert result["policy_id"] == "production-v1"


def test_assurance_provenance_returns_lineage(tmp_path):
    (
        registry,
        evidence_store,
        assurance_store,
        graph,
        policy_engine,
        evaluation_engine,
        assurance_engine,
        service,
    ) = build_service(tmp_path)

    assurance = create_assurance(
        registry,
        evidence_store,
        assurance_store,
        graph,
        policy_engine,
        evaluation_engine,
        assurance_engine,
        "lineage-agent",
        "1.0.0",
        98,
        0,
    )

    result = service.get_assurance_provenance(
        assurance.assurance_id
    )

    assert result["assurance_id"] == assurance.assurance_id
    assert result["verdict"] == "ASSURED"

    assert result["provenance"]["system"]
    assert result["provenance"]["system_versions"]
    assert result["provenance"]["assurance"]
    assert result["provenance"]["passports"]
    assert result["provenance"]["evaluations"]
    assert result["provenance"]["evidence"]
    assert result["provenance"]["policies"]

    relationships = {
        edge["relationship"]
        for edge in result["edges"]
    }

    assert "HAS_PASSPORT" in relationships
    assert "BASED_ON_EVALUATION" in relationships
    assert "SUPPORTED_BY" in relationships
    assert "GOVERNED_BY" in relationships


def test_version_comparison_detects_changes(tmp_path):
    (
        registry,
        evidence_store,
        assurance_store,
        graph,
        policy_engine,
        evaluation_engine,
        assurance_engine,
        service,
    ) = build_service(tmp_path)

    create_assurance(
        registry,
        evidence_store,
        assurance_store,
        graph,
        policy_engine,
        evaluation_engine,
        assurance_engine,
        "versioned-agent",
        "1.0.0",
        98,
        0,
    )

    create_assurance(
        registry,
        evidence_store,
        assurance_store,
        graph,
        policy_engine,
        evaluation_engine,
        assurance_engine,
        "versioned-agent",
        "1.1.0",
        91,
        1,
    )

    result = service.compare_versions(
        system_id="versioned-agent",
        from_version="1.0.0",
        to_version="1.1.0",
    )

    assert result["from_version"] == "1.0.0"
    assert result["to_version"] == "1.1.0"

    assert (
        result["from_assurance"]["verdict"]
        == "ASSURED"
    )

    assert (
        result["to_assurance"]["verdict"]
        == "BLOCKED"
    )

    assert (
        result["changes"]["metrics"]["reliability"]["from"]
        == 98
    )

    assert (
        result["changes"]["metrics"]["reliability"]["to"]
        == 91
    )

    assert (
        result["changes"]["metrics"]["critical_failures"]["from"]
        == 0
    )

    assert (
        result["changes"]["metrics"]["critical_failures"]["to"]
        == 1
    )