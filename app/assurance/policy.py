from __future__ import annotations

from typing import Dict, List

from .models import Policy, PolicyRule


class PolicyEngine:

    SUPPORTED_OPERATORS = {
        ">=",
        ">",
        "<=",
        "<",
        "==",
        "!=",
    }

    def validate_rule(self, rule: PolicyRule) -> None:
        if rule.operator not in self.SUPPORTED_OPERATORS:
            raise ValueError(
                f"Unsupported policy operator: {rule.operator}"
            )

        if rule.severity not in {"blocking", "warning"}:
            raise ValueError(
                f"Unsupported policy severity: {rule.severity}"
            )

    def evaluate_rule(
        self,
        rule: PolicyRule,
        metrics: Dict[str, float],
    ) -> bool:

        self.validate_rule(rule)

        if rule.metric not in metrics:
            return False

        actual = metrics[rule.metric]
        expected = rule.threshold

        if rule.operator == ">=":
            return actual >= expected
        if rule.operator == ">":
            return actual > expected
        if rule.operator == "<=":
            return actual <= expected
        if rule.operator == "<":
            return actual < expected
        if rule.operator == "==":
            return actual == expected
        if rule.operator == "!=":
            return actual != expected

        raise ValueError(f"Unsupported operator: {rule.operator}")

    def evaluate(
        self,
        policy: Policy,
        metrics: Dict[str, float],
    ) -> tuple[bool, List[str], List[str]]:

        blocking_failures: List[str] = []
        warnings: List[str] = []

        for rule in policy.rules:
            passed = self.evaluate_rule(rule, metrics)

            if passed:
                continue

            description = (
                rule.description
                or f"{rule.metric} {rule.operator} {rule.threshold}"
            )

            if rule.severity == "blocking":
                blocking_failures.append(description)
            else:
                warnings.append(description)

        return (
            len(blocking_failures) == 0,
            blocking_failures,
            warnings,
        )
