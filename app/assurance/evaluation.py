from __future__ import annotations

from typing import Dict, List

from .models import EvaluationResult


class EvaluationEngine:

    def evaluate_metrics(
        self,
        evaluation_id: str,
        system_id: str,
        system_version: str,
        evaluation_type: str,
        metrics: Dict[str, float],
        evidence_ids: List[str] | None = None,
        details: Dict | None = None,
    ) -> EvaluationResult:

        return EvaluationResult(
            evaluation_id=evaluation_id,
            system_id=system_id,
            system_version=system_version,
            evaluation_type=evaluation_type,
            metrics=metrics,
            evidence_ids=evidence_ids or [],
            details=details or {},
        )
