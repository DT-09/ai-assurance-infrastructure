from fastapi.testclient import TestClient
from app.main import app, API_KEY

c=TestClient(app); H={'X-API-Key':API_KEY}


def test_agent_runtime_boundary_end_to_end():
    contract={
      'agent_id':'api-agent','version':'1.0.0','allowed_actions':['refund'],
      'allowed_tools':['payments'],'allowed_data_classes':['customer_basic'],
      'approval_required_for':['refund'],'max_transaction_usd':5000,
      'allowed_destinations':['internal']
    }
    r=c.post('/v1/runtime/contracts',json=contract,headers=H); assert r.status_code==200
    action={**{k:contract[k] for k in ['agent_id','version']},'agent_version':'1.0.0','action':'refund','tool':'payments','amount_usd':100,'target':'c1','data_classes':['customer_basic'],'destination':'internal'}
    r=c.post('/v1/runtime/agent-authorize',json=action,headers=H); assert r.status_code==200 and r.json()['decision']=='REQUIRE_APPROVAL'
    did=r.json()['decision_id']
    assert c.post(f'/v1/runtime/approve/{did}',json={'approver':'finance'},headers=H).status_code==200
    action['approval_id']=did
    r=c.post('/v1/runtime/agent-authorize',json=action,headers=H); assert r.status_code==200 and r.json()['decision']=='ALLOW' and r.json()['allowed'] is True


def test_runtime_blocks_undeclared_action():
    action={'agent_id':'api-agent','agent_version':'1.0.0','action':'delete_customer','tool':'payments','amount_usd':1}
    r=c.post('/v1/runtime/agent-authorize',json=action,headers=H); assert r.status_code==200 and r.json()['decision']=='BLOCK'
