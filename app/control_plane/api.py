from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

from .service import ControlPlaneService

router = APIRouter(
    prefix="/v1/control-plane",
    tags=["control-plane"],
)

service = ControlPlaneService()


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1)
    metadata: Dict[str, Any] = {}


class ProjectCreate(BaseModel):
    organization_id: str
    name: str = Field(min_length=1)
    metadata: Dict[str, Any] = {}


class AssetCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    owner: Optional[str] = None
    metadata: Dict[str, Any] = {}


class VersionCreate(BaseModel):
    version: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    model: Optional[str] = None
    framework: Optional[str] = None
    metadata: Dict[str, Any] = {}


class DependencyCreate(BaseModel):
    version_id: str
    dependency_type: str = Field(min_length=1)
    dependency_name: str = Field(min_length=1)
    dependency_version: Optional[str] = None
    critical: bool = False
    metadata: Dict[str, Any] = {}


@router.post("/organizations")
def create_organization(request: OrganizationCreate):
    return service.create_organization(
        name=request.name,
        metadata=request.metadata,
    )


@router.post("/projects")
def create_project(request: ProjectCreate):
    try:
        return service.create_project(
            organization_id=request.organization_id,
            name=request.name,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/assets")
def create_asset(request: AssetCreate):
    try:
        return service.create_asset(
            project_id=request.project_id,
            name=request.name,
            asset_type=request.asset_type,
            owner=request.owner,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/assets/{asset_id}/versions")
def create_version(asset_id: str, request: VersionCreate):
    try:
        return service.create_version(
            asset_id=asset_id,
            version=request.version,
            environment=request.environment,
            model=request.model,
            framework=request.framework,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/assets/{asset_id}/dependencies")
def add_dependency(asset_id: str, request: DependencyCreate):
    try:
        return service.add_dependency(
            asset_id=asset_id,
            version_id=request.version_id,
            dependency_type=request.dependency_type,
            dependency_name=request.dependency_name,
            dependency_version=request.dependency_version,
            critical=request.critical,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str):
    try:
        return service.get_asset(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/assets/{asset_id}/timeline")
def get_timeline(asset_id: str):
    try:
        return service.get_timeline(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/assets/{asset_id}/dependencies")
def get_dependencies(asset_id: str):
    try:
        return service.get_dependencies(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
