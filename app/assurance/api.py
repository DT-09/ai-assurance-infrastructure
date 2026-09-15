import uuid
from datetime import datetime, timezone
import hashlib
import json
import time
import socket
import ipaddress
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException

from .models import (
    SystemRecord,
    EvidenceRecord,
    EvaluationResult,
    Policy,
    PolicyRule,
)
from .registry import AssuranceRegistry
from .evidence import EvidenceStore
from .evaluation import EvaluationEngine
from .store import AssuranceStore
from .engine import AssuranceEngine
from .passport import AssurancePassport, verify_passport
from .verification import verify_evidence, verify_passport_evidence
from .graph import AssuranceGraph
from .provenance import ProvenanceService


router = APIRouter(
    prefix="/v1",
    tags=["AI Assurance Infrastructure"],
)


# -------------------------------------------------------------------
# Core services
# -------------------------------------------------------------------

registry = AssuranceRegistry()
evidence_store = EvidenceStore()
evaluation_engine = EvaluationEngine()
assurance_store = AssuranceStore()
assurance_engine = AssuranceEngine(
    store=assurance_store
)
graph = AssuranceGraph()

provenance = ProvenanceService(
    registry=registry,
    assurance_store=assurance_store,
    evidence_store=evidence_store,
    graph=graph,
)


# -------------------------------------------------------------------
# Provenance
# -------------------------------------------------------------------

@router.get("/provenance/systems/{system_id}")
def get_system_provenance(system_id: str):
    try:
        return provenance.get_system_status(system_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@router.get("/provenance/assurance/{assurance_id}")
def get_assurance_provenance(assurance_id: str):
    try:
        return provenance.get_assurance_provenance(
            assurance_id
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@router.get(
    "/provenance/systems/"
    "{system_id}/diff/{from_version}/{to_version}"
)
def compare_assurance_versions(
    system_id: str,
    from_version: str,
    to_version: str,
):
    try:
        return provenance.compare_versions(
            system_id=system_id,
            from_version=from_version,
            to_version=to_version,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )


def _validate_agent_url(agent_url: str) -> str:
    """Allow only public HTTP(S) endpoints."""

    parsed = urlparse(agent_url)

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(
            status_code=400,
            detail="agent_url must be an HTTP(S) URL.",
        )

    host = parsed.hostname

    try:
        addresses = socket.getaddrinfo(
            host,
            parsed.port
            or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        raise HTTPException(
            status_code=400,
            detail="Could not resolve agent_url host.",
        )

    for item in addresses:
        ip = item[4][0]
        address = ipaddress.ip_address(ip)

        if not address.is_global:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Private or local agent endpoints "
                    "are not allowed."
                ),
            )

    return agent_url


def _jsonable(value):
    """Convert Pydantic objects and nested values to JSON-safe data."""

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    if isinstance(value, dict):
        return {
            str(key): _jsonable(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [_jsonable(item) for item in value]

    return value


def _canonical_hash(payload: dict) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


# -------------------------------------------------------------------
# Passport helpers
# -------------------------------------------------------------------

def _build_passport(
    system,
    assurance,
):
    return AssurancePassport(
        passport_id=f"passport_{uuid.uuid4().hex}",
        assurance_id=assurance.assurance_id,
        system_id=system.system_id,
        system_version=system.version,
        environment=system.environment,
        verdict=(
            assurance.verdict.value
            if hasattr(assurance.verdict, "value")
            else str(assurance.verdict)
        ),
        metrics=assurance.metrics,
        policy_id=assurance.policy_id,
        evaluation_ids=assurance.evaluation_ids,
        evidence_ids=assurance.evidence_ids,
        reasons=assurance.reasons,
        engine_version=assurance.engine_version,
        created_at=assurance.created_at,
    )


def _verify_assurance_evidence(
    assurance,
):
    records = []

    for evidence_id in assurance.evidence_ids:
        evidence = evidence_store.get(evidence_id)

        if evidence is None:
            continue

        records.append(_jsonable(evidence))

    passport = {
        "system": {
            "system_id": assurance.system_id,
            "version": assurance.system_version,
        },
        "assurance": {
            "evidence_ids": assurance.evidence_ids,
        },
    }

    return verify_passport_evidence(
        passport=passport,
        evidence_records=records,
    )


# -------------------------------------------------------------------
# System registration
# -------------------------------------------------------------------

@router.post("/systems")
def register_system(payload: dict):
    system = SystemRecord(
        system_id=str(
            payload.get("system_id")
            or ""
        ),
        name=str(
            payload.get("name")
            or ""
        ),
        system_type=str(
            payload.get("system_type")
            or "agent"
        ),
        version=str(
            payload.get("version")
            or "1.0.0"
        ),
        environment=str(
            payload.get("environment")
            or "staging"
        ),
        model=payload.get("model"),
        framework=payload.get("framework"),
        owner=payload.get("owner"),
        metadata=payload.get("metadata") or {},
    )

    if not system.system_id:
        raise HTTPException(
            status_code=400,
            detail="system_id is required.",
        )

    registry.register(system)

    return {
        "status": "registered",
        "system": system,
    }


# -------------------------------------------------------------------
# System lookup
# -------------------------------------------------------------------

@router.get("/systems/{system_id}")
def get_system(system_id: str):
    system = registry.get(system_id)

    if system is None:
        raise HTTPException(
            status_code=404,
            detail=f"System '{system_id}' not found.",
        )

    return system


# -------------------------------------------------------------------
# Core assurance check
# -------------------------------------------------------------------

@router.post("/assurance/check")
def assurance_check(payload: dict):

    system_data = payload.get("system") or {}

    system = SystemRecord(
        system_id=str(
            system_data.get("system_id")
            or ""
        ),
        name=str(
            system_data.get("name")
            or "AI System"
        ),
        system_type=str(
            system_data.get("system_type")
            or "agent"
        ),
        version=str(
            system_data.get("version")
            or "1.0.0"
        ),
        environment=str(
            system_data.get("environment")
            or "staging"
        ),
        model=system_data.get("model"),
        framework=system_data.get("framework"),
        owner=system_data.get("owner"),
        metadata=system_data.get("metadata") or {},
    )

    if not system.system_id:
        raise HTTPException(
            status_code=400,
            detail="system.system_id is required.",
        )

    registry.register(system)

    metrics = payload.get("metrics") or {}

    evaluation_type = str(
        payload.get("evaluation_type")
        or "workflow"
    )

    evidence_payload = {
        "system": _jsonable(system),
        "metrics": metrics,
        "evaluation_type": evaluation_type,
        "source": "assurance_check",
        "created_at": _now(),
    }

    evidence = EvidenceRecord(
        evidence_id=(
            payload.get("evidence_id")
            or f"ev_{_canonical_hash(evidence_payload)[:24]}"
        ),
        evidence_type="evaluation_input",
        system_id=system.system_id,
        system_version=system.version,
        source="assurance_check",
        payload=evidence_payload,
        content_hash=_canonical_hash(
            evidence_payload
        ),
    )

    evidence_store.create(
        evidence_id=evidence.evidence_id,
        evidence_type=evidence.evidence_type,
        system_id=evidence.system_id,
        system_version=evidence.system_version,
        source=evidence.source,
        payload=evidence.payload,
    )

    evaluation = evaluation_engine.evaluate_metrics(
        evaluation_id=f"eval_{uuid.uuid4().hex}",
        system_id=system.system_id,
        system_version=system.version,
        evaluation_type=evaluation_type,
        metrics=metrics,
        evidence_ids=[evidence.evidence_id],
    )

    policy_data = payload.get("policy")

    policy = None

    if policy_data:
        rules = []

        for rule in policy_data.get("rules", []):
            rules.append(
                PolicyRule(
                    metric=str(
                        rule.get("metric")
                        or ""
                    ),
                    operator=str(
                        rule.get("operator")
                        or ">="
                    ),
                    threshold=float(
                        rule.get("threshold", 0)
                    ),
                    severity=str(
                        rule.get("severity")
                        or "blocking"
                    ),
                    description=str(
                        rule.get("description")
                        or ""
                    ),
                )
            )

        policy = Policy(
            policy_id=str(
                policy_data.get("policy_id")
                or "default-policy"
            ),
            name=str(
                policy_data.get("name")
                or "AI Assurance Policy"
            ),
            version=str(
                policy_data.get("version")
                or "1.0.0"
            ),
            rules=rules,
            metadata=policy_data.get("metadata") or {},
        )

    assurance = assurance_engine.issue(
        system=system,
        evaluations=[evaluation],
        policy=policy,
    )

    passport = _build_passport(
        system=system,
        assurance=assurance,
    )

    verification = _verify_assurance_evidence(
        assurance=assurance,
    )

    # ---------------------------------------------------------------
    # Synchronize complete assurance lifecycle into graph
    # ---------------------------------------------------------------

    graph_result = graph.sync_assurance(
        system=system,
        assurance=assurance,
        evaluations=[evaluation],
        evidence=[evidence],
        policy=policy,
    )

    return {
        "status": "assurance_issued",
        "system": system,
        "evidence": evidence,
        "evaluation": evaluation,
        "assurance": assurance,
        "passport": passport,
        "verification": verification,
        "graph": graph_result,
    }


# -------------------------------------------------------------------
# REMOTE AGENT ASSURANCE
# -------------------------------------------------------------------

@router.post("/assurance/remote")
async def remote_assurance(payload: dict):
    """
    Execute an external AI agent against representative test cases
    and issue a persistent AssuranceRecord.

    Expected agent request:

        {
            "input": <case input>
        }

    Expected agent response:

        {
            "output": <value>,
            "cost_usd": <optional number>
        }

    A raw JSON value is also accepted as the output.
    """

    agent_url = payload.get("agent_url")

    if not isinstance(agent_url, str):
        raise HTTPException(
            status_code=400,
            detail="agent_url is required.",
        )

    agent_url = _validate_agent_url(agent_url)

    system_data = payload.get("system") or {}

    system_id = str(
        system_data.get("system_id")
        or payload.get("system_id")
        or ""
    )

    if not system_id:
        raise HTTPException(
            status_code=400,
            detail="system.system_id is required.",
        )

    system_name = str(
        system_data.get("name")
        or payload.get("name")
        or "Remote AI Agent"
    )

    system_version = str(
        system_data.get("version")
        or payload.get("version")
        or "1.0.0"
    )

    environment = str(
        system_data.get("environment")
        or payload.get("environment")
        or "staging"
    )

    cases = payload.get("test_cases") or []

    if not cases:
        raise HTTPException(
            status_code=400,
            detail="At least one test case is required.",
        )

    # ---------------------------------------------------------------
    # Register the system
    # ---------------------------------------------------------------

    system = SystemRecord(
        system_id=system_id,
        name=system_name,
        system_type=str(
            system_data.get("system_type")
            or "agent"
        ),
        version=system_version,
        environment=environment,
        model=system_data.get("model"),
        framework=system_data.get("framework"),
        owner=system_data.get("owner"),
        metadata={
            **(
                system_data.get("metadata")
                or {}
            ),
            "agent_url": agent_url,
        },
    )

    registry.register(system)

    # ---------------------------------------------------------------
    # Execute agent
    # ---------------------------------------------------------------

    executed_cases = []

    timeout = httpx.Timeout(
        float(
            payload.get(
                "timeout_seconds",
                30,
            )
        ),
        connect=10.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
    ) as client:

        for index, case in enumerate(
            cases,
            start=1,
        ):

            if not isinstance(case, dict):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Test case {index} "
                        "must be an object."
                    ),
                )

            case_id = str(
                case.get("case_id")
                or f"CASE-{index:03d}"
            )

            input_data = case.get(
                "input_data"
            )

            expected_output = case.get(
                "expected_output"
            )

            started = time.perf_counter()

            actual_output = None
            cost_usd = 0.0
            tool_error = False
            error_message = None

            try:
                response = await client.post(
                    agent_url,
                    json={
                        "input": input_data,
                    },
                )

                latency_ms = (
                    time.perf_counter()
                    - started
                ) * 1000

                response.raise_for_status()

                response_data = response.json()

                if (
                    isinstance(
                        response_data,
                        dict,
                    )
                    and "output"
                    in response_data
                ):
                    actual_output = (
                        response_data["output"]
                    )

                    cost_usd = max(
                        float(
                            response_data.get(
                                "cost_usd",
                                0,
                            )
                            or 0
                        ),
                        0,
                    )

                else:
                    actual_output = response_data

            except Exception as exc:

                latency_ms = (
                    time.perf_counter()
                    - started
                ) * 1000

                tool_error = True
                error_message = str(exc)

            success = (
                not tool_error
                and actual_output
                == expected_output
            )

            executed_case = {
                "case_id": case_id,
                "input_data": input_data,
                "expected_output": expected_output,
                "actual_output": actual_output,
                "success": success,
                "latency_ms": latency_ms,
                "tool_error": tool_error,
                "critical": bool(
                    case.get(
                        "critical",
                        False,
                    )
                ),
                "human_review_required": bool(
                    case.get(
                        "human_review_required",
                        False,
                    )
                ),
                "estimated_cost_usd": cost_usd,
            }

            if error_message:
                executed_case[
                    "error_message"
                ] = error_message

                executed_case[
                    "failure_category"
                ] = "TOOL_ERROR"

            executed_cases.append(
                executed_case
            )

    # ---------------------------------------------------------------
    # Calculate qualification metrics
    # ---------------------------------------------------------------

    total = len(executed_cases)

    successful = sum(
        1
        for case in executed_cases
        if case["success"]
    )

    critical_failures = sum(
        1
        for case in executed_cases
        if (
            not case["success"]
            and case["critical"]
        )
    )

    tool_failures = sum(
        1
        for case in executed_cases
        if case["tool_error"]
    )

    human_review_cases = sum(
        1
        for case in executed_cases
        if case["human_review_required"]
    )

    reliability = (
        successful / total * 100
        if total
        else 0
    )

    human_review_rate = (
        human_review_cases
        / total
        * 100
        if total
        else 0
    )

    average_latency = (
        sum(
            case["latency_ms"]
            for case in executed_cases
        )
        / total
        if total
        else 0
    )

    total_cost = sum(
        case["estimated_cost_usd"]
        for case in executed_cases
    )

    average_cost = (
        total_cost / total
        if total
        else 0
    )

    metrics = {
        "total_cases": float(total),
        "successful_cases": float(
            successful
        ),
        "reliability": round(
            reliability,
            4,
        ),
        "critical_failures": float(
            critical_failures
        ),
        "tool_failures": float(
            tool_failures
        ),
        "human_review_rate": round(
            human_review_rate,
            4,
        ),
        "average_latency_ms": round(
            average_latency,
            4,
        ),
        "total_cost_usd": round(
            total_cost,
            6,
        ),
        "average_cost_per_case_usd": round(
            average_cost,
            6,
        ),
    }

    # ---------------------------------------------------------------
    # Create evidence
    # ---------------------------------------------------------------

    evidence_payload = {
        "agent_url": agent_url,
        "system": _jsonable(system),
        "test_cases": executed_cases,
        "metrics": metrics,
        "execution_type": "remote_agent",
        "created_at": _now(),
    }

    evidence = EvidenceRecord(
        evidence_id=(
            "ev_"
            + _canonical_hash(
                evidence_payload
            )[:24]
        ),
        evidence_type="remote_execution",
        system_id=system.system_id,
        system_version=system.version,
        source="remote_agent",
        payload=evidence_payload,
        content_hash=_canonical_hash(
            evidence_payload
        ),
    )

    evidence_store.create(
        evidence_id=evidence.evidence_id,
        evidence_type=evidence.evidence_type,
        system_id=evidence.system_id,
        system_version=evidence.system_version,
        source=evidence.source,
        payload=evidence.payload,
    )

    # ---------------------------------------------------------------
    # Evaluation
    # ---------------------------------------------------------------

    evaluation = evaluation_engine.evaluate_metrics(
        evaluation_id=f"eval_{uuid.uuid4().hex}",
        system_id=system.system_id,
        system_version=system.version,
        evaluation_type="remote_workflow",
        metrics=metrics,
        evidence_ids=[
            evidence.evidence_id
        ],
    )

    # ---------------------------------------------------------------
    # Policy
    # ---------------------------------------------------------------

    policy_data = payload.get("policy")

    if policy_data:
        policy_rules = policy_data.get(
            "rules",
            [],
        )

        policy = Policy(
            policy_id=str(
                policy_data.get(
                    "policy_id",
                    "remote-policy-v1",
                )
            ),
            name=str(
                policy_data.get(
                    "name",
                    "Remote Agent Production Policy",
                )
            ),
            version=str(
                policy_data.get(
                    "version",
                    "1.0.0",
                )
            ),
            rules=[
                PolicyRule(
                    metric=str(
                        rule["metric"]
                    ),
                    operator=str(
                        rule.get(
                            "operator",
                            ">=",
                        )
                    ),
                    threshold=float(
                        rule.get(
                            "threshold",
                            0,
                        )
                    ),
                    severity=str(
                        rule.get(
                            "severity",
                            "blocking",
                        )
                    ),
                    description=str(
                        rule.get(
                            "description",
                            "",
                        )
                    ),
                )
                for rule in policy_rules
            ],
            metadata=policy_data.get(
                "metadata"
            )
            or {},
        )

    else:
        # Default production-oriented policy.
        policy = Policy(
            policy_id="default-production-v1",
            name="Default Production AI Policy",
            version="1.0.0",
            rules=[
                PolicyRule(
                    metric="reliability",
                    operator=">=",
                    threshold=float(
                        payload.get(
                            "target_reliability",
                            95,
                        )
                    ),
                    severity="blocking",
                    description=(
                        "Minimum required workflow reliability."
                    ),
                ),
                PolicyRule(
                    metric="critical_failures",
                    operator="==",
                    threshold=float(
                        payload.get(
                            "maximum_critical_failures",
                            0,
                        )
                    ),
                    severity="blocking",
                    description=(
                        "Maximum permitted critical failures."
                    ),
                ),
                PolicyRule(
                    metric="human_review_rate",
                    operator="<=",
                    threshold=float(
                        payload.get(
                            "maximum_human_review_rate",
                            20,
                        )
                    ),
                    severity="warning",
                    description=(
                        "Maximum expected human-review rate."
                    ),
                ),
            ],
        )

    # ---------------------------------------------------------------
    # Issue AssuranceRecord
    # ---------------------------------------------------------------

    assurance = assurance_engine.issue(
        system=system,
        evaluations=[evaluation],
        policy=policy,
    )

    # ---------------------------------------------------------------
    # Synchronize remote assurance into graph
    # ---------------------------------------------------------------

    graph_result = graph.sync_assurance(
        system=system,
        assurance=assurance,
        evaluations=[evaluation],
        evidence=[evidence],
        policy=policy,
    )

    # ---------------------------------------------------------------
    # Return complete machine-readable result
    # ---------------------------------------------------------------

    return {
        "status": "assurance_issued",
        "assurance": assurance,
        "system": system,
        "evaluation": evaluation,
        "evidence": evidence,
        "execution": {
            "agent_url": agent_url,
            "cases": executed_cases,
            "metrics": metrics,
        },
        "graph": graph_result,
    }


# -------------------------------------------------------------------
# Assurance Passport
# -------------------------------------------------------------------

@router.get(
    "/assurance/{assurance_id}/passport"
)
def get_assurance_passport(assurance_id: str):
    assurance = assurance_store.get(
        assurance_id
    )

    if assurance is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Assurance record "
                f"'{assurance_id}' not found."
            ),
        )

    system = registry.get(
        assurance.system_id
    )

    if system is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"System "
                f"'{assurance.system_id}' not found."
            ),
        )

    passport = _build_passport(
        system=system,
        assurance=assurance,
    )

    return passport


# -------------------------------------------------------------------
# Independent assurance verification
# -------------------------------------------------------------------

@router.post(
    "/assurance/verify"
)
def verify_assurance(payload: dict):
    passport_data = payload.get("passport")

    if not isinstance(
        passport_data,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail="passport is required.",
        )

    passport = AssurancePassport.from_dict(
        passport_data
    )

    passport_valid = verify_passport(
        passport.to_dict()
    )

    evidence_result = verify_passport_evidence(
        passport=passport.to_dict(),
        evidence_records=payload.get(
            "evidence",
            [],
        ),
    )

    return {
        "valid": (
            passport_valid
            and evidence_result["valid"]
        ),
        "passport_valid": passport_valid,
        "evidence_verification": evidence_result,
    }


# -------------------------------------------------------------------
# Assurance history
# -------------------------------------------------------------------

@router.get(
    "/systems/{system_id}/assurance"
)
def list_assurance(system_id: str):
    return {
        "system_id": system_id,
        "records": assurance_store.list_for_system(
            system_id
        ),
    }


# -------------------------------------------------------------------
# Evidence history
# -------------------------------------------------------------------

@router.get(
    "/systems/{system_id}/evidence"
)
def list_evidence(system_id: str):
    return {
        "system_id": system_id,
        "evidence": evidence_store.list_for_system(
            system_id
        ),
    }


# -------------------------------------------------------------------
# Single assurance record
# -------------------------------------------------------------------

@router.get(
    "/assurance/{assurance_id}"
)
def get_assurance(assurance_id: str):
    record = assurance_store.get(
        assurance_id
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Assurance record "
                f"'{assurance_id}' not found."
            ),
        )

    return record


# -------------------------------------------------------------------
# Assurance Graph
# -------------------------------------------------------------------

@router.get(
    "/systems/{system_id}/graph"
)
def get_system_graph(system_id: str):
    try:
        return graph.graph_for_system(system_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )