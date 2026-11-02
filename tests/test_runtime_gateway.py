from app.runtime.gateway import RuntimeGateway, generate_attack_paths
from app.runtime.models import ActionRequest, AuthorityContract, RuntimeDecision
from app.runtime.store import RuntimeStore


def contract():
    return AuthorityContract(
        agent_id="support-agent", version="2.4.1", environment="production",
        allowed_actions={"refund"}, allowed_tools={"payments", "crm"},
        allowed_data_classes={"customer_basic"}, approval_required_for={"refund"},
        max_transaction_usd=5000, allowed_destinations={"internal"}, purpose="customer support",
    )


def refund_request(amount=100, target="customer-1", destination="internal"):
    return ActionRequest(
        agent_id="support-agent", agent_version="2.4.1", action="refund",
        tool="payments", amount_usd=amount, target=target, destination=destination,
    )


def test_undeclared_action_is_blocked():
    g = RuntimeGateway()
    g.register_contract(contract())
    r = g.authorize(ActionRequest(agent_id="support-agent", agent_version="2.4.1", action="delete_customer", tool="crm"))
    assert r.decision == RuntimeDecision.BLOCK
    assert any("outside declared authority" in x for x in r.reasons)


def test_consequential_action_requires_approval():
    g = RuntimeGateway()
    g.register_contract(contract())
    r = g.authorize(refund_request())
    assert r.decision == RuntimeDecision.REQUIRE_APPROVAL


def test_approval_allows_exact_action_once():
    g = RuntimeGateway()
    g.register_contract(contract())
    request = refund_request()
    pending = g.authorize(request)
    g.approve(pending.decision_id, "finance-manager")

    allowed = g.authorize(request, approval_id=pending.decision_id)
    assert allowed.decision == RuntimeDecision.ALLOW

    replay = g.authorize(request, approval_id=pending.decision_id)
    assert replay.decision == RuntimeDecision.REQUIRE_APPROVAL


def test_approval_cannot_be_reused_with_changed_amount():
    g = RuntimeGateway()
    g.register_contract(contract())
    pending = g.authorize(refund_request(amount=100))
    g.approve(pending.decision_id, "finance-manager")

    changed = g.authorize(refund_request(amount=200), approval_id=pending.decision_id)
    assert changed.decision == RuntimeDecision.REQUIRE_APPROVAL


def test_approval_cannot_be_reused_with_changed_target_or_destination():
    g = RuntimeGateway()
    g.register_contract(contract())
    pending = g.authorize(refund_request(target="customer-1"))
    g.approve(pending.decision_id, "finance-manager")

    changed_target = g.authorize(refund_request(target="customer-2"), approval_id=pending.decision_id)
    assert changed_target.decision == RuntimeDecision.REQUIRE_APPROVAL

    changed_destination = g.authorize(
        refund_request(target="customer-1", destination="external"),
        approval_id=pending.decision_id,
    )
    assert changed_destination.decision == RuntimeDecision.BLOCK


def test_approval_cannot_be_granted_for_unknown_or_non_pending_decision():
    g = RuntimeGateway()
    g.register_contract(contract())
    try:
        g.approve("missing", "finance-manager")
    except ValueError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("unknown decision must not be approved")

    pending = g.authorize(refund_request())
    assert pending.decision == RuntimeDecision.REQUIRE_APPROVAL


def test_approval_is_invalid_after_contract_changes():
    g = RuntimeGateway()
    original = contract()
    g.register_contract(original)
    pending = g.authorize(refund_request())
    g.approve(pending.decision_id, "finance-manager")

    revised = AuthorityContract(
        agent_id=original.agent_id, version=original.version,
        environment=original.environment, allowed_actions=original.allowed_actions,
        allowed_tools=original.allowed_tools, allowed_data_classes=original.allowed_data_classes,
        denied_actions=original.denied_actions, approval_required_for=original.approval_required_for,
        max_transaction_usd=original.max_transaction_usd,
        allowed_destinations={"internal", "partner-portal"},
        purpose=original.purpose, contract_version="2",
    )
    g.register_contract(revised)
    result = g.authorize(refund_request(), approval_id=pending.decision_id)
    assert result.decision == RuntimeDecision.REQUIRE_APPROVAL


def test_approval_survives_gateway_restart_and_is_still_one_time(tmp_path):
    store = RuntimeStore(str(tmp_path / "runtime.db"))
    first_gateway = RuntimeGateway(store=store)
    first_gateway.register_contract(contract())
    request = refund_request()
    pending = first_gateway.authorize(request)
    first_gateway.approve(pending.decision_id, "finance-manager")

    restarted_gateway = RuntimeGateway(store=store)
    allowed = restarted_gateway.authorize(request, approval_id=pending.decision_id)
    assert allowed.decision == RuntimeDecision.ALLOW

    replay = RuntimeGateway(store=store).authorize(request, approval_id=pending.decision_id)
    assert replay.decision == RuntimeDecision.REQUIRE_APPROVAL


def test_expired_approval_is_rejected(tmp_path):
    store = RuntimeStore(str(tmp_path / "expired.db"))
    g = RuntimeGateway(store=store, approval_ttl_seconds=1)
    g.register_contract(contract())
    pending = g.authorize(refund_request())
    g.approve(pending.decision_id, "finance-manager")

    from datetime import datetime, timedelta, timezone
    import json
    grant = store.get_approval_grant(pending.decision_id)
    grant["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with store._conn() as connection:
        connection.execute(
            "UPDATE runtime_approval_grants SET payload=? WHERE decision_id=?",
            (json.dumps(grant, sort_keys=True), pending.decision_id),
        )

    result = g.authorize(refund_request(), approval_id=pending.decision_id)
    assert result.decision == RuntimeDecision.REQUIRE_APPROVAL


def test_amount_limit_blocks_even_with_approval_id():
    g = RuntimeGateway()
    g.register_contract(contract())
    request = refund_request(amount=25000)
    result = g.authorize(request, approval_id="anything")
    assert result.decision == RuntimeDecision.BLOCK


def test_evidence_hash_and_attack_paths():
    g = RuntimeGateway()
    g.register_contract(contract())
    result = g.authorize(refund_request())
    assert len(result.evidence_hash) == 64
    paths = generate_attack_paths(contract())
    assert {path["id"] for path in paths} >= {"AUTH-001", "HUMAN-001"}
