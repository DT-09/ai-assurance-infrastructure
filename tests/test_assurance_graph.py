from types import SimpleNamespace

from app.assurance.graph import AssuranceGraph


def test_graph_creates_nodes_and_relationships(tmp_path):
    graph = AssuranceGraph(str(tmp_path / "graph.db"))

    system = SimpleNamespace(
        system_id="refund-agent",
        name="Refund Agent",
        system_type="agent",
        version="1.0.0",
        environment="staging",
        model=None,
        framework=None,
        owner=None,
        metadata={},
    )

    assurance = SimpleNamespace(
        assurance_id="asr_001",
        system_id="refund-agent",
        system_version="1.0.0",
        environment="staging",
        verdict="ASSURED",
        metrics={"reliability": 99.0},
        policy_id="production-v1",
        reasons=[],
        created_at="2026-09-14T00:00:00Z",
        engine_version="assurance-core-1.0.0",
    )

    evaluation = SimpleNamespace(
        evaluation_id="eval_001",
        evaluation_type="workflow",
        system_id="refund-agent",
        system_version="1.0.0",
        metrics={"reliability": 99.0},
        passed=True,
        details={},
        created_at="2026-09-14T00:00:00Z",
        evidence_ids=["ev_001"],
    )

    evidence = SimpleNamespace(
        evidence_id="ev_001",
        evidence_type="execution",
        source="test",
        content_hash="abc123",
        system_id="refund-agent",
        system_version="1.0.0",
        created_at="2026-09-14T00:00:00Z",
    )

    policy = SimpleNamespace(
        policy_id="production-v1",
        name="Production AI Policy",
        version="1.0.0",
        metadata={},
        rules=[],
    )

    result = graph.sync_assurance(
        system=system,
        assurance=assurance,
        evaluations=[evaluation],
        evidence=[evidence],
        policy=policy,
    )

    assert result["system_id"] == "refund-agent"
    assert result["node_count"] == 7
    assert result["edge_count"] == 6

    relationships = {
        edge["relationship"]
        for edge in result["edges"]
    }

    assert "HAS_VERSION" in relationships
    assert "HAS_ASSURANCE" in relationships
    assert "HAS_PASSPORT" in relationships
    assert "BASED_ON_EVALUATION" in relationships
    assert "GOVERNED_BY" in relationships


def test_graph_sync_is_idempotent(tmp_path):
    graph = AssuranceGraph(str(tmp_path / "graph.db"))

    system = SimpleNamespace(
        system_id="agent",
        name="Agent",
        system_type="agent",
        version="1.0.0",
        environment="staging",
        model=None,
        framework=None,
        owner=None,
        metadata={},
    )

    assurance = SimpleNamespace(
        assurance_id="asr_001",
        system_id="agent",
        system_version="1.0.0",
        environment="staging",
        verdict="ASSURED",
        metrics={},
        policy_id=None,
        reasons=[],
        created_at="2026-09-14T00:00:00Z",
        engine_version="assurance-core-1.0.0",
    )

    first = graph.sync_assurance(
        system=system,
        assurance=assurance,
    )

    second = graph.sync_assurance(
        system=system,
        assurance=assurance,
    )

    assert first["node_count"] == second["node_count"]
    assert first["edge_count"] == second["edge_count"]
