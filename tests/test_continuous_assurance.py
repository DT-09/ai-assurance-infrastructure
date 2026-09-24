import os
import tempfile

from app.assurance.continuous import (
    ContinuousAssuranceEngine,
)
from app.assurance.engine import AssuranceEngine
from app.assurance.models import EvaluationResult
from app.control_plane.events import ControlPlaneEventBus
from app.control_plane.service import ControlPlaneService
from app.control_plane.store import ControlPlaneStore


def make_system():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)

    store = ControlPlaneStore(path)
    bus = ControlPlaneEventBus()
    service = ControlPlaneService(
        store=store,
        event_bus=bus,
    )

    org = service.create_organization(
        "Acme AI"
    )

    project = service.create_project(
        org.organization_id,
        "Production AI",
    )

    asset = service.create_asset(
        project.project_id,
        "Claims Agent",
        "ai_agent",
    )

    version = service.create_version(
        asset.asset_id,
        "1.0.0",
        "production",
        model="model-x",
    )

    return service, bus, asset, version, path


def cleanup(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def test_dependency_change_marks_assurance_stale():
    service, bus, asset, version, path = make_system()

    try:
        continuous = ContinuousAssuranceEngine(
            control_plane=service,
            assurance_engine=AssuranceEngine(),
            event_bus=bus,
        )

        service.add_dependency(
            asset.asset_id,
            version.version_id,
            "model",
            "model-x",
            "2.0.0",
            critical=True,
        )

        updated = service.store.get_version(
            version.version_id
        )

        assert updated is not None
        assert updated.status == "assurance_stale"

        impacts = continuous.impacts()

        assert len(impacts) == 1
        assert impacts[0].affected_asset_id == asset.asset_id
        assert impacts[0].affected_version_id == version.version_id
        assert impacts[0].reason == "dependency_changed"
        assert impacts[0].requires_re_evaluation is True

    finally:
        cleanup(path)


def test_dependency_change_triggers_re_evaluation():
    service, bus, asset, version, path = make_system()

    try:
        def evaluator(
            asset_id,
            version_name,
            environment,
        ):
            return [
                EvaluationResult(
                    evaluation_id="eval_recheck_1",
                    system_id=asset_id,
                    system_version=version_name,
                    evaluation_type="reliability",
                    metrics={
                        "reliability": 1.0
                    },
                    passed=True,
                    details={
                        "trigger": "dependency_change"
                    },
                )
            ]

        continuous = ContinuousAssuranceEngine(
            control_plane=service,
            assurance_engine=AssuranceEngine(),
            event_bus=bus,
            evaluator=evaluator,
        )

        service.add_dependency(
            asset.asset_id,
            version.version_id,
            "retrieval",
            "vector-db",
            "3.0.0",
            critical=False,
        )

        results = continuous.re_evaluations()

        assert len(results) == 1
        assert results[0].assurance is not None
        assert (
            results[0].assurance.verdict.value
            == "ASSURED"
        )

        updated = service.store.get_version(
            version.version_id
        )

        assert updated is not None
        assert updated.status == "assured"

    finally:
        cleanup(path)


def test_unrelated_events_do_not_invalidate_assurance():
    service, bus, asset, version, path = make_system()

    try:
        continuous = ContinuousAssuranceEngine(
            control_plane=service,
            assurance_engine=AssuranceEngine(),
            event_bus=bus,
        )

        service.create_version(
            asset.asset_id,
            "2.0.0",
            "staging",
        )

        assert continuous.impacts() == []
        assert continuous.re_evaluations() == []

    finally:
        cleanup(path)


def test_event_bus_delivers_events_to_subscribers():
    bus = ControlPlaneEventBus()
    received = []

    def subscriber(event):
        received.append(event)

    bus.subscribe(subscriber)

    service, _, asset, version, path = make_system()

    try:
        bus2 = service.event_bus

        assert bus2 is not bus

        service.add_dependency(
            asset.asset_id,
            version.version_id,
            "api",
            "payments",
            "1.0",
        )

        events = service.get_timeline(
            asset.asset_id
        )

        assert any(
            event.event_type == "dependency.added"
            for event in events
        )

    finally:
        cleanup(path)
