from __future__ import annotations
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
DATA_DIR=Path(os.getenv('AAI_DATA_DIR',ROOT/'data')); DATA_DIR.mkdir(parents=True,exist_ok=True)
DB_PATH=Path(os.getenv('AAI_DB_PATH',DATA_DIR/'assurance.db'))
DATABASE_URL=os.getenv('AAI_DATABASE_URL',f'sqlite:///{DB_PATH.as_posix()}')
ENVIRONMENT=os.getenv('AAI_ENVIRONMENT','development')
API_KEY=os.getenv('AAI_API_KEY','aai_local_development_key')
BOOTSTRAP_KEY=os.getenv('AAI_BOOTSTRAP_KEY','local-bootstrap-key')
SIGNING_SECRET=os.getenv('AAI_SIGNING_SECRET','development-signing-secret-change-me')
OIDC_ISSUER=os.getenv('AAI_OIDC_ISSUER',''); OIDC_AUDIENCE=os.getenv('AAI_OIDC_AUDIENCE','')
SCIM_TOKEN=os.getenv('AAI_SCIM_TOKEN',''); KMS_PROVIDER=os.getenv('AAI_KMS_PROVIDER','hmac')
PROTOCOL_VERSION='1.0'; ENGINE_VERSION='10.0.0'
REQUIRED_SLO_AVAILABILITY=float(os.getenv('AAI_SLO_AVAILABILITY','0.999'))
REQUIRED_SLO_P95_MS=float(os.getenv('AAI_SLO_P95_MS','500'))
if ENVIRONMENT.lower() in {'production','staging'}:
    for name,val in [('AAI_API_KEY',API_KEY),('AAI_BOOTSTRAP_KEY',BOOTSTRAP_KEY),('AAI_SIGNING_SECRET',SIGNING_SECRET)]:
        if val.startswith(('aai_local','local-bootstrap','development-signing')): raise RuntimeError(f'{name} must be explicitly configured outside development.')
    if DATABASE_URL.startswith('sqlite'): raise RuntimeError('Production/staging requires PostgreSQL via AAI_DATABASE_URL.')
    if KMS_PROVIDER=='hmac': raise RuntimeError('Production/staging requires an external KMS/HSM provider via AAI_KMS_PROVIDER.')
