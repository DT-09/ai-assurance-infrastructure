import os
import tempfile

from app.control_plane.service import ControlPlaneService
from app.control_plane.store import ControlPlaneStore


def make_service():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)

    store = ControlPlaneStore(path)
    return store, ControlPlaneService(store), path


def cleanup(store, path):
    del store
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def test_complete_control_plane_lifecycle():
    store, service, path = make_service()

    try:
        org = service.create_organization(
            "Acme AI",
            {"region": "global"},
        )

        project = service.create_project(
            org.organization_id,
            "Claims Automation",
        )

        asset = service.create_asset(
            project.project_id,
            "Claims Agent",
            "ai_agent",
            owner="engineering",
        )

        version = service.create_version(
            asset.asset_id,
            "1.0.0",
            "production",
            model="gpt-family",
            framework="custom",
        )

        dependency = service.add_dependency(
            asset.asset_id,
            version.version_id,
            "model",
            "gpt-family",
            "latest",
            critical=True,
        )

        result = service.get_asset(asset.asset_id)

        assert result["asset"].asset_id == asset.asset_id
        assert len(result["versions"]) == 1
        assert result["versions"][0]["version"].version == "1.0.0"
        assert len(result["versions"][0]["dependencies"]) == 1
        assert (
            result["versions"][0]["dependencies"][0].dependency_id
            == dependency.dependency_id
        )
    finally:
        cleanup(store, path)


def test_cross_asset_version_is_rejected():
    store, service, path = make_service()

    try:
        org = service.create_organization("Org")
        project = service.create_project(
            org.organization_id,
            "Project",
        )

        asset_a = service.create_asset(
            project.project_id,
            "Agent A",
            "ai_agent",
        )

        asset_b = service.create_asset(
            project.project_id,
            "Agent B",
            "ai_agent",
        )

        version_a = service.create_version(
            asset_a.asset_id,
            "1.0.0",
            "production",
        )

        try:
            service.add_dependency(
                asset_b.asset_id,
                version_a.version_id,
                "model",
                "model-a",
            )
            assert False, "Expected cross-asset dependency rejection"
        except ValueError as exc:
            assert "does not belong" in str(exc)
    finally:
        cleanup(store, path)


def test_timeline_contains_lifecycle_events():
    store, service, path = make_service()

    try:
        org = service.create_organization("Org")
        project = service.create_project(
            org.organization_id,
            "Project",
        )

        asset = service.create_asset(
            project.project_id,
            "Agent",
            "ai_agent",
        )

        version = service.create_version(
            asset.asset_id,
            "1.0.0",
            "staging",
        )

        service.add_dependency(
            asset.asset_id,
            version.version_id,
            "tool",
            "crm",
        )

        timeline = service.get_timeline(asset.asset_id)
        event_types = [event.event_type for event in timeline]

        assert "asset.created" in event_types
        assert "asset.version_registered" in event_types
        assert "dependency.added" in event_types
    finally:
        cleanup(store, path)
