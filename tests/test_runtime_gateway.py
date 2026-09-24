from app.runtime.gateway import RuntimeGateway, generate_attack_paths
from app.runtime.models import ActionRequest, AuthorityContract, RuntimeDecision


def contract():
    return AuthorityContract(
        agent_id="support-agent", version="2.4.1", environment="production",
        allowed_actions={"refund"}, allowed_tools={"payments", "crm"},
        allowed_data_classes={"customer_basic"}, approval_required_for={"refund"},
        max_transaction_usd=5000, allowed_destinations={"internal"}, purpose="customer support",
    )


def test_undeclared_action_is_blocked():
    g = RuntimeGateway(); g.register_contract(contract())
    r = g.authorize(ActionRequest(agent_id="support-agent", agent_version="2.4.1", action="delete_customer", tool="crm"))
    assert r.decision == RuntimeDecision.BLOCK
    assert any("outside declared authority" in x for x in r.reasons)


def test_consequential_action_requires_approval():
    g = RuntimeGateway(); g.register_contract(contract())
    r = g.authorize(ActionRequest(agent_id="support-agent", agent_version="2.4.1", action="refund", tool="payments", amount_usd=100))
    assert r.decision == RuntimeDecision.REQUIRE_APPROVAL


def test_approval_allows_same_action():
    g = RuntimeGateway(); g.register_contract(contract())
    req = ActionRequest(agent_id="support-agent", agent_version="2.4.1", action="refund", tool="payments", amount_usd=100)
    first = g.authorize(req)
    g.approve(first.decision_id, "finance-manager")
    second = g.authorize(req, approval_id=first.decision_id)
    assert second.decision == RuntimeDecision.ALLOW


def test_amount_limit_blocks_even_if_approval_action_exists():
    g = RuntimeGateway(); g.register_contract(contract())
    req = ActionRequest(agent_id="support-agent", agent_version="2.4.1", action="refund", tool="payments", amount_usd=25000)
    r = g.authorize(req, approval_id="anything")
    assert r.decision == RuntimeDecision.BLOCK


def test_evidence_hash_and_attack_paths():
    g = RuntimeGateway(); g.register_contract(contract())
    r = g.authorize(ActionRequest(agent_id="support-agent", agent_version="2.4.1", action="refund", tool="payments", amount_usd=100))
    assert len(r.evidence_hash) == 64
    paths = generate_attack_paths(contract())
    assert {p["id"] for p in paths} >= {"AUTH-001", "HUMAN-001"}
