from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Verdict(str, Enum):
    ASSURED = "ASSURED"
    BLOCKED = "BLOCKED"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class SystemRecord(BaseModel):
    system_id: str
    name: str
    system_type: str = "agent"
    version: str
    environment: str = "staging"
    model: Optional[str] = None
    framework: Optional[str] = None
    owner: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class EvidenceRecord(BaseModel):
    evidence_id: str
    evidence_type: str
    system_id: str
    system_version: str
    source: str
    payload: Dict[str, Any]
    content_hash: str
    created_at: datetime = Field(default_factory=utc_now)


class EvaluationResult(BaseModel):
    evaluation_id: str
    system_id: str
    system_version: str
    evaluation_type: str
    metrics: Dict[str, float] = Field(default_factory=dict)
    passed: Optional[bool] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class PolicyRule(BaseModel):
    metric: str
    operator: str
    threshold: float
    severity: str = "blocking"
    description: Optional[str] = None


class Policy(BaseModel):
    policy_id: str
    name: str
    version: str = "1.0.0"
    rules: List[PolicyRule] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class AssuranceRecord(BaseModel):
    assurance_id: str
    system_id: str
    system_version: str
    environment: str
    verdict: Verdict
    evaluation_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    policy_id: Optional[str] = None
    metrics: Dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    engine_version: str = "assurance-core-1.0.0"
