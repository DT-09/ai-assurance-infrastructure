from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    asset_type: str = Field(default="agent", min_length=1, max_length=80)
    owner: str | None = None
    environment: str = "production"
    criticality: Literal["low", "medium", "high", "critical"] = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)

class VersionCreate(BaseModel):
    version: str = Field(min_length=1, max_length=120)
    model_ref: str | None = None
    runtime_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class DependencyCreate(BaseModel):
    source_asset_id: str
    target_ref: str
    dependency_type: str = "uses"
    criticality: Literal["low", "medium", "high", "critical"] = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)

class EvidenceCreate(BaseModel):
    asset_id: str
    version_id: str | None = None
    evidence_type: str
    source: str
    result: Literal["pass", "fail", "review", "informational"]
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: str | None = None

class EvaluationCreate(BaseModel):
    asset_id: str
    version_id: str | None = None
    evaluation_type: str = "qualification"
    reliability: float = Field(default=1.0, ge=0.0, le=1.0)
    critical_failures: int = Field(default=0, ge=0)
    human_review_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    tool_failures: int = Field(default=0, ge=0)
    evidence_ids: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)

class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: str = "1.0"
    rules: dict[str, Any] = Field(default_factory=dict)

class DecisionCreate(BaseModel):
    asset_id: str
    action: Literal["deploy", "execute", "change", "access"] = "execute"
    context: dict[str, Any] = Field(default_factory=dict)

class TrustState(BaseModel):
    asset_id: str
    state: Literal["ASSURED", "DEGRADED", "BLOCKED"]
    score: float = Field(ge=0.0, le=1.0)
    evidence_state: str
    dependency_state: str
    policy_state: str
    reliability: float
    critical_failures: int
    human_review_rate: float
    reasons: list[str] = Field(default_factory=list)
    computed_at: str
    epoch: int
