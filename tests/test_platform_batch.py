import os
import tempfile

from app.assurance.models import (
    EvaluationResult,
    PolicyRule,
)
from app.assurance.platform import (
    AssurancePlatform,
)
from app.assurance.protocol import (
    AssuranceProtocol,
)
from app.assurance.policy_store import (
    PolicyStore,
)
from app.assurance.registry import (
    AssuranceRegistry,
)
from app.assurance.evidence import (
    EvidenceStore,
)
from app.assurance.store import (
    AssuranceStore,
)
from app.assurance.trust_store import (
    TrustStateStore,
)
from app.assurance.trust_state import (
    TrustState,
)
from app.control_plane.events import (
    ControlPlaneEventBus,
)
from app.control_plane.service import (
    ControlPlaneService,
)
from app.control_plane.store import (
    ControlPlaneStore,
)


def db_path():
    fd, path = tempfile.mkstemp(
        suffix=".db"
    )

    os.close(fd)
    os.unlink(path)

    return path


def make_platform():

    paths = [
        db_path()
        for _ in range(6)
    ]

    bus = (
        ControlPlaneEventBus()
    )

    control_plane = (
        ControlPlaneService(
            ControlPlaneStore(paths[0]),
            bus,
        )
    )

    platform = AssurancePlatform(
        control_plane=control_plane,
        assurance_store=(
            AssuranceStore(paths[1])
        ),
        registry=(
            AssuranceRegistry(paths[2])
        ),
        evidence_store=(
            EvidenceStore(paths[3])
        ),
        policy_store=(
            PolicyStore(paths[4])
        ),
        trust_store=(
            TrustStateStore(paths[5])
        ),
        event_bus=bus,
    )

    return platform, paths


def cleanup(paths):

    for path in paths:

        try:
            os.remove(path)

        except FileNotFoundError:
            pass


def test_full_assurance_to_enforcement_flow():

    platform, paths = (
        make_platform()
    )

    try:

        organization = (
            platform.control_plane
            .create_organization(
                "Acme"
            )
        )

        project = (
            platform.control_plane
            .create_project(
                organization.organization_id,
                "AI",
            )
        )

        asset = (
            platform.control_plane
            .create_asset(
                project.project_id,
                "Refund Agent",
                "agent",
            )
        )

        version = (
            platform.control_plane
            .create_version(
                asset.asset_id,
                "1.0.0",
                "production",
            )
        )

        policy = (
            platform.policy_service
            .create(
                name=(
                    "Production Reliability"
                ),
                rules=[
                    PolicyRule(
                        metric="reliability",
                        operator=">=",
                        threshold=0.99,
                        severity="blocking",
                    )
                ],
            )
        )

        platform.policy_service.bind(
            asset_id=asset.asset_id,
            policy_id=policy.policy_id,
        )

        assurance = (
            platform.assure(
                asset_id=asset.asset_id,
                version="1.0.0",
                environment="production",
                evaluations=[
                    EvaluationResult(
                        evaluation_id="eval_1",
                        system_id=(
                            asset.asset_id
                        ),
                        system_version="1.0.0",
                        evaluation_type=(
                            "reliability"
                        ),
                        metrics={
                            "reliability": 0.995
                        },
                        passed=True,
                    )
                ],
            )
        )

        assert (
            assurance.verdict.value
            == "ASSURED"
        )

        assert (
            platform.current_trust(
                asset.asset_id,
                version.version_id,
            )
            == TrustState.ASSURED
        )

        deployment = (
            platform.deployment_check(
                asset_id=asset.asset_id,
                version_id=(
                    version.version_id
                ),
                environment="production",
            )
        )

        assert (
            deployment.decision.value
            == "ALLOW"
        )

        passport = (
            platform.passport(
                assurance.assurance_id
            )
        )

        passport_data = (
            passport.to_dict()
        )

        assert (
            passport_data[
                "integrity"
            ]["algorithm"]
            == "SHA-256"
        )

        assert (
            passport_data[
                "assurance"
            ]["verdict"]
            == "ASSURED"
        )

    finally:
        cleanup(paths)


def test_failed_assurance_denies_deployment():

    platform, paths = (
        make_platform()
    )

    try:

        organization = (
            platform.control_plane
            .create_organization(
                "Acme"
            )
        )

        project = (
            platform.control_plane
            .create_project(
                organization.organization_id,
                "AI",
            )
        )

        asset = (
            platform.control_plane
            .create_asset(
                project.project_id,
                "Refund Agent",
                "agent",
            )
        )

        version = (
            platform.control_plane
            .create_version(
                asset.asset_id,
                "1.0.0",
                "production",
            )
        )

        policy = (
            platform.policy_service
            .create(
                name="Strict",
                rules=[
                    PolicyRule(
                        metric="reliability",
                        operator=">=",
                        threshold=0.99,
                        severity="blocking",
                    )
                ],
            )
        )

        platform.policy_service.bind(
            asset_id=asset.asset_id,
            policy_id=policy.policy_id,
        )

        assurance = (
            platform.assure(
                asset_id=asset.asset_id,
                version="1.0.0",
                environment="production",
                evaluations=[
                    EvaluationResult(
                        evaluation_id="eval_1",
                        system_id=(
                            asset.asset_id
                        ),
                        system_version="1.0.0",
                        evaluation_type=(
                            "reliability"
                        ),
                        metrics={
                            "reliability": 0.90
                        },
                        passed=True,
                    )
                ],
            )
        )

        assert (
            assurance.verdict.value
            == "BLOCKED"
        )

        deployment = (
            platform.deployment_check(
                asset_id=asset.asset_id,
                version_id=(
                    version.version_id
                ),
                environment="production",
            )
        )

        assert (
            deployment.decision.value
            == "DENY"
        )

    finally:
        cleanup(paths)


def test_dependency_change_persists_stale_and_denies():

    platform, paths = (
        make_platform()
    )

    try:

        organization = (
            platform.control_plane
            .create_organization(
                "Acme"
            )
        )

        project = (
            platform.control_plane
            .create_project(
                organization.organization_id,
                "AI",
            )
        )

        model = (
            platform.control_plane
            .create_asset(
                project.project_id,
                "Model",
                "model",
            )
        )

        model_version = (
            platform.control_plane
            .create_version(
                model.asset_id,
                "1.0.0",
                "production",
            )
        )

        agent = (
            platform.control_plane
            .create_asset(
                project.project_id,
                "Agent",
                "agent",
            )
        )

        agent_version = (
            platform.control_plane
            .create_version(
                agent.asset_id,
                "1.0.0",
                "production",
            )
        )

        platform._transition_to(
            agent.asset_id,
            agent_version.version_id,
            TrustState.EVALUATING,
            reason="test",
        )

        platform._transition_to(
            agent.asset_id,
            agent_version.version_id,
            TrustState.ASSURED,
            reason="test",
        )

        platform.control_plane.add_dependency(
            asset_id=agent.asset_id,
            version_id=(
                agent_version.version_id
            ),
            dependency_type="model",
            dependency_name="Model",
            dependency_version="1.0.0",
            critical=True,
            target_asset_id=model.asset_id,
            target_version_id=(
                model_version.version_id
            ),
        )

        assert (
            platform.current_trust(
                agent.asset_id,
                agent_version.version_id,
            )
            == TrustState.STALE
        )

        deployment = (
            platform.deployment_check(
                asset_id=agent.asset_id,
                version_id=(
                    agent_version.version_id
                ),
                environment="production",
            )
        )

        assert (
            deployment.decision.value
            == "DENY"
        )

    finally:
        cleanup(paths)


def test_protocol_envelope_has_integrity():

    envelope = (
        AssuranceProtocol.envelope(
            "test",
            {
                "hello": "world"
            },
        )
    )

    assert (
        envelope["protocol"]
        == "AI Assurance Protocol"
    )

    assert (
        envelope["protocol_version"]
        == "1.0.0"
    )

    assert (
        envelope["integrity"]
        ["algorithm"]
        == "SHA-256"
    )

    assert (
        envelope["integrity"]
        ["content_hash"]
    )