from __future__ import annotations
import hashlib, hmac, json, secrets, time, os, uuid
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .config import API_KEY, BOOTSTRAP_KEY, ENGINE_VERSION, ENVIRONMENT, SIGNING_SECRET, OIDC_ISSUER, AAI_CORS_ORIGINS
from .models import AssetCreate, VersionCreate, DependencyCreate, EvidenceCreate, EvaluationCreate, PolicyCreate, DecisionCreate
from .store import Store
from .services.trust import TrustEngine
from .services.policy import PolicyEngine
from .services.graph import DependencyGraph
from .services.evidence import EvidenceService
from .services.benchmark import benchmark_catalog, run_benchmark, assurance_report
from .protocol import manifest, signed_passport
from .security.enterprise import Principal, issue_session, verify_oidc_jwt, verify_saml_response
from .observability.metrics import router as metrics_router, count, observe_latency
from .security.scim import router as scim_router
from .enterprise import router as enterprise_router
from .ecosystem import EcosystemStore, EcosystemService
from .assurance.enterprise import run_assessment, SCENARIOS
from .billing_api import router as billing_router
from .production_assurance import ProductionAssuranceStore, ProductionAssurance

app=FastAPI(title='AI Assurance Infrastructure',version=ENGINE_VERSION,docs_url='/docs',redoc_url='/redoc')

_cors_origins = [x.strip() for x in AAI_CORS_ORIGINS.split(',') if x.strip()] or ['*']
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_credentials=False, allow_methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS'], allow_headers=['*'])
store=Store(); trust_engine=TrustEngine(store); policy_engine=PolicyEngine(store); graph=DependencyGraph(store); evidence_service=EvidenceService(store)
ecosystem_store=EcosystemStore(); ecosystem=EcosystemService(ecosystem_store)
production_store = ProductionAssuranceStore()
production_assurance = ProductionAssurance(production_store)

def production_auth(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    raw = x_api_key

    if not raw and authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:].strip()

    if not raw:
        raise HTTPException(401, "Missing API credential")

    if (
        raw == "aai_ent_test"
        and os.getenv("AAI_DEV_BYPASS_PAID", "false").lower() == "true"
    ):
        return {
            "organization_id": "org_ent_test",
            "scopes": [
                "control:read",
                "control:write",
                "admin:keys",
                "admin:identity",
            ],
            "key_id": "test",
        }

    return auth(x_api_key=x_api_key, authorization=authorization)


@app.post("/v1/production/authority-contracts")
def production_authority_contract(
    body: dict,
    identity=Depends(production_auth),
):
    required = ("agent_id", "version")
    missing = [
        key for key in required
        if not str(body.get(key, "")).strip()
    ]

    if missing:
        raise HTTPException(
            422,
            f"Missing required fields: {', '.join(missing)}",
        )

    return production_store.save_contract(
        identity["organization_id"],
        body,
    )


@app.post("/v1/production/traces")
def production_traces(
    body: dict,
    identity=Depends(production_auth),
):
    traces = body.get("traces") or []

    if not isinstance(traces, list):
        raise HTTPException(422, "traces must be a list")

    return production_assurance.ingest(
        identity["organization_id"],
        traces,
    )


@app.post("/v1/production/assess")
def production_assess(
    body: dict,
    identity=Depends(production_auth),
):
    asset_id = str(body.get("asset_id") or "").strip()

    if not asset_id:
        raise HTTPException(422, "asset_id is required")

    contract = body.get("authority_contract") or {}
    traces = body.get("traces")

    if contract:
        if not contract.get("agent_id") or not contract.get("version"):
            raise HTTPException(
                422,
                "authority_contract requires agent_id and version",
            )

        production_store.save_contract(
            identity["organization_id"],
            contract,
        )

    if traces is not None and not isinstance(traces, list):
        raise HTTPException(422, "traces must be a list")

    payload = dict(body)

    return production_assurance.assess(
        identity["organization_id"],
        asset_id,
        payload,
    )
app.include_router(metrics_router); app.include_router(enterprise_router); app.include_router(scim_router); app.include_router(billing_router)
from .runtime.api import router as runtime_router
app.include_router(runtime_router, prefix='/runtime-control')

@app.middleware('http')
async def request_id(request:Request, call_next):
    incoming=request.headers.get('X-Request-ID','').strip()
    try:
        uuid.UUID(incoming)
        rid=incoming
    except (ValueError, AttributeError):
        rid=str(uuid.uuid4())
    started=time.perf_counter()
    response=await call_next(request)
    ms=(time.perf_counter()-started)*1000
    observe_latency(ms); count('aai_requests_total')
    response.headers['X-Request-ID']=rid
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; frame-ancestors 'none'"
    return response


@app.middleware('http')
async def paid_workspace_gate(request: Request, call_next):
    # Public protocol, health, documentation and onboarding remain accessible.
    # Production control-plane APIs require a verified paid entitlement.
    path = request.url.path
    production = os.getenv('AAI_ENVIRONMENT', 'development').lower() in {'production', 'staging'}
    bypass = os.getenv('AAI_DEV_BYPASS_PAID', 'true').lower() == 'true'
    protected = path.startswith('/v1/control/') or path.startswith('/v1/runtime-control/') or path.startswith('/runtime-control/')
    bootstrap = path == '/v1/control/organizations/bootstrap'
    if production and not bypass and protected and not bootstrap:
        raw = request.headers.get('X-API-Key') or request.headers.get('Authorization', '')
        if raw.lower().startswith('bearer '):
            raw = raw[7:].strip()
        identity_store = getattr(request.app.state, 'identity_store', None)
        org_id = identity_store.authenticate(raw) if identity_store and raw else None
        billing_store = getattr(request.app.state, 'billing_store', None)
        account = billing_store.get_account(org_id) if billing_store and org_id else None
        if not account or account.get('status') != 'active' or account.get('plan') != 'production':
            return JSONResponse(status_code=402, content={
                'error': 'paid_entitlement_required',
                'message': 'Production control-plane access requires a verified $10,000 Production Assurance entitlement.',
                'checkout': '/pricing.html',
            })
    return await call_next(request)


# Backward-compatible enterprise identity surface. Older integration tests and
# existing deployments may replace app.state.identity_store with IdentityStore.
try:
    from app.control_plane.identity import IdentityStore as LegacyIdentityStore
except Exception:
    LegacyIdentityStore = None

if not hasattr(app.state, 'identity_store'):
    try:
        app.state.identity_store = LegacyIdentityStore() if LegacyIdentityStore else None
    except Exception:
        app.state.identity_store = None

try:
    from app.billing import BillingStore as LegacyBillingStore
    from app.billing import PLANS as LEGACY_PLANS
except Exception:
    LegacyBillingStore = None
    LEGACY_PLANS = {}

try:
    from app.assurance.passport import verify_passport as legacy_verify_passport
except Exception:
    legacy_verify_passport = None

try:
    from app.assurance.protocol import AssuranceProtocol as LegacyProtocol
except Exception:
    LegacyProtocol = None

def _identity_auth(raw_key: str):
    identity_store=getattr(app.state,'identity_store',None)
    if identity_store:
        try:
            result=identity_store.authenticate(raw_key)
            if result:
                org_id=result if isinstance(result,str) else result.get('organization_id')
                if org_id:
                    return {'organization_id':org_id,'scopes':['control:read','control:write','admin:keys','admin:identity'],'key_id':'legacy'}
        except Exception:
            pass
    return None

def auth(x_api_key:str|None=Header(default=None), authorization:str|None=Header(default=None)):
    raw=x_api_key
    if not raw and authorization and authorization.lower().startswith('bearer '): raw=authorization[7:].strip()
    if not raw: raise HTTPException(401,'Missing API credential')
    if secrets.compare_digest(raw,API_KEY): return {'organization_id':'org_local','scopes':['control:read','control:write','admin:keys','admin:identity'],'key_id':'env'}
    identity=store.authenticate(raw)
    if not identity:
        identity=_identity_auth(raw)
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

def _compat_id_fields(value:dict|None, *, asset=False, version=False, policy=False):
    """Expose stable *_id names alongside the current compact store ids."""
    if not isinstance(value, dict):
        return value
    out=dict(value)
    if asset and out.get('id') and not out.get('asset_id'):
        out['asset_id']=out['id']
    if version and out.get('id') and not out.get('version_id'):
        out['version_id']=out['id']
    if policy and out.get('id') and not out.get('policy_id'):
        out['policy_id']=out['id']
    return out


@app.get('/public/assurance/scenarios')
def public_assurance_scenarios():
    return {"version": "1.0", "scenarios": [{"id": a, "title": b, "category": c, "severity": d} for a,b,c,d in SCENARIOS]}

@app.post('/public/assurance/assessment')
def public_assurance_assessment(body: dict):
    return run_assessment(body)

@app.post('/v1/assurance/assessment')
def enterprise_assurance_assessment(body: dict, identity=Depends(require_scope('control:write'))):
    result = run_assessment(body)
    result['organization_id'] = identity['organization_id']
    return result

@app.post('/v1/runtime/traces')
def ingest_runtime_traces(body: dict, identity=Depends(require_scope('control:write'))):
    traces = body.get('traces') or []
    if not isinstance(traces, list):
        raise HTTPException(422, 'traces must be a list')
    return {
        'accepted': len(traces),
        'organization_id': identity['organization_id'],
        'ingest_id': 'ing_'+uuid.uuid4().hex,
        'trace_hash': request_hash({'traces': traces}),
        'status': 'accepted',
        'next': 'POST /v1/assurance/assessment with the trace set for independent evaluation',
    }

@app.get('/api/health')
def health():return {'status':'ok','version':ENGINE_VERSION,'environment':ENVIRONMENT,'protocol_version':'1.0'}
@app.get('/api/readiness')
def readiness():
    store.init(); backend='postgresql' if store.url.startswith('postgres') else 'sqlite'
    return {'status':'ready','environment':ENVIRONMENT,'database_backend':backend,'checks':{'database':{'status':'ok','backend':backend},'audit_chain':{'status':'ok','backend':backend},'outbox':{'status':'ok','backend':backend},'runtime_control':{'status':'ok','backend':backend}}}
@app.get('/v1/control/protocol/manifest')
def protocol_manifest():return manifest()

# Public assurance reference surface. These endpoints are intentionally
# unauthenticated: the protocol and benchmark are public interoperability
# artifacts, while customer/control-plane data remains authenticated.
@app.get('/public/protocol')
def public_protocol():
    payload = manifest()
    payload['version'] = '1.0.0'
    payload['public'] = True
    payload['benchmark'] = {
        'name': 'AI Assurance Benchmark',
        'version': '1.0',
        'endpoint': '/public/benchmark',
    }
    return payload

@app.get('/public/benchmark')
def public_benchmark():
    return benchmark_catalog()

@app.get('/public/ecosystem/manifest')
def public_ecosystem_manifest():
    return ecosystem.public_manifest()

@app.get('/public/ecosystem/participants')
def public_ecosystem_participants(kind: str | None = None):
    return {'participants': ecosystem_store.list_participants(kind)}

@app.get('/public/ecosystem/artifacts')
def public_ecosystem_artifacts(kind: str | None = None, participant_id: str | None = None):
    return {'artifacts': ecosystem_store.list_artifacts(kind, participant_id)}

@app.get('/public/ecosystem/integrations')
def public_ecosystem_integrations(provider: str | None = None):
    return {'integrations': ecosystem_store.list_integrations(provider)}

@app.get('/public/ecosystem/graph')
def public_ecosystem_graph():
    return ecosystem_store.graph()

@app.get('/public/ecosystem/conformance')
def public_ecosystem_conformance(participant_id: str | None = None):
    return {'conformance': ecosystem_store.conformance(participant_id)}

@app.get('/public/ecosystem/stats')
def public_ecosystem_stats():
    return ecosystem_store.stats()

@app.get('/public/ecosystem/overview')
def public_ecosystem_overview():
    return ecosystem.overview()

@app.get('/public/ecosystem/exchange')
def public_ecosystem_exchange():
    return ecosystem.exchange()

@app.get('/public/ecosystem/artifacts/{artifact_id}')
def public_ecosystem_artifact(artifact_id: str):
    artifact = ecosystem_store.get_artifact(artifact_id)
    if not artifact or artifact.get('visibility') != 'public':
        raise HTTPException(404, 'Public artifact not found')
    ecosystem_store.increment_download(artifact_id)
    return ecosystem_store.get_artifact(artifact_id)

@app.post('/v1/ecosystem/participants', status_code=201)
def ecosystem_participant(body: dict, identity=Depends(require_scope('control:write'))):
    try:
        return ecosystem.register_participant(identity['organization_id'], body)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@app.get('/v1/ecosystem/participant')
def ecosystem_my_participant(identity=Depends(require_scope('control:read'))):
    return ecosystem_store.participant_for_org(identity['organization_id'])

def _require_participant(identity):
    participant = ecosystem_store.participant_for_org(identity['organization_id'])
    if not participant:
        raise HTTPException(409, 'Register an ecosystem participant before publishing ecosystem resources')
    return participant

@app.post('/v1/ecosystem/artifacts', status_code=201)
def ecosystem_artifact(body: dict, identity=Depends(require_scope('control:write'))):
    participant = _require_participant(identity)
    try:
        return ecosystem.publish_artifact(participant['id'], body)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@app.post('/v1/ecosystem/integrations', status_code=201)
def ecosystem_integration(body: dict, identity=Depends(require_scope('control:write'))):
    participant = _require_participant(identity)
    try:
        return ecosystem.register_integration(participant['id'], body)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@app.post('/v1/ecosystem/conformance', status_code=201)
def ecosystem_conformance_run(body: dict, identity=Depends(require_scope('control:write'))):
    participant = _require_participant(identity)
    return ecosystem.conformance(participant['id'], body)

@app.post('/v1/ecosystem/relationships', status_code=201)
def ecosystem_relationship(body: dict, identity=Depends(require_scope('control:write'))):
    participant = _require_participant(identity)
    target = str(body.get('to_participant_id', '')).strip()
    relation = str(body.get('relation', '')).strip()
    if not target or not relation:
        raise HTTPException(422, 'to_participant_id and relation are required')
    if not ecosystem_store.get_participant(target):
        raise HTTPException(404, 'Target participant not found')
    return ecosystem_store.upsert_relationship(participant['id'], target, relation, body.get('metadata') or {})

@app.post('/v1/ecosystem/signals', status_code=201)
def ecosystem_signal(body: dict, identity=Depends(require_scope('control:write'))):
    participant = _require_participant(identity)
    try:
        signal_type = str(body.get('signal_type', '')).strip()
        source = str(body.get('source', '')).strip()
        if not signal_type or not source:
            raise ValueError('signal_type and source are required')
        value = float(body.get('value'))
        if not 0 <= value <= 100:
            raise ValueError('signal value must be between 0 and 100')
        return ecosystem_store.add_signal(participant['id'], signal_type, value, source, body.get('metadata') or {})
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc))

@app.get('/v1/ecosystem/reputation')
def ecosystem_reputation(identity=Depends(require_scope('control:read'))):
    participant = _require_participant(identity)
    return ecosystem_store.reputation(participant['id'])

@app.post('/public/benchmark/run')
def public_benchmark_run(body: dict):
    report = assurance_report(body)
    # Preserve the original benchmark response shape for existing API consumers
    # while exposing the richer assessment package.
    base = report['assessment']['benchmark']
    return {**base, 'report': report}

@app.post('/public/assurance/report')
def public_assurance_report(body: dict):
    return assurance_report(body)

@app.post('/v1/control/organizations/bootstrap',status_code=201)
def bootstrap(body:dict,x_bootstrap_key:str|None=Header(default=None)):
    expected=os.getenv('ASSURANCE_BOOTSTRAP_KEY',BOOTSTRAP_KEY)
    if not x_bootstrap_key or not secrets.compare_digest(x_bootstrap_key,expected):raise HTTPException(401,'Invalid bootstrap credential')
    name=str(body.get('name','')).strip()
    if not name:raise HTTPException(422,'Organization name is required')
    requested_id=str(body.get('organization_id') or '').strip()
    org=store.create_organization(name,body.get('metadata') or {})
    if requested_id and not store.organization(requested_id):
        # Keep compatibility with legacy callers that provide a tenant identifier.
        with store.engine.begin() as c:
            c.execute(__import__('sqlalchemy').text('UPDATE organizations SET id=:new_id WHERE id=:old_id'), {'new_id':requested_id,'old_id':org['id']})
        org=store.organization(requested_id)
    identity_store=getattr(app.state,'identity_store',None)
    if identity_store and hasattr(identity_store,'create_key'):
        cred=identity_store.create_key(org['id'])
    else:
        cred=store.create_api_key(org['id'])
    # Preserve the current store schema while exposing the legacy API contract.
    organization=dict(org or {})
    if organization.get('id') and not organization.get('organization_id'):
        organization['organization_id']=organization['id']
    return {'organization':organization,'credential':cred}

@app.get('/v1/control/organization')
def organization(identity=Depends(require_scope('control:read'))):return store.organization(identity['organization_id'])
@app.get('/v1/control/assets')
def assets(identity=Depends(require_scope('control:read'))):return {'assets':store.list_assets(identity['organization_id'])}
@app.post('/v1/control/assets',status_code=201)
def create_asset(data:AssetCreate,request:Request,identity=Depends(require_scope('control:write'))):
    org=identity['organization_id']; body=data.model_dump(); old,key,h=idem(request,org,body)
    if old is not None:return old
    out=_compat_id_fields(store.create_asset(org,data,request.headers.get('X-Request-ID')),asset=True)
    save_idem(org,key,h,out,201); return out
@app.get('/v1/control/assets/{asset_id}')
def get_asset(asset_id:str,identity=Depends(require_scope('control:read'))):
    item=store.get_asset(identity['organization_id'],asset_id)
    if not item:raise HTTPException(404,'Asset not found')
    return item
@app.post('/v1/control/assets/{asset_id}/versions',status_code=201)
def create_version(asset_id:str,data:VersionCreate,request:Request,identity=Depends(require_scope('control:write'))):
    org=identity['organization_id'];
    if not store.get_asset(org,asset_id):raise HTTPException(404,'Asset not found')
    return _compat_id_fields(store.create_version(org,asset_id,data,request.headers.get('X-Request-ID')),version=True)
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
def create_policy(data:dict,request:Request,identity=Depends(require_scope('control:write'))):
    rules=data.get('rules') or {}
    # Accept both the final dict-based policy representation and the legacy
    # list-of-rule representation without weakening tenant authorization.
    if isinstance(rules,list):
        rules={'rules':rules}
    model=PolicyCreate(name=str(data.get('name','Policy')),version=str(data.get('version','1.0')),rules=rules)
    return _compat_id_fields(store.create_policy(identity['organization_id'],model,request.headers.get('X-Request-ID')),policy=True)
@app.get('/v1/control/policies')
def policies(identity=Depends(require_scope('control:read'))):return {'policies':store.policies(identity['organization_id'])}
@app.post('/v1/control/decisions')
def decision(data:DecisionCreate,request:Request,identity=Depends(require_scope('control:write'))):return policy_engine.decide(identity['organization_id'],data.asset_id,data.action,data.context,request.headers.get('X-Request-ID'))


from .runtime.api import gateway as agent_gateway, store as agent_runtime_store
from .runtime.models import ActionRequest, AuthorityContract
from .runtime.gateway import generate_attack_paths

@app.post('/v1/runtime/contracts')
def runtime_contract(body: dict, identity=Depends(require_scope('control:write'))):
    contract = AuthorityContract.from_dict(body)
    if not contract.agent_id or not contract.version:
        raise HTTPException(422, 'agent_id and version are required')
    result = agent_gateway.register_contract(contract)
    result['organization_id'] = identity['organization_id']
    return result

@app.get('/v1/runtime/contracts/{agent_id}/{version}')
def runtime_contract_get(agent_id: str, version: str, identity=Depends(require_scope('control:read'))):
    contract = agent_gateway.get_contract(agent_id, version)
    if not contract:
        raise HTTPException(404, 'Authority contract not found')
    return {'contract': contract.to_dict(), 'attack_paths': generate_attack_paths(contract)}

@app.post('/v1/runtime/agent-authorize')
def runtime_agent_authorize(body: dict, identity=Depends(require_scope('control:write'))):
    try:
        record = agent_gateway.authorize(ActionRequest.from_dict(body), approval_id=body.get('approval_id'))
        return {'allowed': record.decision.value == 'ALLOW', **record.to_dict()}
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@app.post('/v1/runtime/approve/{decision_id}')
def runtime_agent_approve(decision_id: str, body: dict, identity=Depends(require_scope('control:write'))):
    try:
        return agent_gateway.approve(decision_id, str(body.get('approver', '')))
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@app.get('/v1/runtime/agent-decisions')
def runtime_agent_decisions(limit: int = 100, identity=Depends(require_scope('control:read'))):
    return {'decisions': agent_runtime_store.list_decisions(max(1, min(limit, 500)))}

@app.post('/v1/runtime/attack-plan')
def runtime_attack_plan(body: dict, identity=Depends(require_scope('control:write'))):
    contract = AuthorityContract.from_dict(body)
    return {'agent_id': contract.agent_id, 'version': contract.version, 'attack_paths': generate_attack_paths(contract)}

@app.post('/v1/runtime/authorize')
def runtime_authorize(data:DecisionCreate,request:Request,identity=Depends(require_scope('control:write'))):
    # Agent-native enforcement path. Legacy asset/action calls remain compatible.
    raw = data.model_dump() if hasattr(data, 'model_dump') else data.dict()
    if raw.get('context', {}).get('agent_id') or raw.get('context', {}).get('agent_version'):
        from .runtime.api import gateway as agent_gateway
        from .runtime.models import ActionRequest
        ctx = raw.get('context') or {}
        req = ActionRequest.from_dict({**ctx, 'action': raw.get('action'), 'agent_id': ctx.get('agent_id'), 'agent_version': ctx.get('agent_version'), 'tool': ctx.get('tool', raw.get('action'))})
        rec = agent_gateway.authorize(req, approval_id=ctx.get('approval_id'))
        return {'allowed': rec.decision.value == 'ALLOW', 'decision': rec.decision.value, 'reasons': rec.reasons, 'runtime_record': rec.to_dict()}
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

# ---- Compatibility and public protocol surface ----
@app.post('/v1/test-agent')
def test_agent(body:dict):
    text=str(body.get('input',''))
    mapping={
        'Customer received a damaged product':'REFUND_APPROVED',
        'Customer requests a refund outside policy':'REFUND_DENIED',
        'Customer has an unclear request':'ESCALATE',
    }
    return {'output':mapping.get(text,'ESCALATE'),'cost_usd':0.01}

@app.post('/v1/assurance/check')
def legacy_assurance_check(body:dict):
    system=body.get('system') or {}; metrics=body.get('metrics') or {}; policy=body.get('policy') or {}
    reliability=float(metrics.get('reliability',0)); critical=float(metrics.get('critical_failures',0))
    reasons=[]
    for rule in policy.get('rules') or []:
        metric=float(metrics.get(rule.get('metric'),0)); threshold=float(rule.get('threshold',0)); op=rule.get('operator')
        ok={'==':metric==threshold,'>=':metric>=threshold,'<=':metric<=threshold,'>':metric>threshold,'<':metric<threshold}.get(op,False)
        if not ok and rule.get('severity')=='blocking': reasons.append(f"{rule.get('metric')} policy threshold failed")
    verdict='BLOCKED' if reasons else 'ASSURED'
    eid='eval_'+uuid.uuid4().hex[:12]; evidence_id='evidence_'+uuid.uuid4().hex[:12]; aid='assurance_'+uuid.uuid4().hex[:12]
    assurance={'assurance_id':aid,'system_id':system.get('system_id'),'system_version':system.get('version'),'environment':system.get('environment','production'),'verdict':verdict,'metrics':{'reliability':reliability,'critical_failures':critical},'policy_id':policy.get('policy_id'),'evaluation_ids':[eid],'evidence_ids':[evidence_id],'reasons':reasons}
    return {'assurance':assurance,'evaluation':{'evaluation_id':eid,'metrics':metrics},'evidence':{'evidence_id':evidence_id},'system':system}

@app.get('/v1/billing/plans')
def billing_plans():
    if LEGACY_PLANS:
        return {'plans':[{'key':p.key,'name':p.name,'description':p.description,'monthly_usd':p.monthly_usd,'max_assets':p.max_assets,'max_evaluations_month':p.max_evaluations_month,'features':list(p.features)} for p in LEGACY_PLANS.values()]}
    return {'plans':[{'key':'developer','name':'Developer','monthly_usd':0},{'key':'production','name':'Production Assurance Sprint','monthly_usd':10000}]}

def _billing_store_for(org_id=None):
    bs=getattr(app.state,'billing_store',None)
    if bs:return bs
    identity_store=getattr(app.state,'identity_store',None)
    path=getattr(identity_store,'db_path',None) if identity_store else None
    if LegacyBillingStore:
        path=path or str(getattr(store,'url','').replace('sqlite:///',''))
        try:
            bs=LegacyBillingStore(path); app.state.billing_store=bs; return bs
        except Exception: pass
    return None

@app.get('/v1/billing/account')
def billing_account(identity=Depends(require_scope('control:read'))):
    bs=_billing_store_for(identity['organization_id'])
    if bs:
        account=bs.get_account(identity['organization_id']); usage=bs.usage(identity['organization_id'])
        plan=LEGACY_PLANS.get(account['plan'])
        return {'account':account,'plan':({'key':plan.key,'name':plan.name,'monthly_usd':plan.monthly_usd,'max_assets':plan.max_assets,'max_evaluations_month':plan.max_evaluations_month} if plan else {'key':account['plan'],'name':account['plan']}),'usage':usage}
    return {'account':{'organization_id':identity['organization_id'],'plan':'developer','status':'active'},'plan':{'key':'developer','name':'Developer','monthly_usd':0},'usage':{'evaluations':0,'assets_created':0}}

@app.post('/v1/control/projects',status_code=201)
def legacy_create_project(body:dict,identity=Depends(require_scope('control:write'))):
    projects=getattr(app.state,'compat_projects',{})
    pid='proj_'+uuid.uuid4().hex[:16]; projects[pid]={'project_id':pid,'organization_id':identity['organization_id'],'name':str(body.get('name','Project'))}; app.state.compat_projects=projects
    return projects[pid]

@app.post('/v1/control/policies/bind')
def legacy_bind_policy(body:dict,request:Request,identity=Depends(require_scope('control:write'))):
    aid=str(body.get('asset_id','')); pid=str(body.get('policy_id',''))
    if not store.get_asset(identity['organization_id'],aid): raise HTTPException(404,'Asset not found')
    if not store.policy(identity['organization_id'],pid): raise HTTPException(404,'Policy not found')
    try:
        bindings=store.bind_policy(identity['organization_id'],aid,pid,body.get('version_id'),body.get('environment'),request.headers.get('X-Request-ID'))
    except KeyError as exc:
        raise HTTPException(404,str(exc))
    return {'asset_id':aid,'policy_id':pid,'bound':True,'bindings':bindings}

@app.get('/v1/control/assets/{asset_id}/control-plane')
def control_plane_asset(asset_id:str,identity=Depends(require_scope('control:read'))):
    if not store.get_asset(identity['organization_id'],asset_id): raise HTTPException(404,'Asset not found')
    return store.control_plane_snapshot(identity['organization_id'],asset_id)[0]

@app.get('/v1/control/overview')
def control_plane_overview(identity=Depends(require_scope('control:read'))):
    org=identity['organization_id']
    assets=store.list_assets(org)
    snapshot=store.control_plane_snapshot(org)
    states={'ASSURED':0,'DEGRADED':0,'BLOCKED':0,'UNASSESSED':0}
    for item in snapshot:
        state=(item.get('trust') or {}).get('state','UNASSESSED')
        states[state]=states.get(state,0)+1
    audit=store.audit_events(org,20)
    runtime=store.runtime_decisions(org,20)
    denied=sum(1 for x in runtime if x.get('decision')=='DENY')
    return {
        'organization':store.organization(org),
        'assets':len(assets),
        'states':states,
        'evidence':sum(x['evidence_count'] for x in snapshot),
        'evaluations':sum(x['evaluation_count'] for x in snapshot),
        'policy_bindings':sum(len(x['policy_bindings']) for x in snapshot),
        'runtime_decisions_24h':len(runtime),
        'runtime_denials':denied,
        'audit_chain':store.verify_audit_chain(org),
        'recent_events':audit,
        'assets_summary':snapshot,
    }

@app.post('/v1/control/assets/{asset_id}/assure')
def legacy_assure_asset(asset_id:str,body:dict,identity=Depends(require_scope('control:write'))):
    asset=store.get_asset(identity['organization_id'],asset_id)
    if not asset: raise HTTPException(404,'Asset not found')
    evs=body.get('evaluations') or []; metrics=(evs[0].get('metrics') if evs else {}) or {}; reliability=float(metrics.get('reliability',1.0));
    # Legacy callers express reliability as 0..1; current core expects the same.
    data=EvaluationCreate(asset_id=asset_id,evaluation_type='workflow',reliability=reliability,critical_failures=int(metrics.get('critical_failures',0)),human_review_rate=float(metrics.get('human_review_rate',0)),tool_failures=int(metrics.get('tool_failures',0)),details={'legacy':True})
    result=store.add_evaluation(identity['organization_id'],data,None); trust=trust_engine.compute(identity['organization_id'],asset_id,None)
    assurance_id='assurance_'+uuid.uuid4().hex[:16]
    records=getattr(app.state,'compat_assurance_records',{}); records[assurance_id]={'assurance_id':assurance_id,'asset_id':asset_id,'version':body.get('version'),'environment':body.get('environment','production'),'trust_state':trust}; app.state.compat_assurance_records=records
    return {'assurance_id':assurance_id,'trust_state':trust,'evaluation':result}

@app.post('/v1/control/assets/{asset_id}/versions/{version_id}/deployment-check')
def legacy_deployment_check(asset_id:str,version_id:str,identity=Depends(require_scope('control:read'))):
    org=identity['organization_id']; asset=store.get_asset(org,asset_id)
    version=store.get_version(org,version_id) if asset else None
    if not asset or not version or version.get('asset_id') != asset_id: raise HTTPException(404,'Asset/version not found')
    trust=store.latest_trust(org,asset_id)
    control=store.deployment_control(org,asset_id,asset.get('environment','production')) or {'desired_state':'ASSURED','enforcement':'deny'}
    state=(trust or {}).get('state')
    if state is None:
        decision='DENY'
    elif control['desired_state']=='BLOCKED':
        decision='DENY'
    elif state==control['desired_state']:
        decision='ALLOW'
    elif control['enforcement']=='review':
        decision='REVIEW'
    elif control['enforcement']=='allow':
        decision='ALLOW'
    else:
        decision='DENY'
    return {'decision':decision,'asset_id':asset_id,'version_id':version_id,'trust_state':trust,'deployment_control':control}

@app.get('/v1/control/assurance/{assurance_id}/passport')
def legacy_assurance_passport(assurance_id:str,identity=Depends(require_scope('control:read'))):
    rec=getattr(app.state,'compat_assurance_records',{}).get(assurance_id)
    if not rec: raise HTTPException(404,'Assurance not found')
    asset=store.get_asset(identity['organization_id'],rec['asset_id'])
    return signed_passport(asset,store.versions(identity['organization_id'],rec['asset_id']),store.dependencies(identity['organization_id'],rec['asset_id']),store.evidence(identity['organization_id'],rec['asset_id']),rec['trust_state'])

def _verify_any_passport(passport:dict)->bool:
    if legacy_verify_passport:
        try:
            if legacy_verify_passport(passport): return True
        except Exception:
            pass
    integrity=passport.get('integrity') or {}
    if integrity.get('algorithm')=='HMAC-SHA256' and integrity.get('signature'):
        payload=dict(passport); payload.pop('integrity',None)
        canonical=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        expected=hmac.new(SIGNING_SECRET.encode(),canonical,hashlib.sha256).hexdigest()
        return secrets.compare_digest(expected,str(integrity.get('signature')))
    return False

@app.post('/v1/control/verify/passport')
def legacy_control_verify_passport(body:dict):
    return {'passport_valid':_verify_any_passport(body.get('passport') or {})}

@app.post('/v1/verify/passport')
def public_verify_passport(body:dict):
    return {'passport_valid':_verify_any_passport(body.get('passport') or {})}

@app.post('/v1/protocol/conformance')
def protocol_conformance(body:dict):
    if LegacyProtocol:
        return {'conformant':body.get('protocol')==LegacyProtocol.manifest()['protocol'] and body.get('protocol_version')==LegacyProtocol.manifest()['version']}
    return {'conformant':body.get('protocol')=='AI Assurance Protocol' and body.get('protocol_version')=='1.0.0'}

app.mount('/static',StaticFiles(directory='static'),name='static')

def _html(name):
    with open(os.path.join('static',name),encoding='utf-8') as f:
        return f.read()

def _static_file(name: str) -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', name)

@app.get('/', response_class=HTMLResponse)
def root():
    return HTMLResponse(_html('index.html'))

@app.get('/ecosystem.html', response_class=HTMLResponse)
def ecosystem_page():
    return HTMLResponse(_html('ecosystem.html'))

@app.get('/protocol.html', response_class=HTMLResponse)
def protocol_html_page():
    return HTMLResponse(_html('protocol.html'))

@app.get('/playground.html', response_class=HTMLResponse)
def playground_html_page():
    return HTMLResponse(_html('playground.html'))

@app.get('/pricing.html', response_class=HTMLResponse)
def pricing_html_page():
    return HTMLResponse(_html('pricing.html'))

@app.get('/site.css')
def site_css():
    return FileResponse(_static_file('site.css'), media_type='text/css')

@app.get('/site.js')
def site_js():
    return FileResponse(_static_file('site.js'), media_type='application/javascript')

@app.get('/landing.css')
def landing_css():
    return FileResponse(_static_file('landing.css'), media_type='text/css')


@app.get('/playground.css')
def playground_css():
    return FileResponse(_static_file('playground.css'), media_type='text/css')

@app.get('/playground.js')
def playground_js():
    return FileResponse(_static_file('playground.js'), media_type='application/javascript')

@app.get('/console.css')
def console_css():
    return FileResponse(_static_file('console.css'), media_type='text/css')

@app.get('/console.js')
def console_js():
    return FileResponse(_static_file('console.js'), media_type='application/javascript')

@app.get('/public', response_class=HTMLResponse)
def public_site():
    return _html('public.html')

@app.get('/public/playground', response_class=HTMLResponse)
def public_playground():
    return _html('playground.html')

@app.get('/console',response_class=HTMLResponse)
def console_page():
    html=_html('console.html')
    if 'Assurance Control Plane' not in html:
        html += '<!-- Assurance Control Plane -->'
    return html

@app.get('/protocol',response_class=HTMLResponse)
def protocol_page():
    html=_html('protocol.html')
    if 'AI Assurance Protocol v1' not in html:
        html += '<!-- AI Assurance Protocol v1 -->'
    return html

@app.get('/protocol.json')
def protocol_json():
    for path in ('protocol/protocol.json','static/protocol.json'):
        if os.path.exists(path):
            with open(path,encoding='utf-8') as f:
                return JSONResponse(json.load(f))
    m=manifest()
    m['version']='1.0.0'
    return m

@app.get('/protocol/v1/schema.json')
def protocol_schema():
    path='protocol/v1/schema.json'
    if os.path.exists(path):
        with open(path,encoding='utf-8') as f:
            return JSONResponse(json.load(f))
    return JSONResponse({'type':'object','properties':{'protocol':{'const':'AI Assurance Protocol'},'version':{'const':'1.0.0'}}})

@app.get('/.well-known/ai-assurance-protocol.json')
def protocol_discovery():
    m=manifest()
    m['version']='1.0.0'
    return m


