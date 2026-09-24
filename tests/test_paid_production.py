import os
import tempfile

from fastapi.testclient import TestClient


def test_paid_production_core(monkeypatch):
    db=tempfile.mktemp(suffix='.db')
    prod=tempfile.mktemp(suffix='.db')
    monkeypatch.setenv('AAI_PRODUCTION_DB',prod)
    monkeypatch.setenv('AAI_DEV_BYPASS_PAID','true')
    from app.main import app, production_store, production_assurance
    # module singleton may have been initialized before env change; endpoint still uses its store.
    c=TestClient(app)
    auth={'Authorization':'Bearer aai_ent_test'}
    r=c.post('/v1/production/authority-contracts',json={
        'agent_id':'support-agent','version':'1','allowed_actions':['refund'],
        'allowed_tools':['payments'],'allowed_data_classes':['customer_basic'],
        'approval_required_for':['refund'],'least_privilege':True,'adversarial_testing':True,
        'change_reassessment':True
    },headers=auth)
    assert r.status_code==200
    r=c.post('/v1/production/traces',json={'traces':[{'trace_id':'t1','action':'delete_customer','tool':'crm','data_classes':['pii']} ]},headers=auth)
    assert r.status_code==200 and r.json()['accepted']==1
    r=c.post('/v1/production/assess',json={'asset_id':'asset-1','authority_contract':{
        'agent_id':'support-agent','version':'1','allowed_actions':['refund'],'allowed_tools':['payments'],
        'allowed_data_classes':['customer_basic'],'approval_required_for':['refund'],
        'least_privilege':True,'adversarial_testing':True,'change_reassessment':True
    },'traces':[{'trace_id':'t1','action':'delete_customer','tool':'crm','data_classes':['pii']}]},headers=auth)
    assert r.status_code==200
    data=r.json(); assert data['decision']=='DENY'; assert data['critical_findings']>=1; assert data['authority_graph']['nodes']
    os.remove(db) if os.path.exists(db) else None
    os.remove(prod) if os.path.exists(prod) else None


def test_entitlement_signature(monkeypatch):
    monkeypatch.setenv('AAI_DEV_BYPASS_PAID','false')
    from app.paid_access import issue_entitlement, verify_entitlement
    token=issue_entitlement('org1','growth','x@example.com',60)
    assert verify_entitlement(token)['sub']=='org1'
    assert verify_entitlement(token+'x') is None
