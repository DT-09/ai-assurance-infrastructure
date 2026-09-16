from fastapi.testclient import TestClient
from app.main import app, API_KEY

c=TestClient(app)
H={'X-API-Key':API_KEY}

def test_runtime_control_and_deployment():
    a=c.post('/v1/control/assets',json={'name':'enterprise-agent','asset_type':'agent'},headers=H).json()
    aid=a['id']
    c.post('/v1/control/evaluations',json={'asset_id':aid,'reliability':1.0,'critical_failures':0,'human_review_rate':0,'tool_failures':0},headers=H)
    d=c.post('/v1/runtime/authorize',json={'asset_id':aid,'action':'execute','context':{}},headers=H)
    assert d.status_code==200 and d.json()['decision']=='ALLOW' and d.json()['allowed'] is True
    ctl=c.post('/v1/control/deployment-controls',json={'asset_id':aid,'environment':'production','desired_state':'ASSURED','enforcement':'deny'},headers=H)
    assert ctl.status_code==200 and ctl.json()['desired_state']=='ASSURED'

def test_credential_lifecycle():
    r=c.post('/v1/control/credentials',json={'scopes':['control:read']},headers=H)
    assert r.status_code==201
    kid=r.json()['id']; assert c.get('/v1/control/credentials',headers=H).status_code==200
    assert c.delete('/v1/control/credentials/'+kid,headers=H).json()['revoked'] is True

def test_enterprise_catalog_and_slo():
    assert 'openai' in c.get('/v1/enterprise/integrations').json()['providers']
    assert c.get('/v1/slo',headers=H).status_code==200
