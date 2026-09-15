from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import EvaluationResult


class EvaluationEngine:
    """
    Creates normalized evaluation results for the assurance system.

    evidence_store is accepted as an optional dependency so the evaluation
    layer can be connected to evidence persistence without breaking the
    existing API.
    """

    def __init__(self, evidence_store=None):
        self.evidence_store = evidence_store

    def evaluate_metrics(
        self,
        evaluation_id: str,
        system_id: str,
        system_version: str,
        evaluation_type: str,
        metrics: Dict[str, Any],
        evidence_ids: Optional[List[str]] = None,
        passed: Optional[bool] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        return EvaluationResult(
            evaluation_id=evaluation_id,
            system_id=system_id,
            system_version=system_version,
            evaluation_type=evaluation_type,
            metrics=metrics,
            passed=passed,
            details=details or {},
            evidence_ids=evidence_ids or [],
            created_at=datetime.now(timezone.utc).isoformat(),
        )