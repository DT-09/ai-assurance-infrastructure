from __future__ import annotations
import os
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from .security.enterprise import Principal, issue_session
from .security.kms import build_kms
from .integrations.adapters import IntegrationRegistry
from .slo import SLOMonitor

router=APIRouter(prefix='/v1/enterprise',tags=['enterprise'])
integrations=IntegrationRegistry(); slo=SLOMonitor(); kms=build_kms()

@router.get('/integrations')
def integration_catalog(): return {'providers':integrations.providers(),'webhook_supported':True}

@router.post('/integrations/{provider}/normalize')
async def normalize(provider:str, request:Request):
    try: body=await request.json(); return integrations.normalize(provider,body).__dict__
    except KeyError: raise HTTPException(404,'Provider not configured')
    except ValueError as e: raise HTTPException(400,str(e))

@router.get('/slo')
def slo_report(): return slo.report()

@router.get('/security/posture')
def security_posture():
    return {'production_requirements':{'external_kms':os.getenv('AAI_KMS_PROVIDER','hmac')!='hmac','oidc':bool(os.getenv('AAI_OIDC_ISSUER')),'scim':bool(os.getenv('AAI_SCIM_TOKEN')),'postgresql':os.getenv('AAI_DATABASE_URL','').startswith('postgres'),'tls_termination':os.getenv('AAI_TLS_TERMINATED','false').lower()=='true'},'kms_provider':os.getenv('AAI_KMS_PROVIDER','hmac')}
