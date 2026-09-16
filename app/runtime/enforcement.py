from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

@dataclass
class RuntimeRequest:
    asset_id: str
    action: str
    context: dict[str, Any]

@dataclass
class RuntimeDecision:
    decision: str
    allowed: bool
    reasons: list[str]
    trust_state: str | None

class RuntimeEnforcer:
    """Library-level runtime gate. Integrate before every consequential agent action."""
    def __init__(self, decision_fn: Callable[..., dict[str,Any]]): self.decision_fn=decision_fn
    def authorize(self, req: RuntimeRequest) -> RuntimeDecision:
        d=self.decision_fn(req.asset_id, req.action, req.context)
        decision=d.get('decision','DENY'); return RuntimeDecision(decision, decision=='ALLOW', d.get('reasons',[]), d.get('trust_state'))
    def guard(self, req: RuntimeRequest):
        result=self.authorize(req)
        if not result.allowed: raise PermissionError(f'AI Assurance runtime control: {result.decision}: {"; ".join(result.reasons)}')
        return result
