from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import requests


@dataclass
class AAIActionDenied(RuntimeError):
    decision: dict


class AAIRuntimeClient:
    """Small integration client: authorize first, then invoke the real tool locally."""

    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _post(self, path: str, payload: dict) -> dict:
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        r = requests.post(self.base_url + path, json=payload, headers=headers, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def authorize(self, **action: Any) -> dict:
        return self._post("/v1/runtime/agent-authorize", action)

    def guarded_call(self, executor: Callable[[dict], Any], **action: Any) -> Any:
        decision = self.authorize(**action)
        if decision["decision"] != "ALLOW":
            raise AAIActionDenied(decision)
        return executor(action)
