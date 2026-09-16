from __future__ import annotations
import base64, hashlib, hmac, json
from .config import PROTOCOL_VERSION, SIGNING_SECRET

def manifest():
    return {"protocol":"AI Assurance Protocol","version":PROTOCOL_VERSION,"status":"active","purpose":"Vendor-neutral machine-readable assurance state, evidence and control signals.","resources":["organization","asset","version","dependency","evidence","evaluation","trust_state","policy","decision","trust_passport"],"states":["ASSURED","DEGRADED","BLOCKED"],"decisions":["ALLOW","REVIEW","DENY"],"provenance":{"algorithm":"SHA-256","chain":True},"passport":{"signature":"HMAC-SHA256","canonicalization":"RFC-8785-compatible deterministic JSON ordering"}}

def signed_passport(asset,versions,dependencies,evidence,trust):
    payload={"passport_version":"1.0","protocol":"AI Assurance Protocol","asset":asset,"versions":versions,"dependencies":dependencies,"evidence":evidence,"trust_state":trust}
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    sig=hmac.new(SIGNING_SECRET.encode(),canonical,hashlib.sha256).hexdigest()
    return {**payload,"integrity":{"algorithm":"HMAC-SHA256","signature":sig}}
