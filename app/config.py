from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


def _csv(value: str) -> List[str]:
    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


@dataclass(frozen=True)
class Settings:
    environment: str
    cors_origins: List[str]
    trusted_hosts: List[str]
    bootstrap_key: str | None

    identity_db: str
    control_plane_db: str
    assurance_db: str
    evidence_db: str
    policy_db: str
    trust_db: str

    database_url: str | None
    db_connect_timeout_seconds: float

    @property
    def is_production(self) -> bool:
        return self.environment in {
            "production",
            "prod",
        }

    @property
    def database_backend(self) -> str:
        return (
            "postgresql"
            if self.database_url
            else "sqlite"
        )

    def validate(self) -> None:
        if self.is_production:
            if not self.database_url:
                raise RuntimeError(
                    "Production requires ASSURANCE_DATABASE_URL "
                    "with a PostgreSQL connection string."
                )

            if not self.database_url.startswith(
                ("postgresql://", "postgres://")
            ):
                raise RuntimeError(
                    "ASSURANCE_DATABASE_URL must be a "
                    "PostgreSQL connection string."
                )

    @classmethod
    def from_env(cls) -> "Settings":
        environment = (
            os.getenv(
                "ASSURANCE_ENV",
                "development",
            )
            .strip()
            .lower()
        )

        origins = _csv(
            os.getenv(
                "ASSURANCE_CORS_ORIGINS",
                "*",
            )
        )

        hosts = _csv(
            os.getenv(
                "ASSURANCE_TRUSTED_HOSTS",
                "*",
            )
        )

        database_url = (
            os.getenv(
                "ASSURANCE_DATABASE_URL",
                "",
            ).strip()
            or None
        )

        timeout = float(
            os.getenv(
                "ASSURANCE_DB_CONNECT_TIMEOUT",
                "10",
            )
        )

        return cls(
            environment=environment,

            cors_origins=origins or ["*"],
            trusted_hosts=hosts or ["*"],

            bootstrap_key=os.getenv(
                "ASSURANCE_BOOTSTRAP_KEY"
            ),

            identity_db=os.getenv(
                "ASSURANCE_IDENTITY_DB",
                "data/identity.db",
            ),

            control_plane_db=os.getenv(
                "ASSURANCE_CONTROL_PLANE_DB",
                "data/control_plane.db",
            ),

            assurance_db=os.getenv(
                "ASSURANCE_ASSURANCE_DB",
                "data/assurance.db",
            ),

            evidence_db=os.getenv(
                "ASSURANCE_EVIDENCE_DB",
                "data/evidence.db",
            ),

            policy_db=os.getenv(
                "ASSURANCE_POLICY_DB",
                "data/policies.db",
            ),

            trust_db=os.getenv(
                "ASSURANCE_TRUST_DB",
                "data/trust.db",
            ),

            database_url=database_url,

            db_connect_timeout_seconds=timeout,
        )


settings = Settings.from_env()
