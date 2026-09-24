from __future__ import annotations
import json, os, time
import httpx
from .store import Store

class OutboxWorker:
    def __init__(self, store=None): self.store=store or Store()
    def run_once(self, limit=100):
        sent=0
        # A deployed worker can route these durable events to Kafka/SNS/PubSub/EventBridge/webhooks.
        destination=os.getenv('AAI_EVENT_SINK_URL','')
        for event in self.store.pending_outbox_all(limit):
            if destination:
                with httpx.Client(timeout=10) as c:
                    r=c.post(destination,json=event); r.raise_for_status()
            self.store.mark_outbox_published(event['id']); sent+=1
        return {'published':sent}

def main():
    w=OutboxWorker(); interval=float(os.getenv('AAI_OUTBOX_INTERVAL','2'))
    while True:
        try:w.run_once()
        except Exception as exc: print(f'outbox worker error: {exc}',flush=True)
        time.sleep(interval)

if __name__=='__main__': main()
