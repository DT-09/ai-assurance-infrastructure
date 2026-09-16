from __future__ import annotations

from typing import Any, Optional

import httpx


class AssuranceClientError(RuntimeError):
    pass


class AssuranceAuthenticationError(AssuranceClientError):
    pass


class AssuranceClient:
    """Small vendor-neutral Python client for the AI Assurance Control Plane."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        response = self._client.request(method, path, **kwargs)
        if response.status_code in {401, 403}:
            raise AssuranceAuthenticationError(self._message(response))
        if response.status_code >= 400:
            raise AssuranceClientError(self._message(response))
        return response.json()

    @staticmethod
    def _message(response: httpx.Response) -> str:
        try:
            data = response.json()
            if isinstance(data, dict) and data.get("detail"):
                return str(data["detail"])
        except ValueError:
            pass
        return f"Control Plane request failed: HTTP {response.status_code}"

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/v1/control/health")

    def protocol(self) -> dict[str, Any]:
        return self._request("GET", "/v1/control/protocol/manifest")

    def protocol_manifest(self):
        return self._request("GET", "/protocol.json")

    def verify_passport_public(self, passport: dict[str, Any], evidence: Optional[list[dict[str, Any]]] = None):
        return self._request("POST", "/v1/verify/passport", json={"passport": passport, "evidence": evidence or []})

    def conformance(self, document: dict[str, Any]):
        return self._request("POST", "/v1/protocol/conformance", json=document)

    def create_project(self, name: str, metadata: Optional[dict[str, Any]] = None):
        return self._request("POST", "/v1/control/projects", json={"name": name, "metadata": metadata or {}})

    def create_asset(self, project_id: str, name: str, asset_type: str = "agent", owner: Optional[str] = None, metadata: Optional[dict[str, Any]] = None):
        return self._request("POST", "/v1/control/assets", json={"project_id": project_id, "name": name, "asset_type": asset_type, "owner": owner, "metadata": metadata or {}})

    def create_version(self, asset_id: str, version: str, environment: str, model: Optional[str] = None, framework: Optional[str] = None, metadata: Optional[dict[str, Any]] = None):
        return self._request("POST", f"/v1/control/assets/{asset_id}/versions", json={"version": version, "environment": environment, "model": model, "framework": framework, "metadata": metadata or {}})

    def get_asset(self, asset_id: str):
        return self._request("GET", f"/v1/control/assets/{asset_id}")

    def assure(self, asset_id: str, version: str, environment: str, evaluations: list[dict[str, Any]]):
        return self._request("POST", f"/v1/control/assets/{asset_id}/assure", json={"version": version, "environment": environment, "evaluations": evaluations})

    def trust(self, asset_id: str, version_id: str):
        return self._request("GET", f"/v1/control/assets/{asset_id}/trust/{version_id}")

    def deployment_check(self, asset_id: str, version_id: str):
        return self._request("POST", f"/v1/control/assets/{asset_id}/versions/{version_id}/deployment-check")

    def runtime_check(self, asset_id: str, version_id: str):
        return self._request("POST", f"/v1/control/assets/{asset_id}/versions/{version_id}/runtime-check")

    def passport(self, assurance_id: str):
        return self._request("GET", f"/v1/control/assurance/{assurance_id}/passport")

    def verify_passport(self, passport: dict[str, Any], evidence: Optional[list[dict[str, Any]]] = None):
        response = self._client.post("/v1/control/verify/passport", json={"passport": passport, "evidence": evidence or []})
        if response.status_code >= 400:
            raise AssuranceClientError(self._message(response))
        return response.json()
