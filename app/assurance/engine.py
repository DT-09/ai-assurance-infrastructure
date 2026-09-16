from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterable, Optional

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
    """
    Core assurance decision engine.

    Issues AssuranceRecords from evaluation results and policies.
    """

    ENGINE_VERSION = "assurance-core-1.0.0"

    def __init__(
        self,
        assurance_store: Optional[AssuranceStore] = None,
        store: Optional[AssuranceStore] = None,
    ):
        if assurance_store is not None and store is not None:
            if assurance_store is not store:
                raise ValueError(
                    "Provide either assurance_store or store, "
                    "not two different stores."
                )

        self.store = assurance_store or store or AssuranceStore()

    def issue(
        self,
        system: SystemRecord,
        evaluations: Iterable[EvaluationResult],
        policy: Optional[Policy] = None,
    ) -> AssuranceRecord:
        evaluations = list(evaluations)

        assurance_id = f"asr_{uuid.uuid4().hex}"

        if not evaluations:
            record = AssuranceRecord(
                assurance_id=assurance_id,
                system_id=system.system_id,
                system_version=system.version,
                environment=system.environment,
                verdict=Verdict.UNKNOWN,
                evaluation_ids=[],
                evidence_ids=[],
                policy_id=policy.policy_id if policy else None,
                metrics={},
                reasons=["No evaluations were supplied."],
                created_at=datetime.now(timezone.utc).isoformat(),
                engine_version=self.ENGINE_VERSION,
            )

            self.store.save(record)
            return record

        blocking_failures = []
        warnings = []

        if policy is not None:
            policy_engine = PolicyEngine()

            for evaluation in evaluations:
                passed, evaluation_blocking, evaluation_warnings = (
                    policy_engine.evaluate(
                        metrics=evaluation.metrics,
                        policy=policy,
                    )
                )

                if not passed:
                    blocking_failures.extend(evaluation_blocking)

                warnings.extend(evaluation_warnings)

        else:
            for evaluation in evaluations:
                if evaluation.passed is False:
                    blocking_failures.append(
                        f"Evaluation {evaluation.evaluation_id} failed."
                    )

        if blocking_failures:
            verdict = Verdict.BLOCKED
        elif warnings:
            verdict = Verdict.DEGRADED
        else:
            verdict = Verdict.ASSURED

        metrics = {}

        for evaluation in evaluations:
            metrics.update(evaluation.metrics)

        evidence_ids = []

        for evaluation in evaluations:
            for evidence_id in evaluation.evidence_ids:
                if evidence_id not in evidence_ids:
                    evidence_ids.append(evidence_id)

        reasons = []

        if blocking_failures:
            reasons.extend(blocking_failures)

        if warnings:
            reasons.extend(warnings)

        if not reasons:
            reasons.append(
                "All applicable assurance requirements passed."
            )

        record = AssuranceRecord(
            assurance_id=assurance_id,
            system_id=system.system_id,
            system_version=system.version,
            environment=system.environment,
            verdict=verdict,
            evaluation_ids=[
                evaluation.evaluation_id
                for evaluation in evaluations
            ],
            evidence_ids=evidence_ids,
            policy_id=policy.policy_id if policy else None,
            metrics=metrics,
            reasons=reasons,
            created_at=datetime.now(timezone.utc).isoformat(),
            engine_version=self.ENGINE_VERSION,
        )

        self.store.save(record)

        return record