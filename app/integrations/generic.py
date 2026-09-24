from __future__ import annotations
import hashlib, hmac, json, time
from dataclasses import dataclass
from typing import Any
import httpx

@dataclass
class IntegrationEvent:
    provider: str
    event_type: str
    asset_id: str
    payload: dict[str,Any]

class WebhookIntegration:
    def __init__(self, url:str, secret:str|None=None): self.url=url; self.secret=secret
    def send(self,event:IntegrationEvent):
        body=json.dumps({'provider':event.provider,'event_type':event.event_type,'asset_id':event.asset_id,'payload':event.payload},sort_keys=True,separators=(',',':')).encode()
        headers={'Content-Type':'application/json','X-AAI-Timestamp':str(int(time.time()))}
        if self.secret: headers['X-AAI-Signature']=hmac.new(self.secret.encode(),body,hashlib.sha256).hexdigest()
        with httpx.Client(timeout=10) as c: r=c.post(self.url,content=body,headers=headers); r.raise_for_status(); return {'status_code':r.status_code}

SUPPORTED_PROVIDERS=('openai','anthropic','aws-bedrock','google-vertex-ai','azure-openai','langchain','llamaindex','generic-webhook')
