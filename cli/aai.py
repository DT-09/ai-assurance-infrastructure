from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

from app.assurance.passport import verify_passport
from app.assurance.protocol import AssuranceProtocol
from protocol.v1.conformance import conformance_report


def _load_json(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON document must be an object")
    return data


def _dump(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))


def cmd_protocol(_: argparse.Namespace) -> int:
    _dump(AssuranceProtocol.manifest())
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    passport = _load_json(args.passport)
    local_valid = verify_passport(passport)
    result: dict[str, Any] = {"local_integrity": local_valid}
    if args.server:
        response = httpx.post(
            args.server.rstrip("/") + "/v1/verify/passport",
            json={"passport": passport, "evidence": []},
            timeout=args.timeout,
        )
        response.raise_for_status()
        result["server"] = response.json()
        valid = bool(result["server"].get("valid"))
    else:
        valid = local_valid
    _dump(result)
    return 0 if valid else 1


def cmd_conformance(args: argparse.Namespace) -> int:
    report = conformance_report(_load_json(args.document))
    _dump(report)
    return 0 if report["conformant"] else 1


def cmd_fetch_passport(args: argparse.Namespace) -> int:
    if not args.api_key:
        raise ValueError("--api-key is required")
    response = httpx.get(
        args.server.rstrip("/") + f"/v1/control/assurance/{args.assurance_id}/passport",
        headers={"X-API-Key": args.api_key},
        timeout=args.timeout,
    )
    response.raise_for_status()
    passport = response.json()
    if args.output:
        Path(args.output).write_text(json.dumps(passport, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _dump(passport)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aai", description="AI Assurance Protocol CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    protocol = sub.add_parser("protocol", help="Print Protocol v1 manifest")
    protocol.set_defaults(func=cmd_protocol)

    verify = sub.add_parser("verify", help="Verify a Trust Passport")
    verify.add_argument("passport")
    verify.add_argument("--server", help="AI Assurance server base URL")
    verify.add_argument("--timeout", type=float, default=30.0)
    verify.set_defaults(func=cmd_verify)

    conform = sub.add_parser("conformance", help="Check a Protocol v1 document")
    conform.add_argument("document")
    conform.set_defaults(func=cmd_conformance)

    fetch = sub.add_parser("fetch-passport", help="Fetch a passport from the control plane")
    fetch.add_argument("assurance_id")
    fetch.add_argument("--server", required=True)
    fetch.add_argument("--api-key", required=True)
    fetch.add_argument("--output")
    fetch.add_argument("--timeout", type=float, default=30.0)
    fetch.set_defaults(func=cmd_fetch_passport)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        return int(args.func(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"aai: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
