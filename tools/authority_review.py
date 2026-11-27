#!/usr/bin/env python3
"""Run a local, deterministic AI-agent authority review from sanitized JSON.

No network calls are made. Input and output remain on the machine running this tool.
This checks observed traces against a declared authority contract; it does not execute
adversarial tests or certify a system as safe.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from app.production_assurance import ProductionAssurance, ProductionAssuranceStore

MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_TRACES = 5000


def load_payload(path: Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError(f"Input exceeds {MAX_INPUT_BYTES // (1024 * 1024)} MB.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}.") from exc
    if not isinstance(payload, dict):
        raise ValueError("The input root must be a JSON object.")
    if not str(payload.get("asset_id", "")).strip():
        raise ValueError("asset_id is required.")
    contract = payload.get("authority_contract", {})
    traces = payload.get("traces", [])
    policies = payload.get("policies", [])
    changes = payload.get("changes", [])
    if not isinstance(contract, dict):
        raise ValueError("authority_contract must be an object.")
    for name, value in (("traces", traces), ("policies", policies), ("changes", changes)):
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise ValueError(f"{name} must be an array of JSON objects.")
    if len(traces) > MAX_TRACES:
        raise ValueError(f"Maximum supported trace count is {MAX_TRACES}.")
    return payload


def review(payload: dict[str, Any]) -> dict[str, Any]:
    # A temporary SQLite database ensures the CLI does not write customer evidence
    # into a persistent AAI database. It is deleted when the review completes.
    with tempfile.TemporaryDirectory(prefix="aai-authority-review-") as tmp:
        store = ProductionAssuranceStore(str(Path(tmp) / "review.sqlite"))
        engine = ProductionAssurance(store)
        assessment = engine.assess(
            organization_id="local-review",
            asset_id=str(payload["asset_id"]),
            payload=payload,
        )

    planned = assessment.pop("attack_plan", [])
    for item in planned:
        item["execution"] = "NOT_RUN"
        item["note"] = "Coverage candidate only. This CLI does not execute adversarial tests."
    return {
        "report_type": "AAI Agent Authority Review",
        "report_version": "1.0",
        "method": "Deterministic comparison of supplied execution traces against the declared authority contract.",
        "assessment": assessment,
        "attack_coverage_plan": planned,
        "limitations": [
            "Findings are limited to the supplied contract, traces, policies and changes.",
            "A missing finding does not prove that an agent is safe or secure.",
            "The attack coverage plan is not an executed penetration test.",
            "This report is not a certification, legal opinion, compliance attestation or guarantee.",
            "Only sanitized, authorized data should be used. Do not provide credentials, secrets or personal data.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a local AI-agent authority review.")
    parser.add_argument("input", type=Path, help="Path to a sanitized review JSON file.")
    parser.add_argument("-o", "--output", type=Path, help="Write report JSON to this path; stdout if omitted.")
    args = parser.parse_args(argv)
    try:
        payload = load_payload(args.input)
        report = review(payload)
        rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
            print(f"Report written to {args.output}")
        else:
            sys.stdout.write(rendered)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"authority-review: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
