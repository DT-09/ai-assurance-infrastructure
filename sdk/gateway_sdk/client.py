from typing import Any

import httpx

from .models import (
    Agent,
    Credential,
    DecisionResult,
    Organization,
)


class GatewayError(Exception):
    """Base exception for Gateway SDK errors."""


class GatewayAuthenticationError(GatewayError):
    """Raised when the API key is missing or invalid."""


class GatewayNotFoundError(GatewayError):
    """Raised when the requested resource does not exist."""


class GatewayConflictError(GatewayError):
    """Raised when the request conflicts with current state."""


class GatewayClient:
    """
    Python client for the AI Agent Trust & Control Plane.

    Example:

        client = GatewayClient(
            base_url="https://example.com",
            api_key="gw_...",
        )

        result = client.evaluate(
            agent_id="support-agent",
            tool="crm",
            action="read",
        )

        print(result.decision)
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
    ):
        if not base_url:
            raise ValueError(
                "base_url is required"
            )

        if not api_key:
            raise ValueError(
                "api_key is required"
            )

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict[str, Any]:

        response = self._client.request(
            method,
            path,
            **kwargs,
        )

        if response.status_code in {
            401,
            403,
        }:
            raise GatewayAuthenticationError(
                self._error_message(response)
            )

        if response.status_code == 404:
            raise GatewayNotFoundError(
                self._error_message(response)
            )

        if response.status_code == 409:
            raise GatewayConflictError(
                self._error_message(response)
            )

        if response.status_code >= 400:
            raise GatewayError(
                self._error_message(response)
            )

        return response.json()

    @staticmethod
    def _error_message(
        response: httpx.Response,
    ) -> str:

        try:
            data = response.json()

            if isinstance(data, dict):
                detail = data.get("detail")

                if detail:
                    return str(detail)

        except ValueError:
            pass

        return (
            f"Gateway request failed "
            f"with status {response.status_code}"
        )

    # -------------------------
    # Health
    # -------------------------

    def health(self) -> dict[str, Any]:
        """
        Check gateway health.

        This endpoint is public.
        """

        response = self._client.get("/health")

        if response.status_code >= 400:
            raise GatewayError(
                self._error_message(response)
            )

        return response.json()

    # -------------------------
    # Organization
    # -------------------------

    def get_organization(self) -> Organization:
        data = self._request(
            "GET",
            "/api/organization",
        )

        return Organization.from_dict(data)

    # -------------------------
    # Credentials
    # -------------------------

    def create_credential(
        self,
        name: str = "default",
    ) -> dict[str, Any]:
        """
        Create a new API credential.

        The plaintext API key is returned only once
        by the gateway.
        """

        return self._request(
            "POST",
            "/api/credentials",
            json={
                "name": name,
            },
        )

    def list_credentials(
        self,
    ) -> list[Credential]:

        data = self._request(
            "GET",
            "/api/credentials",
        )

        return [
            Credential.from_dict(item)
            for item in data.get(
                "credentials",
                [],
            )
        ]

    def revoke_credential(
        self,
        credential_id: str,
    ) -> Credential:

        data = self._request(
            "POST",
            f"/api/credentials/"
            f"{credential_id}/revoke",
        )

        return Credential.from_dict(
            data["credential"]
        )

    # -------------------------
    # Agents
    # -------------------------

    def register_agent(
        self,
        agent_id: str,
        organization_id: str,
        owner: str,
        environment: str,
        qualification_status: str = (
            "NOT_QUALIFIED"
        ),
        policy: dict[str, Any] | None = None,
    ) -> Agent:

        payload = {
            "agent_id": agent_id,
            "organization_id": organization_id,
            "owner": owner,
            "environment": environment,
            "qualification_status": (
                qualification_status
            ),
            "policy": policy or {},
        }

        data = self._request(
            "POST",
            "/api/agents",
            json=payload,
        )

        return Agent.from_dict(
            data["agent"]
        )

    def list_agents(self) -> list[Agent]:

        data = self._request(
            "GET",
            "/api/agents",
        )

        return [
            Agent.from_dict(item)
            for item in data.get(
                "agents",
                [],
            )
        ]

    def get_agent(
        self,
        agent_id: str,
    ) -> Agent:

        data = self._request(
            "GET",
            f"/api/agents/{agent_id}",
        )

        return Agent.from_dict(data)

    def suspend_agent(
        self,
        agent_id: str,
    ) -> Agent:

        data = self._request(
            "POST",
            f"/api/agents/{agent_id}/suspend",
        )

        return self.get_agent(
            data["agent_id"]
        )

    def revoke_agent(
        self,
        agent_id: str,
    ) -> Agent:

        data = self._request(
            "POST",
            f"/api/agents/{agent_id}/revoke",
        )

        return self.get_agent(
            data["agent_id"]
        )

    def set_qualification(
        self,
        agent_id: str,
        qualification_status: str,
    ) -> Agent:

        data = self._request(
            "POST",
            f"/api/agents/{agent_id}/qualification",
            params={
                "qualification_status":
                    qualification_status,
            },
        )

        return self.get_agent(
            data["agent_id"]
        )

    # -------------------------
    # Control
    # -------------------------

    def evaluate(
        self,
        agent_id: str,
        tool: str,
        action: str,
        parameters: dict[str, Any] | None = None,
    ) -> DecisionResult:

        data = self._request(
            "POST",
            "/api/control/evaluate",
            json={
                "agent_id": agent_id,
                "tool": tool,
                "action": action,
                "parameters": parameters or {},
            },
        )

        return DecisionResult.from_dict(data)

    # -------------------------
    # Approvals
    # -------------------------

    def list_approvals(
        self,
    ) -> list[dict[str, Any]]:

        data = self._request(
            "GET",
            "/api/approvals",
        )

        return data.get(
            "approvals",
            [],
        )

    def get_approval(
        self,
        approval_id: str,
    ) -> dict[str, Any]:

        return self._request(
            "GET",
            f"/api/approvals/{approval_id}",
        )

    def approve(
        self,
        approval_id: str,
    ) -> dict[str, Any]:

        return self._request(
            "POST",
            f"/api/approvals/"
            f"{approval_id}/approve",
        )

    def reject(
        self,
        approval_id: str,
    ) -> dict[str, Any]:

        return self._request(
            "POST",
            f"/api/approvals/"
            f"{approval_id}/reject",
        )

    # -------------------------
    # Audit
    # -------------------------

    def audit(
        self,
    ) -> list[dict[str, Any]]:

        data = self._request(
            "GET",
            "/api/gateway/audit",
        )

        return data.get(
            "events",
            [],
        )