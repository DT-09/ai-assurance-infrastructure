import os
import tempfile

import pytest

from app.assurance.models import (
    EvaluationResult,
    PolicyRule,
    SystemRecord,
)
from app.assurance.policy_service import PolicyService
from app.assurance.policy_store import PolicyStore
from app.assurance.engine import AssuranceEngine


def make_store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)

    return PolicyStore(path), path


def cleanup(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def test_policy_service_creates_and_validates_policy():
    store, path = make_store()

    try:
        service = PolicyService(store)

        policy = service.create(
            name="Production Reliability",
            version="1.0.0",
            rules=[
                PolicyRule(
                    metric="reliability",
                    operator=">=",
                    threshold=0.99,
                    severity="blocking",
                    description=(
                        "Reliability must remain at least 99%"
                    ),
                )
            ],
        )

        assert policy.policy_id.startswith("pol_")

        loaded = service.get(policy.policy_id)

        assert loaded is not None
        assert loaded.name == "Production Reliability"
        assert loaded.version == "1.0.0"
        assert len(loaded.rules) == 1

    finally:
        cleanup(path)


def test_invalid_policy_is_rejected():
    store, path = make_store()

    try:
        service = PolicyService(store)

        with pytest.raises(ValueError):
            service.create(
                name="Invalid",
                version="1.0.0",
                rules=[
                    PolicyRule(
                        metric="reliability",
                        operator="INVALID",
                        threshold=0.99,
                    )
                ],
            )

    finally:
        cleanup(path)


def test_policy_binding_resolves_most_specific_policy():
    store, path = make_store()

    try:
        service = PolicyService(store)

        asset_policy = service.create(
            name="Asset Policy",
            version="1.0.0",
            rules=[
                PolicyRule(
                    metric="reliability",
                    operator=">=",
                    threshold=0.95,
                )
            ],
        )

        version_policy = service.create(
            name="Production Policy",
            version="2.0.0",
            rules=[
                PolicyRule(
                    metric="reliability",
                    operator=">=",
                    threshold=0.99,
                )
            ],
        )

        service.bind(
            asset_id="ast_1",
            policy_id=asset_policy.policy_id,
        )

        service.bind(
            asset_id="ast_1",
            policy_id=version_policy.policy_id,
            version_id="ver_1",
            environment="production",
        )

        resolved = service.resolve(
            asset_id="ast_1",
            version_id="ver_1",
            environment="production",
        )

        assert resolved is not None
        assert (
            resolved.policy_id
            == version_policy.policy_id
        )

    finally:
        cleanup(path)


def test_policy_evaluation_is_deterministic():
    store, path = make_store()

    try:
        service = PolicyService(store)

        policy = service.create(
            name="Reliability Policy",
            version="1.0.0",
            rules=[
                PolicyRule(
                    metric="reliability",
                    operator=">=",
                    threshold=0.99,
                    severity="blocking",
                ),
                PolicyRule(
                    metric="latency",
                    operator="<=",
                    threshold=1000,
                    severity="warning",
                ),
            ],
        )

        result = service.evaluate(
            policy,
            {
                "reliability": 0.995,
                "latency": 1500,
            },
        )

        passed, blocking, warnings = result

        assert passed is True
        assert blocking == []
        assert len(warnings) == 1

    finally:
        cleanup(path)


def test_policy_is_applied_during_assurance():
    store, path = make_store()

    try:
        service = PolicyService(store)

        policy = service.create(
            name="Strict Reliability",
            version="1.0.0",
            rules=[
                PolicyRule(
                    metric="reliability",
                    operator=">=",
                    threshold=0.99,
                    severity="blocking",
                )
            ],
        )

        assurance = AssuranceEngine()

        result = assurance.issue(
            system=SystemRecord(
                system_id="ast_1",
                name="Test Agent",
                system_type="agent",
                version="1.0.0",
                environment="production",
                model=None,
                framework=None,
                owner=None,
                metadata={},
            ),
            evaluations=[
                EvaluationResult(
                    evaluation_id="eval_1",
                    system_id="ast_1",
                    system_version="1.0.0",
                    evaluation_type="reliability",
                    metrics={
                        "reliability": 0.95
                    },
                    passed=True,
                )
            ],
            policy=policy,
        )

        assert result.policy_id == policy.policy_id
        assert result.verdict.value == "BLOCKED"

    finally:
        cleanup(path)