import os
import tempfile

from app.assurance.engine import AssuranceEngine
from app.assurance.models import EvaluationResult
from app.control_plane.bridge import AssuranceControlPlaneBridge
from app.control_plane.service import ControlPlaneService
from app.control_plane.store import ControlPlaneStore


def make_control_plane():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)

    store = ControlPlaneStore(path)
    service = ControlPlaneService(store)

    return service, path


def test_control_plane_asset_maps_to_assurance_system():
    control_plane, path = make_control_plane()

    try:
        engine = AssuranceEngine()

        org = control_plane.create_organization(
            "Acme AI"
        )

        project = control_plane.create_project(
            org.organization_id,
            "Automation",
        )

        asset = control_plane.create_asset(
            project.project_id,
            "Claims Agent",
            "ai_agent",
            owner="engineering",
        )

        control_plane.create_version(
            asset.asset_id,
            "1.0.0",
            "production",
            model="model-x",
            framework="framework-y",
        )

        bridge = AssuranceControlPlaneBridge(
            control_plane,
            engine,
        )

        system = bridge.build_system_record(
            asset.asset_id,
            "1.0.0",
            "production",
        )

        assert system.system_id == asset.asset_id
        assert system.name == "Claims Agent"
        assert system.version == "1.0.0"
        assert system.environment == "production"
        assert system.model == "model-x"
        assert system.framework == "framework-y"

    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def test_assurance_is_issued_for_control_plane_asset():
    control_plane, path = make_control_plane()

    try:
        engine = AssuranceEngine()

        org = control_plane.create_organization(
            "Acme AI"
        )

        project = control_plane.create_project(
            org.organization_id,
            "Automation",
        )

        asset = control_plane.create_asset(
            project.project_id,
            "Claims Agent",
            "ai_agent",
        )

        control_plane.create_version(
            asset.asset_id,
            "2.0.0",
            "staging",
        )

        bridge = AssuranceControlPlaneBridge(
            control_plane,
            engine,
        )

        evaluation = EvaluationResult(
            evaluation_id="eval_control_plane_1",
            system_id=asset.asset_id,
            system_version="2.0.0",
            evaluation_type="reliability",
            metrics={"reliability": 1.0},
            passed=True,
            details={
                "source": "control-plane-test"
            },
        )

        assurance = bridge.issue_assurance(
            asset_id=asset.asset_id,
            version="2.0.0",
            environment="staging",
            evaluations=[evaluation],
        )

        assert assurance.system_id == asset.asset_id
        assert assurance.system_version == "2.0.0"
        assert assurance.environment == "staging"
        assert assurance.verdict.value == "ASSURED"

    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def test_control_plane_context_contains_dependencies():
    control_plane, path = make_control_plane()

    try:
        org = control_plane.create_organization(
            "Acme AI"
        )

        project = control_plane.create_project(
            org.organization_id,
            "Automation",
        )

        asset = control_plane.create_asset(
            project.project_id,
            "Claims Agent",
            "ai_agent",
        )

        version = control_plane.create_version(
            asset.asset_id,
            "1.0.0",
            "production",
        )

        control_plane.add_dependency(
            asset.asset_id,
            version.version_id,
            "model",
            "model-x",
            "1.2.0",
            critical=True,
        )

        bridge = AssuranceControlPlaneBridge(
            control_plane,
            AssuranceEngine(),
        )

        context = bridge.get_control_plane_context(
            asset.asset_id
        )

        assert context["asset"].asset_id == asset.asset_id
        assert len(context["versions"]) == 1
        assert len(
            context["versions"][0]["dependencies"]
        ) == 1

    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
