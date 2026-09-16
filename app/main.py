from __future__ import annotations
import hashlib, json, secrets, time
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from .config import API_KEY, BOOTSTRAP_KEY, ENGINE_VERSION, ENVIRONMENT, SIGNING_SECRET, OIDC_ISSUER
from .models import AssetCreate, VersionCreate, DependencyCreate, EvidenceCreate, EvaluationCreate, PolicyCreate, DecisionCreate
from .store import Store
from .services.trust import TrustEngine
from .services.policy import PolicyEngine
from .services.graph import DependencyGraph
from .services.evidence import EvidenceService
from .protocol import manifest, signed_passport
from .security.enterprise import Principal, issue_session, verify_oidc_jwt, verify_saml_response
from .observability.metrics import router as metrics_router, count, observe_latency
from .security.scim import router as scim_router
from .enterprise import router as enterprise_router

app=FastAPI(title='AI Assurance Infrastructure',version=ENGINE_VERSION,docs_url='/docs',redoc_url='/redoc')
store=Store(); trust_engine=TrustEngine(store); policy_engine=PolicyEngine(store); graph=DependencyGraph(store); evidence_service=EvidenceService(store)
app.include_router(metrics_router); app.include_router(enterprise_router); app.include_router(scim_router)

@app.middleware('http')
async def request_id(request:Request, call_next):
    rid=request.headers.get('X-Request-ID') or secrets.token_hex(12); started=time.perf_counter()
    try:
        response=await call_next(request); return response
    finally:
        ms=(time.perf_counter()-started)*1000; observe_latency(ms); count('aai_requests_total');
        try: response.headers['X-Request-ID']=rid
        except Exception: pass


def auth(x_api_key:str|None=Header(default=None), authorization:str|None=Header(default=None)):
    raw=x_api_key
    if not raw and authorization and authorization.lower().startswith('bearer '): raw=authorization[7:].strip()
    if not raw: raise HTTPException(401,'Missing API credential')
    if secrets.compare_digest(raw,API_KEY): return {'organization_id':'org_local','scopes':['control:read','control:write','admin:keys','admin:identity'],'key_id':'env'}
    identity=store.authenticate(raw)
    if not identity: raise HTTPException(401,'Invalid API credential')
    return identity

def require_scope(scope:str):
    def dep(identity=Depends(auth)):
        if scope not in identity['scopes']: raise HTTPException(403,'Insufficient scope')
        return identity
    return dep

def request_hash(body:dict): return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def idem(request:Request,org_id:str,body:dict):
    key=request.headers.get('Idempotency-Key');
    if not key:return None,None,None
    existing=store.idempotent_get(org_id,key); h=request_hash(body)
    if existing:
        if existing['request_hash']!=h:raise HTTPException(409,'Idempotency key was already used with a different request body')
        return existing['response'],None,None
    return None,key,h

def save_idem(org,key,h,response,status):
    if key: store.idempotent_put(org,key,h,response,status)

@app.get('/api/health')
def health():return {'status':'ok','version':ENGINE_VERSION,'environment':ENVIRONMENT,'protocol_version':'1.0'}
@app.get('/api/readiness')
def readiness():
    store.init(); backend='postgresql' if store.url.startswith('postgres') else 'sqlite-wal'; return {'status':'ready','database_backend':backend,'checks':{'database':{'status':'ok','backend':backend},'audit_chain':{'status':'ok','backend':'hash-chained'},'outbox':{'status':'ok','backend':'durable'},'runtime_control':{'status':'ok','backend':'policy-gate'}}}
@app.get('/v1/control/protocol/manifest')
def protocol_manifest():return manifest()

@app.post('/v1/control/organizations/bootstrap',status_code=201)
def bootstrap(body:dict,x_bootstrap_key:str|None=Header(default=None)):
    if not x_bootstrap_key or not secrets.compare_digest(x_bootstrap_key,BOOTSTRAP_KEY):raise HTTPException(401,'Invalid bootstrap credential')
    name=str(body.get('name','')).strip()
    if not name:raise HTTPException(422,'Organization name is required')
    org=store.create_organization(name,body.get('metadata') or {}); cred=store.create_api_key(org['id']); return {'organization':org,'credential':cred}

@app.get('/v1/control/organization')
def organization(identity=Depends(require_scope('control:read'))):return store.organization(identity['organization_id'])
@app.get('/v1/control/assets')
def assets(identity=Depends(require_scope('control:read'))):return {'assets':store.list_assets(identity['organization_id'])}
@app.post('/v1/control/assets',status_code=201)
def create_asset(data:AssetCreate,request:Request,identity=Depends(require_scope('control:write'))):
    org=identity['organization_id']; body=data.model_dump(); old,key,h=idem(request,org,body)
    if old is not None:return old
    out=store.create_asset(org,data,request.headers.get('X-Request-ID')); save_idem(org,key,h,out,201); return out
@app.get('/v1/control/assets/{asset_id}')
def get_asset(asset_id:str,identity=Depends(require_scope('control:read'))):
    item=store.get_asset(identity['organization_id'],asset_id)
    if not item:raise HTTPException(404,'Asset not found')
    return item
@app.post('/v1/control/assets/{asset_id}/versions',status_code=201)
def create_version(asset_id:str,data:VersionCreate,request:Request,identity=Depends(require_scope('control:write'))):
    org=identity['organization_id'];
    if not store.get_asset(org,asset_id):raise HTTPException(404,'Asset not found')
    return store.create_version(org,asset_id,data,request.headers.get('X-Request-ID'))
@app.get('/v1/control/assets/{asset_id}/versions')
def versions(asset_id:str,identity=Depends(require_scope('control:read'))):return {'versions':store.versions(identity['organization_id'],asset_id)}
@app.post('/v1/control/dependencies',status_code=201)
def dependency(data:DependencyCreate,request:Request,identity=Depends(require_scope('control:write'))):
    org=identity['organization_id'];
    if not store.get_asset(org,data.source_asset_id):raise HTTPException(404,'Source asset not found')
    return store.add_dependency(org,data,request.headers.get('X-Request-ID'))
@app.get('/v1/control/assets/{asset_id}/dependencies')
def dependencies(asset_id:str,identity=Depends(require_scope('control:read'))):return {'dependencies':graph.direct(identity['organization_id'],asset_id)}
@app.get('/v1/control/graph')
def graph_snapshot(identity=Depends(require_scope('control:read'))):return graph.snapshot(identity['organization_id'])
@app.get('/v1/control/assets/{asset_id}/impact')
def impact(asset_id:str,identity=Depends(require_scope('control:read'))):return {'asset_id':asset_id,'impacted_assets':graph.impact(identity['organization_id'],asset_id)}
@app.post('/v1/control/evidence',status_code=201)
def evidence(data:EvidenceCreate,request:Request,identity=Depends(require_scope('control:write'))):
    org=identity['organization_id'];
    if not store.get_asset(org,data.asset_id):raise HTTPException(404,'Asset not found')
    return store.add_evidence(org,data,request.headers.get('X-Request-ID'))
@app.get('/v1/control/assets/{asset_id}/evidence')
def asset_evidence(asset_id:str,identity=Depends(require_scope('control:read'))):return {'evidence':store.evidence(identity['organization_id'],asset_id)}
@app.get('/v1/control/evidence/{evidence_id}/verify')
def verify_evidence(evidence_id:str,identity=Depends(require_scope('control:read'))):
    item=store.get_evidence(identity['organization_id'],evidence_id)
    if not item:raise HTTPException(404,'Evidence not found')
    return evidence_service.verify(item)
@app.post('/v1/control/evaluations',status_code=201)
def evaluation(data:EvaluationCreate,request:Request,identity=Depends(require_scope('control:write'))):
    org=identity['organization_id'];
    if not store.get_asset(org,data.asset_id):raise HTTPException(404,'Asset not found')
    result=store.add_evaluation(org,data,request.headers.get('X-Request-ID')); result['trust_state']=trust_engine.compute(org,data.asset_id,request.headers.get('X-Request-ID')); return result
@app.get('/v1/control/assets/{asset_id}/evaluations')
def evaluations(asset_id:str,identity=Depends(require_scope('control:read'))):return {'evaluations':store.evaluations(identity['organization_id'],asset_id)}
@app.post('/v1/control/assets/{asset_id}/trust/recompute')
def recompute_trust(asset_id:str,request:Request,identity=Depends(require_scope('control:write'))):
    try:return trust_engine.compute(identity['organization_id'],asset_id,request.headers.get('X-Request-ID'))
    except KeyError:raise HTTPException(404,'Asset not found')
@app.get('/v1/control/assets/{asset_id}/trust')
def trust(asset_id:str,identity=Depends(require_scope('control:read'))):
    value=store.latest_trust(identity['organization_id'],asset_id)
    if not value:raise HTTPException(404,'Trust state not computed')
    return value
@app.post('/v1/control/policies',status_code=201)
def create_policy(data:PolicyCreate,request:Request,identity=Depends(require_scope('control:write'))):return store.create_policy(identity['organization_id'],data,request.headers.get('X-Request-ID'))
@app.get('/v1/control/policies')
def policies(identity=Depends(require_scope('control:read'))):return {'policies':store.policies(identity['organization_id'])}
@app.post('/v1/control/decisions')
def decision(data:DecisionCreate,request:Request,identity=Depends(require_scope('control:write'))):return policy_engine.decide(identity['organization_id'],data.asset_id,data.action,data.context,request.headers.get('X-Request-ID'))

@app.post('/v1/runtime/authorize')
def runtime_authorize(data:DecisionCreate,request:Request,identity=Depends(require_scope('control:write'))):
    started=time.perf_counter(); result=policy_engine.decide(identity['organization_id'],data.asset_id,data.action,data.context,request.headers.get('X-Request-ID')); latency=(time.perf_counter()-started)*1000
    stored=store.record_runtime_decision(identity['organization_id'],data.asset_id,data.action,result['decision'],latency,data.context,request.headers.get('X-Request-ID')); trust=result.get('trust_state') or {}
    allowed=result['decision']=='ALLOW'; count('aai_runtime_decisions_total'); count('aai_runtime_denied_total' if not allowed else 'aai_runtime_allowed_total')
    return {'allowed':allowed,'decision':result['decision'],'reasons':result['reasons'],'trust_state':trust,'runtime_record':stored}
@app.post('/v1/control/deployment-controls')
def deployment_control(body:dict,identity=Depends(require_scope('control:write'))):
    org=identity['organization_id']; aid=str(body.get('asset_id','')); env=str(body.get('environment','production')); state=str(body.get('desired_state','ASSURED')); enforcement=str(body.get('enforcement','deny'))
    if not store.get_asset(org,aid):raise HTTPException(404,'Asset not found')
    if state not in {'ASSURED','DEGRADED','BLOCKED'} or enforcement not in {'deny','review','allow'}:raise HTTPException(422,'Invalid deployment control')
    return store.upsert_deployment_control(org,aid,env,state,enforcement)
@app.get('/v1/control/assets/{asset_id}/deployment-control')
def get_deployment_control(asset_id:str,environment:str='production',identity=Depends(require_scope('control:read'))):return store.deployment_control(identity['organization_id'],asset_id,environment) or {'asset_id':asset_id,'environment':environment,'desired_state':'ASSURED','enforcement':'deny'}

@app.get('/v1/control/audit')
def audit(limit:int=100,identity=Depends(require_scope('control:read'))):return {'events':store.audit_events(identity['organization_id'],max(1,min(limit,500)))}
@app.get('/v1/control/audit/verify')
def audit_verify(identity=Depends(require_scope('control:read'))):return store.verify_audit_chain(identity['organization_id'])
@app.get('/v1/control/outbox')
def outbox(limit:int=100,identity=Depends(require_scope('control:read'))):return {'events':store.pending_outbox(identity['organization_id'],max(1,min(limit,500)))}
@app.get('/v1/control/runtime/decisions')
def runtime_decisions(limit:int=100,identity=Depends(require_scope('control:read'))):return {'decisions':store.runtime_decisions(identity['organization_id'],max(1,min(limit,500)))}
@app.get('/v1/control/assets/{asset_id}/passport')
def passport(asset_id:str,identity=Depends(require_scope('control:read'))):
    org=identity['organization_id']; asset=store.get_asset(org,asset_id)
    if not asset:raise HTTPException(404,'Asset not found')
    return signed_passport(asset,store.versions(org,asset_id),store.dependencies(org,asset_id),store.evidence(org,asset_id),store.latest_trust(org,asset_id))
@app.post('/v1/control/credentials',status_code=201)
def credentials(body:dict,identity=Depends(require_scope('admin:keys'))):
    scopes=body.get('scopes') or ['control:read']; allowed={'control:read','control:write','admin:keys','admin:identity'}
    if any(x not in allowed for x in scopes):raise HTTPException(422,'Unsupported scope')
    return store.create_api_key(identity['organization_id'],scopes)
@app.get('/v1/control/credentials')
def credentials_list(identity=Depends(require_scope('admin:keys'))):return {'credentials':store.api_keys(identity['organization_id'])}
@app.delete('/v1/control/credentials/{key_id}')
def credential_revoke(key_id:str,identity=Depends(require_scope('admin:keys'))):return store.revoke_api_key(identity['organization_id'],key_id)
@app.get('/v1/control/directory/users')
def directory_users(identity=Depends(require_scope('admin:identity'))):return {'users':store.directory_users(identity['organization_id'])}

@app.get('/v1/sso/config')
def sso_config(identity=Depends(require_scope('admin:identity'))):return {'oidc_issuer':OIDC_ISSUER,'oidc_configured':bool(OIDC_ISSUER),'scim_configured':bool(__import__('os').getenv('AAI_SCIM_TOKEN')),'saml_supported_via_enterprise_idp':True}
@app.post('/v1/sso/oidc/verify')
async def oidc_verify(body:dict,identity=Depends(require_scope('admin:identity'))):
    if not OIDC_ISSUER or not __import__('os').getenv('AAI_OIDC_AUDIENCE'): raise HTTPException(503,'OIDC is not configured')
    try: return {'claims':await verify_oidc_jwt(str(body.get('id_token','')),OIDC_ISSUER,__import__('os').getenv('AAI_OIDC_AUDIENCE'))}
    except Exception as e: raise HTTPException(401,f'OIDC verification failed: {e}')

@app.post('/v1/sso/saml/verify')
async def saml_verify(body:dict,identity=Depends(require_scope('admin:identity'))):
    settings=body.get('settings') or {}
    try: return {'assertion':await verify_saml_response(str(body.get('saml_response','')),body.get('request_data') or {},settings)}
    except Exception as e: raise HTTPException(401,f'SAML verification failed: {e}')

@app.post('/v1/sso/session')
def sso_session(body:dict,identity=Depends(require_scope('admin:identity'))):
    principal=Principal(str(body.get('subject','')),identity['organization_id'],tuple(body.get('scopes') or ['control:read']),tuple(body.get('roles') or ['viewer']))
    if not principal.subject:raise HTTPException(422,'subject is required')
    return {'access_token':issue_session(principal,SIGNING_SECRET,int(body.get('ttl_seconds',3600))),'token_type':'bearer'}
@app.get('/v1/slo')
def slo(identity=Depends(require_scope('control:read'))):return store.slo_report(identity['organization_id'])

app.mount('/static',StaticFiles(directory='static'),name='static')
@app.get('/',response_class=HTMLResponse)
def root():
    with open('static/console.html',encoding='utf-8') as f:return f.read()
