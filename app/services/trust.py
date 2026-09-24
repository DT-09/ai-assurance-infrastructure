from __future__ import annotations
from ..models import now_iso

class TrustEngine:
    def __init__(self, store): self.store=store

    def compute(self, org_id: str, asset_id: str, request_id: str | None = None):
        asset=self.store.get_asset(org_id,asset_id)
        if not asset: raise KeyError("asset not found")
        evidence=self.store.evidence(org_id,asset_id)
        evaluations=self.store.evaluations(org_id,asset_id)
        deps=self.store.dependencies(org_id,asset_id)
        latest=evaluations[0] if evaluations else None
        reliability=float(latest["reliability"]) if latest else 0.0
        critical_failures=int(latest["critical_failures"]) if latest else 1
        human_review=float(latest["human_review_rate"]) if latest else 1.0
        failed=sum(1 for e in evidence if e["result"]=="fail")
        review=sum(1 for e in evidence if e["result"]=="review")
        critical_deps=sum(1 for d in deps if d["criticality"]=="critical")
        reasons=[]; score=reliability
        if not evaluations: reasons.append("No assurance evaluation has been recorded."); score=min(score,.20)
        if critical_failures>0: reasons.append(f"{critical_failures} critical evaluation failure(s)."); score=min(score,.49)
        if failed: reasons.append(f"{failed} failing evidence record(s)."); score=min(score,.45)
        if review: reasons.append(f"{review} evidence record(s) require review."); score=min(score,.79)
        if critical_deps: reasons.append(f"{critical_deps} critical dependency relationship(s) require monitoring.")
        if human_review>.20: reasons.append("Human review rate exceeds the default 20% control threshold."); score=min(score,.79)
        if critical_failures>0 or failed: state="BLOCKED"
        elif score<.80 or review or human_review>.20: state="DEGRADED"
        else: state="ASSURED"
        previous=self.store.latest_trust(org_id,asset_id)
        epoch=(previous["epoch"]+1) if previous else 1
        trust={"asset_id":asset_id,"state":state,"score":round(max(0,min(1,score)),4),"evidence_state":"FAILED" if failed else ("REVIEW" if review else ("VERIFIED" if evidence else "MISSING")),"dependency_state":"ATTENTION" if critical_deps else "STABLE","policy_state":"UNKNOWN","reliability":reliability,"critical_failures":critical_failures,"human_review_rate":human_review,"reasons":reasons or ["All current assurance signals satisfy the default control thresholds."],"computed_at":now_iso(),"epoch":epoch}
        return self.store.save_trust(org_id,trust,request_id)
