from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from .identity import IdentityStore
from .models import Dependency
from .service import ControlPlaneService
from app.billing import PLANS

from app.assurance.models import EvaluationResult, PolicyRule
from app.assurance.passport import AssurancePassport, verify_passport
from app.assurance.platform import AssurancePlatform
from app.assurance.verification import verify_passport_evidence


router = APIRouter(prefix="/v1/control", tags=["AI Assurance Control Plane"])


class BootstrapRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    organization_id: Optional[str] = Field(default=None, min_length=2, max_length=100)


class KeyRequest(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=100)


class ProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetRequest(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=200)
    asset_type: str = Field(min_length=1, max_length=100)
    owner: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VersionRequest(BaseModel):
    version: str = Field(min_length=1, max_length=100)
    environment: str = Field(min_length=1, max_length=100)
    model: Optional[str] = None
    framework: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DependencyRequest(BaseModel):
    version_id: str
    dependency_type: str
    dependency_name: str
    dependency_version: Optional[str] = None
    critical: bool = False
    target_asset_id: Optional[str] = None
    target_version_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyRuleRequest(BaseModel):
    metric: str
    operator: str
    threshold: float
    severity: str = "blocking"
    description: Optional[str] = None


class PolicyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: str = "1.0.0"
    rules: list[PolicyRuleRequest]
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyBindingRequest(BaseModel):
    asset_id: str
    policy_id: str
    version_id: Optional[str] = None
    environment: Optional[str] = None


class EvaluationRequest(BaseModel):
    evaluation_id: Optional[str] = None
    evaluation_type: str = "workflow"
    metrics: dict[str, float] = Field(default_factory=dict)
    passed: Optional[bool] = None
    details: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class AssuranceRequest(BaseModel):
    version: str
    environment: str
    evaluations: list[EvaluationRequest]


class RevokeRequest(BaseModel):
    reason: str = "manual_revocation"


def _platform(request: Request) -> AssurancePlatform:
    return request.app.state.assurance_platform


def _identity(request: Request) -> IdentityStore:
    return request.app.state.identity_store


def require_identity(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> str:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    organization_id = _identity(request).authenticate(x_api_key)
    if organization_id is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    return organization_id


def _require_project_org(platform: AssurancePlatform, project_id: str, organization_id: str):
    project = platform.control_plane.store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _require_asset_org(platform: AssurancePlatform, asset_id: str, organization_id: str):
    asset = platform.control_plane.store.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="AI asset not found")
    _require_project_org(platform, asset.project_id, organization_id)
    return asset


def _enforce_asset_limit(request: Request, organization_id: str) -> None:
    account = request.app.state.billing_store.get_account(organization_id)
    plan = PLANS.get(account["plan"], PLANS["developer"])
    if plan.max_assets is None:
        return
    usage = request.app.state.billing_store.usage(organization_id)
    if usage["assets_created"] >= plan.max_assets:
        raise HTTPException(
            status_code=402,
            detail=f"Plan '{plan.key}' has reached its monthly asset limit. Upgrade the workspace to continue.",
        )


def _enforce_evaluation_limit(request: Request, organization_id: str, count: int) -> None:
    account = request.app.state.billing_store.get_account(organization_id)
    plan = PLANS.get(account["plan"], PLANS["developer"])
    if plan.max_evaluations_month is None:
        return
    usage = request.app.state.billing_store.usage(organization_id)
    if usage["evaluations"] + count > plan.max_evaluations_month:
        raise HTTPException(
            status_code=402,
            detail=f"Plan '{plan.key}' has reached its monthly evaluation limit. Upgrade the workspace to continue.",
        )


@router.get("/health")
def control_health(request: Request):
    return {
        "status": "ok",
        "service": "ai-assurance-control-plane",
        "version": AssurancePlatform.VERSION,
    }


@router.get("/protocol/manifest")
def protocol_manifest(request: Request):
    return _platform(request).protocol_manifest()


@router.post("/organizations/bootstrap", status_code=status.HTTP_201_CREATED)
def bootstrap_organization(payload: BootstrapRequest, request: Request, x_bootstrap_key: Optional[str] = Header(default=None, alias="X-Bootstrap-Key")):
    expected = os.getenv("ASSURANCE_BOOTSTRAP_KEY")
    if not expected or not x_bootstrap_key or x_bootstrap_key != expected:
        raise HTTPException(status_code=401, detail="Invalid bootstrap credential")
    platform = _platform(request)
    try:
        organization = platform.control_plane.create_organization(
            payload.name,
            metadata={},
            organization_id=payload.organization_id,
        )
    except ValueError as exc:
        if "already exists" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    key = _identity(request).create_key(organization.organization_id, "initial")
    request.app.state.billing_store.ensure_account(organization.organization_id)
    return {"organization": organization, "credential": key, "billing": request.app.state.billing_store.get_account(organization.organization_id)}


@router.post("/credentials")
def create_credential(payload: KeyRequest, request: Request, organization_id: str = Depends(require_identity)):
    return _identity(request).create_key(organization_id, payload.name)


@router.get("/credentials")
def list_credentials(request: Request, organization_id: str = Depends(require_identity)):
    return {"credentials": _identity(request).list_keys(organization_id)}


@router.get("/organization")
def current_organization(request: Request, organization_id: str = Depends(require_identity)):
    organization = _platform(request).control_plane.store.get_organization(organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


@router.post("/credentials/{key_id}/revoke")
def revoke_credential(key_id: str, request: Request, organization_id: str = Depends(require_identity)):
    if not _identity(request).revoke(key_id, organization_id):
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"status": "revoked", "key_id": key_id}


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectRequest, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    item = platform.control_plane.create_project(organization_id, payload.name, payload.metadata)
    return item


@router.post("/assets", status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetRequest, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_project_org(platform, payload.project_id, organization_id)
    _enforce_asset_limit(request, organization_id)
    result = platform.control_plane.create_asset(
        payload.project_id, payload.name, payload.asset_type, payload.owner, payload.metadata
    )
    request.app.state.billing_store.increment_usage(organization_id, "assets_created")
    return result


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    return platform.control_plane.get_asset(asset_id)


@router.post("/assets/{asset_id}/versions", status_code=status.HTTP_201_CREATED)
def create_version(asset_id: str, payload: VersionRequest, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    return platform.control_plane.create_version(
        asset_id, payload.version, payload.environment, payload.model, payload.framework, payload.metadata
    )


@router.post("/assets/{asset_id}/dependencies", status_code=status.HTTP_201_CREATED)
def add_dependency(asset_id: str, payload: DependencyRequest, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    if payload.target_asset_id:
        _require_asset_org(platform, payload.target_asset_id, organization_id)
    if payload.target_version_id:
        target = platform.control_plane.store.get_version(payload.target_version_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Target asset version not found")
        _require_asset_org(platform, target.asset_id, organization_id)
    return platform.control_plane.add_dependency(
        asset_id=asset_id,
        version_id=payload.version_id,
        dependency_type=payload.dependency_type,
        dependency_name=payload.dependency_name,
        dependency_version=payload.dependency_version,
        critical=payload.critical,
        metadata=payload.metadata,
        target_asset_id=payload.target_asset_id,
        target_version_id=payload.target_version_id,
    )


@router.get("/assets/{asset_id}/timeline")
def asset_timeline(asset_id: str, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    return {"asset_id": asset_id, "events": platform.control_plane.get_timeline(asset_id)}


@router.get("/assets/{asset_id}/dependencies")
def asset_dependencies(asset_id: str, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    return {"asset_id": asset_id, "dependencies": platform.control_plane.get_dependencies(asset_id)}


@router.post("/policies", status_code=status.HTTP_201_CREATED)
def create_policy(payload: PolicyRequest, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    metadata = {**payload.metadata, "organization_id": organization_id}
    return platform.policy_service.create(
        name=payload.name,
        version=payload.version,
        rules=[PolicyRule(**rule.model_dump()) for rule in payload.rules],
        metadata=metadata,
    )


@router.get("/policies")
def list_policies(request: Request, organization_id: str = Depends(require_identity)):
    policies = _platform(request).policy_service.list()
    visible = [
        policy for policy in policies
        if policy.metadata.get("organization_id") in {None, organization_id}
    ]
    return {"policies": visible}


@router.get("/policies/{policy_id}")
def get_policy(policy_id: str, request: Request, organization_id: str = Depends(require_identity)):
    policy = _platform(request).policy_service.get(policy_id)
    if policy is None or policy.metadata.get("organization_id") not in {None, organization_id}:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.post("/policies/bind")
def bind_policy(payload: PolicyBindingRequest, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, payload.asset_id, organization_id)
    policy = platform.policy_service.get(payload.policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    if policy.metadata.get("organization_id") not in {None, organization_id}:
        raise HTTPException(status_code=404, detail="Policy not found")
    return platform.policy_service.bind(
        asset_id=payload.asset_id,
        policy_id=payload.policy_id,
        version_id=payload.version_id,
        environment=payload.environment,
    )


@router.post("/assets/{asset_id}/assure")
def assure_asset(asset_id: str, payload: AssuranceRequest, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    _enforce_evaluation_limit(request, organization_id, len(payload.evaluations))
    evaluations: list[EvaluationResult] = []
    for item in payload.evaluations:
        evidence_ids = []
        for evidence in item.evidence:
            evidence_id = str(evidence.get("evidence_id") or platform.control_plane._id("evi"))
            record = platform.evidence_store.create(
                evidence_id=evidence_id,
                evidence_type=str(evidence.get("evidence_type", "evaluation")),
                system_id=asset_id,
                system_version=payload.version,
                source=str(evidence.get("source", "api")),
                payload=dict(evidence.get("payload") or {}),
            )
            evidence_ids.append(record.evidence_id)
        evaluations.append(
            EvaluationResult(
                evaluation_id=item.evaluation_id or platform.control_plane._id("eval"),
                system_id=asset_id,
                system_version=payload.version,
                evaluation_type=item.evaluation_type,
                metrics=item.metrics,
                passed=item.passed,
                details=item.details,
                evidence_ids=evidence_ids,
            )
        )
    result = platform.assure(
        asset_id=asset_id,
        version=payload.version,
        environment=payload.environment,
        evaluations=evaluations,
    )
    for _ in evaluations:
        request.app.state.billing_store.increment_usage(organization_id, "evaluations")
    return result


@router.get("/assets/{asset_id}/trust/{version_id}")
def trust_state(asset_id: str, version_id: str, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    version = platform.control_plane.store.get_version(version_id)
    if version is None or version.asset_id != asset_id:
        raise HTTPException(status_code=404, detail="Asset version not found")
    return {
        "asset_id": asset_id,
        "version_id": version_id,
        "state": platform.current_trust(asset_id, version_id).value,
        "history": platform.trust_history(asset_id, version_id),
    }


@router.post("/assets/{asset_id}/versions/{version_id}/deployment-check")
def deployment_check(asset_id: str, version_id: str, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    return platform.deployment_check(asset_id=asset_id, version_id=version_id, environment="production")


@router.post("/assets/{asset_id}/versions/{version_id}/runtime-check")
def runtime_check(asset_id: str, version_id: str, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    return platform.runtime_check(asset_id=asset_id, version_id=version_id, environment="production")


@router.post("/assets/{asset_id}/versions/{version_id}/revoke")
def revoke_asset(asset_id: str, version_id: str, payload: RevokeRequest, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    version = platform.control_plane.store.get_version(version_id)
    if version is None or version.asset_id != asset_id:
        raise HTTPException(status_code=404, detail="Asset version not found")
    return platform.revoke(asset_id=asset_id, version_id=version_id, reason=payload.reason)


@router.get("/assets/{asset_id}/assurance")
def asset_assurance(asset_id: str, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    return {"asset_id": asset_id, "records": platform.assurance_store.list_for_system(asset_id)}


@router.get("/assets/{asset_id}/graph")
def asset_graph(asset_id: str, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    return platform.graph.graph_for_system(asset_id)


@router.get("/assurance/{assurance_id}")
def get_assurance(assurance_id: str, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    record = platform.assurance_store.get(assurance_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Assurance record not found")
    _require_asset_org(platform, record.system_id, organization_id)
    return record


@router.get("/assurance/{assurance_id}/passport")
def get_passport(assurance_id: str, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    record = platform.assurance_store.get(assurance_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Assurance record not found")
    _require_asset_org(platform, record.system_id, organization_id)
    return platform.passport(assurance_id).to_dict()


@router.get("/assets/{asset_id}/provenance/{assurance_id}")
def provenance(asset_id: str, assurance_id: str, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    record = platform.assurance_store.get(assurance_id)
    if record is None or record.system_id != asset_id:
        raise HTTPException(status_code=404, detail="Assurance record not found")
    return platform.provenance.get_assurance_provenance(assurance_id)


@router.get("/assets/{asset_id}/version-diff/{from_version}/{to_version}")
def version_diff(asset_id: str, from_version: str, to_version: str, request: Request, organization_id: str = Depends(require_identity)):
    platform = _platform(request)
    _require_asset_org(platform, asset_id, organization_id)
    return platform.provenance.compare_versions(asset_id, from_version, to_version)


@router.post("/verify/passport")
def verify_passport_public(payload: dict):
    passport = payload.get("passport")
    if not isinstance(passport, dict):
        raise HTTPException(status_code=400, detail="passport is required")
    passport_valid = verify_passport(passport)
    evidence_result = verify_passport_evidence(passport, payload.get("evidence", []))
    return {
        "valid": passport_valid and evidence_result["valid"],
        "passport_valid": passport_valid,
        "evidence_verification": evidence_result,
    }
