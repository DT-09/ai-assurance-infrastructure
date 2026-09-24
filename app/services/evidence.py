from __future__ import annotations
import hashlib, json
class EvidenceService:
    def __init__(self,store): self.store=store
    def verify(self,evidence):
        body={"asset_id":evidence["asset_id"],"version_id":evidence["version_id"],"evidence_type":evidence["evidence_type"],"source":evidence["source"],"result":evidence["result"],"payload":evidence["payload"],"occurred_at":evidence["occurred_at"],"previous_hash":evidence["previous_hash"]}
        expected=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        return {"evidence_id":evidence["id"],"valid":expected==evidence["provenance_hash"],"expected_hash":expected,"stored_hash":evidence["provenance_hash"]}
