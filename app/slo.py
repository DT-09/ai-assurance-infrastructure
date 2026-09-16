from __future__ import annotations
import time
from dataclasses import dataclass

@dataclass(frozen=True)
class SLO:
    name:str; target:float; window_seconds:int

class SLOMonitor:
    def __init__(self): self.samples=[]
    def record(self, success:bool, latency_ms:float): self.samples.append((time.time(),success,latency_ms)); self.samples=self.samples[-10000:]
    def report(self):
        if not self.samples: return {'availability':1.0,'latency_p95_ms':0.0,'sample_count':0}
        ok=sum(1 for _,s,_ in self.samples if s); lat=sorted(x[2] for x in self.samples); p95=lat[min(len(lat)-1,int(len(lat)*.95))]
        return {'availability':ok/len(self.samples),'latency_p95_ms':p95,'sample_count':len(self.samples)}
