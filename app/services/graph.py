from __future__ import annotations
class DependencyGraph:
    def __init__(self,store): self.store=store
    def direct(self,org_id,asset_id): return self.store.dependencies(org_id,asset_id)
    def snapshot(self,org_id):
        assets=self.store.list_assets(org_id); deps=self.store.all_dependencies(org_id)
        nodes=[{"id":a["id"],"label":a["name"],"type":a["asset_type"],"criticality":a["criticality"]} for a in assets]
        edges=[{"source":d["source_asset_id"],"target":d["target_ref"],"type":d["dependency_type"],"criticality":d["criticality"]} for d in deps]
        return {"nodes":nodes,"edges":edges}
    def impact(self,org_id,asset_id):
        deps=self.store.all_dependencies(org_id); impacted=[]; frontier={asset_id}; seen=set()
        while frontier:
            cur=frontier.pop()
            for d in deps:
                if d["target_ref"]==cur and d["source_asset_id"] not in seen:
                    seen.add(d["source_asset_id"]); impacted.append({"asset_id":d["source_asset_id"],"dependency":d}); frontier.add(d["source_asset_id"])
        return impacted
