from __future__ import annotations
import os, secrets
from fastapi import APIRouter, Header, HTTPException, Request
from ..store import Store

router=APIRouter(prefix='/scim/v2',tags=['scim'])
store=Store()

def auth(token: str|None):
    expected=os.getenv('AAI_SCIM_TOKEN','');
    if not expected or not token or not secrets.compare_digest(token.replace('Bearer ','').strip(),expected): raise HTTPException(401,'Invalid SCIM bearer token')
    org=os.getenv('AAI_SCIM_ORGANIZATION_ID','org_local')
    if not store.organization(org): raise HTTPException(500,'SCIM organization is not configured')
    return org

@router.get('/Users')
def users(startIndex:int=1,count:int=100,authorization:str|None=Header(None)):
    org=auth(authorization); vals=store.directory_users(org); vals=[v for v in vals if v.get('active',1)]
    return {'schemas':['urn:ietf:params:scim:api:messages:2.0:ListResponse'],'totalResults':len(vals),'startIndex':startIndex,'itemsPerPage':count,'Resources':vals[startIndex-1:startIndex-1+count]}

@router.post('/Users',status_code=201)
async def create_user(request:Request,authorization:str|None=Header(None)):
    org=auth(authorization); body=await request.json(); uid=body.get('id') or ('scim_'+secrets.token_hex(10)); body['id']=uid; return store.upsert_directory_user(org,uid,body.get('userName',''),body)

@router.patch('/Users/{user_id}')
async def patch_user(user_id:str,request:Request,authorization:str|None=Header(None)):
    org=auth(authorization); current=store.directory_user(org,user_id) or {'id':user_id}; body=await request.json()
    for op in body.get('Operations',[]):
        if op.get('op','').lower()=='replace':
            path=op.get('path'); val=op.get('value');
            if path: current[path]=val
            elif isinstance(val,dict): current.update(val)
    return store.upsert_directory_user(org,user_id,current.get('userName',''),current)

@router.delete('/Users/{user_id}',status_code=204)
def delete_user(user_id:str,authorization:str|None=Header(None)):
    org=auth(authorization); store.delete_directory_user(org,user_id)
