import os, tempfile
from app.store import Store
from app.models import AssetCreate, PolicyCreate
from app.services.policy import PolicyEngine

def make():
    fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd); os.unlink(path)
    s=Store(path); o=s.create_organization('Final Test'); a=s.create_asset(o['id'],AssetCreate(name='Agent',environment='production')); return s,o,a,path

def test_policy_binding_is_persistent():
    s,o,a,path=make()
    try:
        p=s.create_policy(o['id'],PolicyCreate(name='Production',rules={'minimum_score':.95}))
        s.bind_policy(o['id'],a['id'],p['id'],environment='production')
        assert s.policy_bindings(o['id'],a['id'])[0]['policy_id']==p['id']
        assert s.effective_policy(o['id'],a['id'],'production')['name']=='Production'
    finally: os.remove(path)

def test_untrusted_asset_cannot_be_runtime_allowed():
    s,o,a,path=make()
    try:
        result=PolicyEngine(s).decide(o['id'],a['id'],'execute',{'environment':'production'})
        assert result['decision']=='DENY'
    finally: os.remove(path)

def test_control_plane_snapshot_is_single_operational_view():
    s,o,a,path=make()
    try:
        snap=s.control_plane_snapshot(o['id'],a['id'])[0]
        assert snap['asset']['id']==a['id']
        assert 'versions' in snap and 'dependencies' in snap
        assert 'trust' in snap and 'policy_bindings' in snap and 'deployment_control' in snap
    finally: os.remove(path)
