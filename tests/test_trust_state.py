import os
import tempfile

from app.assurance.policy_store import PolicyStore
from app.assurance.trust_state import (
    TrustState,
    TrustStateMachine,
)
from app.assurance.trust_store import TrustStateStore
from app.assurance.models import Policy, PolicyRule


def test_trust_state_machine_transitions():
    machine = TrustStateMachine()

    assert (
        machine.get_state(
            "ast_1",
            "ver_1",
        )
        == TrustState.UNKNOWN
    )

    first = machine.transition(
        "ast_1",
        "ver_1",
        TrustState.EVALUATING,
        "initial_evaluation",
    )

    assert (
        first.previous_state
        == TrustState.UNKNOWN
    )

    assured = machine.transition(
        "ast_1",
        "ver_1",
        TrustState.ASSURED,
        "evaluation_passed",
        assurance_id="asr_1",
    )

    assert (
        assured.previous_state
        == TrustState.EVALUATING
    )

    assert (
        machine.get_state(
            "ast_1",
            "ver_1",
        )
        == TrustState.ASSURED
    )


def test_invalid_trust_transition_is_rejected():
    machine = TrustStateMachine()

    machine.transition(
        "ast_1",
        "ver_1",
        TrustState.EVALUATING,
        "start",
    )

    machine.transition(
        "ast_1",
        "ver_1",
        TrustState.BLOCKED,
        "failed",
    )

    try:
        machine.transition(
            "ast_1",
            "ver_1",
            TrustState.ASSURED,
            "invalid",
        )
        assert False
    except ValueError:
        assert True


def test_trust_state_persists():
    fd, path = tempfile.mkstemp(
        suffix=".db"
    )
    os.close(fd)
    os.unlink(path)

    try:
        store = TrustStateStore(path)
        machine = TrustStateMachine()

        transition = machine.transition(
            "ast_1",
            "ver_1",
            TrustState.EVALUATING,
            "evaluation_started",
        )

        store.save_transition(
            transition
        )

        transition = machine.transition(
            "ast_1",
            "ver_1",
            TrustState.ASSURED,
            "evaluation_passed",
            assurance_id="asr_1",
        )

        store.save_transition(
            transition
        )

        assert (
            store.get_state(
                "ast_1",
                "ver_1",
            )
            == TrustState.ASSURED
        )

        history = store.history(
            "ast_1",
            "ver_1",
        )

        assert len(history) == 2
        assert (
            history[-1].new_state
            == TrustState.ASSURED
        )

    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def test_policy_persists():
    fd, path = tempfile.mkstemp(
        suffix=".db"
    )
    os.close(fd)
    os.unlink(path)

    try:
        store = PolicyStore(path)

        policy = Policy(
            policy_id="pol_1",
            name="Production Reliability",
            version="1.0",
            rules=[
                PolicyRule(
                    metric="reliability",
                    operator=">=",
                    threshold=0.99,
                    severity="blocking",
                    description="Minimum reliability",
                )
            ],
        )

        store.save(policy)

        loaded = store.get(
            "pol_1"
        )

        assert loaded is not None
        assert loaded.name == (
            "Production Reliability"
        )
        assert loaded.version == "1.0"
        assert len(loaded.rules) == 1
        assert (
            loaded.rules[0].metric
            == "reliability"
        )
        assert (
            loaded.rules[0].threshold
            == 0.99
        )

    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
