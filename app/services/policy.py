from __future__ import annotations

from typing import Any


class PolicyEngine:
    """Deterministic policy decision layer.

    Trust state is the safety floor. Bound workspace policies add explicit
    constraints without allowing a policy to manufacture trust.
    """

    def __init__(self, store):
        self.store = store

    @staticmethod
    def _compare(value: float, operator: str, threshold: float) -> bool:
        return {
            "==": value == threshold,
            "!=": value != threshold,
            ">": value > threshold,
            ">=": value >= threshold,
            "<": value < threshold,
            "<=": value <= threshold,
        }.get(operator, False)

    def _apply_rules(self, policy: dict[str, Any], trust: dict[str, Any], action: str, context: dict[str, Any]):
        rules = policy.get("rules") or {}
        reasons: list[str] = []
        decision = "ALLOW"

        # Canonical scalar rules.
        if "minimum_score" in rules and trust["score"] < float(rules["minimum_score"]):
            decision, reasons = "DENY", ["Policy minimum_score is not satisfied."]
        if "minimum_reliability" in rules and trust["reliability"] < float(rules["minimum_reliability"]):
            decision, reasons = "DENY", ["Policy minimum_reliability is not satisfied."]
        if "maximum_critical_failures" in rules and trust["critical_failures"] > int(rules["maximum_critical_failures"]):
            decision, reasons = "DENY", ["Policy maximum_critical_failures is exceeded."]
        if "maximum_human_review_rate" in rules and trust["human_review_rate"] > float(rules["maximum_human_review_rate"]):
            decision, reasons = "DENY", ["Policy maximum_human_review_rate is exceeded."]

        # Optional action allow-list.
        actions = rules.get("allowed_actions")
        if actions and action not in actions:
            decision, reasons = "DENY", [f"Action '{action}' is not allowed by the bound policy."]

        # Generic metric rules: [{"metric","operator","threshold","effect"}]
        for rule in rules.get("rules", []) if isinstance(rules.get("rules"), list) else []:
            metric = str(rule.get("metric", ""))
            if not metric or metric not in trust:
                continue
            try:
                ok = self._compare(float(trust[metric]), str(rule.get("operator", ">=")), float(rule.get("threshold", 0)))
            except (TypeError, ValueError):
                ok = False
            if not ok:
                effect = str(rule.get("effect", "deny")).lower()
                if effect == "review":
                    decision, reasons = ("REVIEW" if decision == "ALLOW" else decision), reasons + [f"Policy rule failed: {metric}."]
                else:
                    decision, reasons = "DENY", reasons + [f"Policy rule failed: {metric}."]

        return decision, reasons

    def decide(self, org_id, asset_id, action, context, request_id=None):
        if not self.store.get_asset(org_id, asset_id):
            return self.store.add_decision(org_id, asset_id, action, "DENY", ["Asset not found."], context, request_id)

        trust = self.store.latest_trust(org_id, asset_id)
        if not trust:
            decision, reasons = "DENY", ["No current trust state exists."]
        elif trust["state"] == "BLOCKED":
            decision, reasons = "DENY", ["Asset is BLOCKED."]
        elif trust["state"] == "DEGRADED":
            decision, reasons = "REVIEW", ["Asset is DEGRADED."]
        else:
            decision, reasons = "ALLOW", ["Asset is ASSURED."]

        environment = context.get("environment", "production")
        policy = self.store.effective_policy(org_id, asset_id, environment)
        if policy and trust:
            pdecision, preasons = self._apply_rules(policy, trust, action, context)
            if pdecision == "DENY":
                decision = "DENY"
            elif pdecision == "REVIEW" and decision == "ALLOW":
                decision = "REVIEW"
            reasons.extend(preasons)
            if policy.get("name"):
                reasons.append(f"Policy: {policy['name']} v{policy.get('version','1.0')}.")

        required = context.get("required_state")
        if required and trust and trust["state"] != required:
            decision, reasons = "DENY", reasons + ["Requested trust state does not match the current state."]
        min_score = context.get("minimum_score")
        if min_score is not None and (not trust or trust["score"] < float(min_score)):
            decision, reasons = "DENY", reasons + ["Current trust score is below the requested minimum."]

        result = self.store.add_decision(org_id, asset_id, action, decision, reasons, context, request_id)
        return result | {"trust_state": trust, "policy": policy}
