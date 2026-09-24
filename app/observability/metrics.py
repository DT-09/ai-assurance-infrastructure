from __future__ import annotations
import time
from collections import defaultdict
from fastapi import APIRouter, Response

router=APIRouter()
_counts=defaultdict(int); _latencies=[]; _started=time.time()

def count(name:str, value:int=1): _counts[name]+=value

def observe_latency(ms:float):
    _latencies.append(ms)
    if len(_latencies)>5000: del _latencies[:1000]

@router.get('/metrics')
def metrics():
    lines=['# TYPE aai_uptime_seconds gauge',f'aai_uptime_seconds {time.time()-_started:.3f}']
    for k,v in sorted(_counts.items()): lines += [f'# TYPE {k} counter',f'{k} {v}']
    if _latencies:
        lines += [f'# TYPE aai_request_latency_ms gauge',f'aai_request_latency_ms {sum(_latencies)/len(_latencies):.3f}']
    return Response('\n'.join(lines)+'\n', media_type='text/plain; version=0.0.4')
