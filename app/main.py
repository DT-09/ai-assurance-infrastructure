from pathlib import Path
import csv
import io
import json
import os
import ipaddress
import time

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import httpx
import socket
from urllib.parse import urlparse

from .models import Workflow
from .engine import qualify_workflow


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def _validate_agent_url(agent_url: str) -> str:
    """Allow only public HTTP(S) agent endpoints for remote qualification."""
    parsed = urlparse(agent_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="agent_url must be an HTTP(S) URL.")

    host = parsed.hostname
    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="Could not resolve agent_url host.")

    for item in addresses:
        ip = item[4][0]
        addr = ipaddress.ip_address(ip)
        if not addr.is_global:
            raise HTTPException(status_code=400, detail="Private or local agent endpoints are not allowed.")
    return agent_url


app = FastAPI(
    title="AI Workflow Qualification",
    version="1.0.0",
    description="Deployment qualification engine for AI workflows.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return FileResponse(
        STATIC_DIR / "index.html",
        media_type="text/html",
    )


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "AI Workflow Qualification",
        "version": "1.0.0",
    }


@app.get("/api/demo")
def demo():
    workflow = Workflow(
        name="Customer Refund Agent",
        description="AI agent responsible for processing customer refund requests.",
        target_reliability=95,
        maximum_critical_failures=0,
        maximum_human_review_rate=20,
        test_cases=[
            {
                "case_id": "REF-001",
                "expected_output": "Approve refund",
                "actual_output": "Approve refund",
                "success": True,
                "latency_ms": 1200,
                "tool_error": False,
                "critical": False,
                "human_review_required": False,
                "estimated_cost_usd": 0.03,
            },
            {
                "case_id": "REF-002",
                "expected_output": "Reject refund",
                "actual_output": "Reject refund",
                "success": True,
                "latency_ms": 1400,
                "tool_error": False,
                "critical": False,
                "human_review_required": False,
                "estimated_cost_usd": 0.03,
            },
            {
                "case_id": "REF-003",
                "expected_output": "Escalate",
                "actual_output": "Escalate",
                "success": True,
                "latency_ms": 1700,
                "tool_error": False,
                "critical": False,
                "human_review_required": True,
                "estimated_cost_usd": 0.04,
            },
            {
                "case_id": "REF-004",
                "expected_output": "Reject refund",
                "actual_output": "Approve refund",
                "success": False,
                "latency_ms": 2100,
                "tool_error": False,
                "critical": True,
                "human_review_required": False,
                "estimated_cost_usd": 0.03,
            },
        ],
    )

    return qualify_workflow(workflow)


@app.post("/api/qualify")
def qualify(workflow: Workflow):
    return qualify_workflow(workflow)



@app.post("/api/qualify/remote")
async def qualify_remote(payload: dict):
    """Run qualification against a company's HTTP agent endpoint.

    The agent must accept POST JSON: {"input": <case input>} and return
    either a JSON value or {"output": <value>, "cost_usd": <number>}.
    """
    agent_url = payload.get("agent_url")
    if not isinstance(agent_url, str):
        raise HTTPException(status_code=400, detail="agent_url is required.")
    agent_url = _validate_agent_url(agent_url)

    name = payload.get("name") or "Remote AI Agent"
    description = payload.get("description") or "Remote agent qualification"
    cases = payload.get("test_cases") or []
    if not cases:
        raise HTTPException(status_code=400, detail="At least one test case is required.")

    workflow = Workflow(
        name=name,
        description=description,
        target_reliability=float(payload.get("target_reliability", 95)),
        maximum_critical_failures=int(payload.get("maximum_critical_failures", 0)),
        maximum_human_review_rate=float(payload.get("maximum_human_review_rate", 20)),
        maximum_average_latency_ms=payload.get("maximum_average_latency_ms"),
        maximum_average_cost_usd=payload.get("maximum_average_cost_usd"),
        test_cases=[],
    )

    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for index, case in enumerate(cases, 1):
            if not isinstance(case, dict):
                raise HTTPException(status_code=400, detail=f"Test case {index} must be an object.")
            case_id = str(case.get("case_id") or f"CASE-{index:03d}")
            started = time.perf_counter()
            try:
                response = await client.post(agent_url, json={"input": case.get("input_data")})
                latency_ms = (time.perf_counter() - started) * 1000
                response.raise_for_status()
                data = response.json()
                actual = data.get("output") if isinstance(data, dict) and "output" in data else data
                cost = float(data.get("cost_usd", 0) or 0) if isinstance(data, dict) else 0.0
                workflow.test_cases.append({
                    "case_id": case_id,
                    "input_data": case.get("input_data"),
                    "expected_output": case.get("expected_output"),
                    "actual_output": actual,
                    "success": actual == case.get("expected_output"),
                    "latency_ms": latency_ms,
                    "maximum_latency_ms": case.get("maximum_latency_ms"),
                    "tool_error": False,
                    "critical": bool(case.get("critical", False)),
                    "human_review_required": bool(case.get("human_review_required", False)),
                    "estimated_cost_usd": max(cost, 0),
                    "maximum_cost_usd": case.get("maximum_cost_usd"),
                })
            except Exception as exc:
                latency_ms = (time.perf_counter() - started) * 1000
                workflow.test_cases.append({
                    "case_id": case_id,
                    "input_data": case.get("input_data"),
                    "expected_output": case.get("expected_output"),
                    "actual_output": None,
                    "success": False,
                    "latency_ms": latency_ms,
                    "maximum_latency_ms": case.get("maximum_latency_ms"),
                    "tool_error": True,
                    "critical": bool(case.get("critical", False)),
                    "human_review_required": bool(case.get("human_review_required", False)),
                    "estimated_cost_usd": 0,
                    "maximum_cost_usd": case.get("maximum_cost_usd"),
                    "error_message": str(exc),
                    "failure_category": "TOOL_ERROR",
                })

    return qualify_workflow(workflow)

@app.post("/api/qualify/json")
async def qualify_json(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=400,
            detail="Upload a .json file.",
        )

    raw = await file.read()

    try:
        data = json.loads(raw.decode("utf-8"))
        workflow = Workflow.model_validate(data)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON workflow: {exc}",
        )

    return qualify_workflow(workflow)


@app.post("/api/qualify/csv")
async def qualify_csv(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Upload a .csv file.",
        )

    raw = await file.read()

    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        cases = []

        for row in reader:
            cases.append(
                {
                    "case_id": row.get("case_id", ""),
                    "expected_output": row.get("expected_output", ""),
                    "actual_output": row.get("actual_output", ""),
                    "success": (
                        row.get("success", "false").strip().lower()
                        == "true"
                    ),
                    "latency_ms": float(row.get("latency_ms", 0) or 0),
                    "tool_error": (
                        row.get("tool_error", "false").strip().lower()
                        == "true"
                    ),
                    "critical": (
                        row.get("critical", "false").strip().lower()
                        == "true"
                    ),
                    "human_review_required": (
                        row.get(
                            "human_review_required",
                            "false",
                        ).strip().lower()
                        == "true"
                    ),
                    "estimated_cost_usd": float(
                        row.get("estimated_cost_usd", 0) or 0
                    ),
                }
            )

        workflow = Workflow(
            name=os.path.splitext(file.filename)[0],
            description="Imported CSV workflow",
            test_cases=cases,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid CSV: {exc}",
        )

    return qualify_workflow(workflow)
