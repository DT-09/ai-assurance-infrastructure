from __future__ import annotations

import hashlib
import json
import uuid
from typing import Dict, List

from .models import (
    AssuranceRecord,
    EvaluationResult,
    Policy,
    SystemRecord,
    Verdict,
)
from .policy import PolicyEngine
from .store import AssuranceStore


class AssuranceEngine:

    def __init__(
        self,
        policy_engine: PolicyEngine | None = None,
        store: AssuranceStore | None = None,
    ):
        self.policy_engine = policy_engine or PolicyEngine()
        self.store = store or AssuranceStore()

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    def issue(
        self,
        system: SystemRecord,
        evaluations: List[EvaluationResult],
        policy: Policy | None = None,
    ) -> AssuranceRecord:

        metrics: Dict[str, float] = {}

        for evaluation in evaluations:
            metrics.update(evaluation.metrics)

        reasons: List[str] = []
        verdict = Verdict.UNKNOWN

        if not evaluations:
            reasons.append("No evaluations available")
            verdict = Verdict.UNKNOWN

        elif policy is None:
            all_passed = all(
                evaluation.passed is not False
                for evaluation in evaluations
            )

            if all_passed:
                verdict = Verdict.ASSURED
            else:
                verdict = Verdict.BLOCKED
                reasons.append("One or more evaluations failed")

        else:
            passed, blocking_failures, warnings = (
                self.policy_engine.evaluate(policy, metrics)
            )

            reasons.extend(blocking_failures)

            if not passed:
                verdict = Verdict.BLOCKED
            elif warnings:
                verdict = Verdict.DEGRADED
                reasons.extend(warnings)
            else:
                verdict = Verdict.ASSURED

        evaluation_ids = [
            evaluation.evaluation_id
            for evaluation in evaluations
        ]

        evidence_ids = [
            evidence_id
            for evaluation in evaluations
            for evidence_id in evaluation.evidence_ids
        ]

        record = AssuranceRecord(
            assurance_id=self._new_id("asr"),
            system_id=system.system_id,
            system_version=system.version,
            environment=system.environment,
            verdict=verdict,
            evaluation_ids=evaluation_ids,
            evidence_ids=evidence_ids,
            policy_id=policy.policy_id if policy else None,
            metrics=metrics,
            reasons=reasons,
        )

        self.store.save(record)

        return record
