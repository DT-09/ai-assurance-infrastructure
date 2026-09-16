from __future__ import annotations
from typing import Any
import httpx

class AssuranceClient:
    def __init__(self,base_url:str,api_key:str,timeout:float=20.0):
        self.base_url=base_url.rstrip("/"); self.client=httpx.Client(timeout=timeout,headers={"X-API-Key":api_key})
    def close(self): self.client.close()
    def _request(self,method,path,**kwargs):
        r=self.client.request(method,self.base_url+path,**kwargs); r.raise_for_status(); return r.json()
    def create_asset(self,**data): return self._request("POST","/v1/control/assets",json=data)
    def create_version(self,asset_id,**data): return self._request("POST",f"/v1/control/assets/{asset_id}/versions",json=data)
    def add_dependency(self,**data): return self._request("POST","/v1/control/dependencies",json=data)
    def record_evidence(self,**data): return self._request("POST","/v1/control/evidence",json=data)
    def record_evaluation(self,**data): return self._request("POST","/v1/control/evaluations",json=data)
    def trust(self,asset_id): return self._request("GET",f"/v1/control/assets/{asset_id}/trust")
    def recompute_trust(self,asset_id): return self._request("POST",f"/v1/control/assets/{asset_id}/trust/recompute")
    def decide(self,**data): return self._request("POST","/v1/control/decisions",json=data)
    def graph(self): return self._request("GET","/v1/control/graph")
    def impact(self,asset_id): return self._request("GET",f"/v1/control/assets/{asset_id}/impact")
    def evidence(self,asset_id): return self._request("GET",f"/v1/control/assets/{asset_id}/evidence")
    def passport(self,asset_id): return self._request("GET",f"/v1/control/assets/{asset_id}/passport")
    def audit(self,limit=100): return self._request("GET",f"/v1/control/audit?limit={limit}")
    def verify_audit(self): return self._request("GET","/v1/control/audit/verify")
    def manifest(self): return self._request("GET","/v1/control/protocol/manifest")
