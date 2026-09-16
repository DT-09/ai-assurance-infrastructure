from __future__ import annotations
class PolicyEngine:
    def __init__(self,store): self.store=store
    def decide(self,org_id,asset_id,action,context,request_id=None):
        trust=self.store.latest_trust(org_id,asset_id)
        if not trust: decision,reasons="DENY",["No current trust state exists."]
        elif trust["state"]=="BLOCKED": decision,reasons="DENY",["Asset is BLOCKED."]
        elif trust["state"]=="DEGRADED": decision,reasons="REVIEW",["Asset is DEGRADED."]
        else: decision,reasons="ALLOW",["Asset is ASSURED."]
        required=context.get("required_state")
        if required and trust and trust["state"]!=required: decision="DENY"; reasons.append("Requested trust state does not match the current state.")
        min_score=context.get("minimum_score")
        if min_score is not None and (not trust or trust["score"]<float(min_score)): decision="DENY"; reasons.append("Current trust score is below the requested minimum.")
        return self.store.add_decision(org_id,asset_id,action,decision,reasons,context,request_id) | {"trust_state":trust}
