import os
import tempfile

from app.assurance.impact import DependencyImpactEngine
from app.control_plane.service import ControlPlaneService
from app.control_plane.store import ControlPlaneStore


def make_service():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)

    store = ControlPlaneStore(path)
    service = ControlPlaneService(store=store)

    return service, path


def create_asset(service, project_id, name):
    asset = service.create_asset(
        project_id=project_id,
        name=name,
        asset_type="ai_agent",
    )

    version = service.create_version(
        asset_id=asset.asset_id,
        version="1.0.0",
        environment="production",
    )

    return asset, version


def test_direct_dependency_impact():
    service, path = make_service()

    try:
        org = service.create_organization("Test Org")
        project = service.create_project(
            org.organization_id,
            "AI Project",
        )

        upstream_asset, upstream_version = create_asset(
            service,
            project.project_id,
            "Model Service",
        )

        downstream_asset, downstream_version = create_asset(
            service,
            project.project_id,
            "Customer Agent",
        )

        service.add_dependency(
            asset_id=downstream_asset.asset_id,
            version_id=downstream_version.version_id,
            dependency_type="ai_service",
            dependency_name="Model Service",
            dependency_version="1.0.0",
            critical=True,
            target_asset_id=upstream_asset.asset_id,
            target_version_id=upstream_version.version_id,
        )

        engine = DependencyImpactEngine(service)

        dependency_event = next(
            event
            for event in service.store.list_events(
                "asset_version",
                downstream_version.version_id,
            )
            if event.event_type == "dependency.added"
        )

        analysis = engine.analyze_event(dependency_event)

        assert analysis is not None
        assert analysis.blast_radius == 1
        assert analysis.critical_impacts == 1

        impacted = analysis.affected_versions[0]

        assert impacted.version_id == downstream_version.version_id
        assert impacted.direct is True
        assert impacted.critical is True
        assert impacted.depth == 1

    finally:
        os.unlink(path)


def test_transitive_dependency_impact():
    service, path = make_service()

    try:
        org = service.create_organization("Test Org")
        project = service.create_project(
            org.organization_id,
            "AI Project",
        )

        asset_a, version_a = create_asset(
            service,
            project.project_id,
            "Foundation Model",
        )

        asset_b, version_b = create_asset(
            service,
            project.project_id,
            "Reasoning Agent",
        )

        asset_c, version_c = create_asset(
            service,
            project.project_id,
            "Customer Agent",
        )

        service.add_dependency(
            asset_id=asset_b.asset_id,
            version_id=version_b.version_id,
            dependency_type="ai_service",
            dependency_name="Foundation Model",
            dependency_version="1.0.0",
            critical=True,
            target_asset_id=asset_a.asset_id,
            target_version_id=version_a.version_id,
        )

        service.add_dependency(
            asset_id=asset_c.asset_id,
            version_id=version_c.version_id,
            dependency_type="ai_service",
            dependency_name="Reasoning Agent",
            dependency_version="1.0.0",
            critical=True,
            target_asset_id=asset_b.asset_id,
            target_version_id=version_b.version_id,
        )

        engine = DependencyImpactEngine(service)

        dependency_event = next(
            event
            for event in service.store.list_events(
                "asset_version",
                version_b.version_id,
            )
            if event.event_type == "dependency.added"
        )

        analysis = engine.analyze_event(dependency_event)

        assert analysis is not None

        impacted_ids = {
            item.version_id
            for item in analysis.affected_versions
        }

        assert version_b.version_id in impacted_ids
        assert version_c.version_id in impacted_ids

        c = next(
            item
            for item in analysis.affected_versions
            if item.version_id == version_c.version_id
        )

        assert c.depth == 2
        assert c.direct is False
        assert analysis.max_depth == 2
        assert analysis.blast_radius == 2

    finally:
        os.unlink(path)


def test_noncritical_dependency_is_tracked():
    service, path = make_service()

    try:
        org = service.create_organization("Test Org")
        project = service.create_project(
            org.organization_id,
            "AI Project",
        )

        upstream_asset, upstream_version = create_asset(
            service,
            project.project_id,
            "Logging Agent",
        )

        downstream_asset, downstream_version = create_asset(
            service,
            project.project_id,
            "Production Agent",
        )

        service.add_dependency(
            asset_id=downstream_asset.asset_id,
            version_id=downstream_version.version_id,
            dependency_type="service",
            dependency_name="Logging Agent",
            critical=False,
            target_asset_id=upstream_asset.asset_id,
            target_version_id=upstream_version.version_id,
        )

        engine = DependencyImpactEngine(service)

        dependency_event = next(
            event
            for event in service.store.list_events(
                "asset_version",
                downstream_version.version_id,
            )
            if event.event_type == "dependency.added"
        )

        analysis = engine.analyze_event(dependency_event)

        assert analysis is not None
        assert analysis.blast_radius == 1

        item = analysis.affected_versions[0]

        assert item.critical is False
        assert item.reason == "noncritical_dependency_impact"

    finally:
        os.unlink(path)


def test_re_evaluation_plan_prioritizes_critical():
    service, path = make_service()

    try:
        org = service.create_organization("Test Org")
        project = service.create_project(
            org.organization_id,
            "AI Project",
        )

        upstream_asset, upstream_version = create_asset(
            service,
            project.project_id,
            "Core Model",
        )

        critical_asset, critical_version = create_asset(
            service,
            project.project_id,
            "Payment Agent",
        )

        service.add_dependency(
            asset_id=critical_asset.asset_id,
            version_id=critical_version.version_id,
            dependency_type="model",
            dependency_name="Core Model",
            critical=True,
            target_asset_id=upstream_asset.asset_id,
            target_version_id=upstream_version.version_id,
        )

        engine = DependencyImpactEngine(service)

        event = next(
            event
            for event in service.store.list_events(
                "asset_version",
                critical_version.version_id,
            )
            if event.event_type == "dependency.added"
        )

        analysis = engine.analyze_event(event)
        plan = engine.build_re_evaluation_plan(analysis)

        assert len(plan) == 1
        assert plan[0].version_id == critical_version.version_id
        assert plan[0].priority == "critical"

    finally:
        os.unlink(path)


def test_unrelated_event_has_no_impact():
    service, path = make_service()

    try:
        org = service.create_organization("Test Org")
        project = service.create_project(
            org.organization_id,
            "AI Project",
        )

        asset, version = create_asset(
            service,
            project.project_id,
            "Agent",
        )

        event = service.record_event(
            "asset_version",
            version.version_id,
            "asset.version_registered",
            {},
        )

        engine = DependencyImpactEngine(service)

        assert engine.analyze_event(event) is None

    finally:
        os.unlink(path)
