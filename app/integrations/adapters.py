from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .generic import SUPPORTED_PROVIDERS

@dataclass
class AdapterResult:
    provider: str
    normalized: dict[str,Any]
    evidence_type: str

class ProviderAdapter:
    def __init__(self, provider:str):
        if provider not in SUPPORTED_PROVIDERS: raise ValueError(f'Unsupported provider: {provider}')
        self.provider=provider
    def normalize(self,payload:dict[str,Any]) -> AdapterResult:
        return AdapterResult(self.provider, {'provider':self.provider,'payload':payload}, 'provider_event')

class IntegrationRegistry:
    def __init__(self): self._adapters={p:ProviderAdapter(p) for p in SUPPORTED_PROVIDERS}
    def providers(self): return sorted(self._adapters)
    def normalize(self, provider:str, payload:dict[str,Any]): return self._adapters[provider].normalize(payload)
