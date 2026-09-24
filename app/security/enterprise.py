from __future__ import annotations
import base64, hashlib, hmac, json, secrets, time
from dataclasses import dataclass
from typing import Any

try:
    import jwt
except Exception:
    jwt = None

@dataclass(frozen=True)
class Principal:
    subject: str
    organization_id: str
    scopes: tuple[str, ...]
    roles: tuple[str, ...] = ()


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def secure_token(nbytes: int = 32) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(nbytes)).decode().rstrip('=')


def sign_hs256(payload: dict[str, Any], secret: str) -> str:
    if jwt:
        return jwt.encode(payload, secret, algorithm='HS256')
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(raw).decode() + '.' + sig


def verify_hs256(token: str, secret: str) -> dict[str, Any]:
    if jwt:
        return jwt.decode(token, secret, algorithms=['HS256'])
    encoded, sig = token.split('.', 1)
    raw = base64.urlsafe_b64decode(encoded + '===')
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected): raise ValueError('Invalid token')
    return json.loads(raw)


def issue_session(principal: Principal, secret: str, ttl_seconds: int = 3600) -> str:
    now = int(time.time())
    return sign_hs256({'sub': principal.subject, 'org': principal.organization_id,
                       'scopes': list(principal.scopes), 'roles': list(principal.roles),
                       'iat': now, 'exp': now + ttl_seconds}, secret)


def oidc_claims(token: str, secret: str | None = None) -> dict[str, Any]:
    if not secret: raise ValueError('OIDC verification key is not configured')
    return verify_hs256(token, secret)

async def verify_oidc_jwt(token: str, issuer: str, audience: str):
    if not jwt: raise RuntimeError('PyJWT is required for OIDC verification')
    import httpx
    cfg_url=issuer.rstrip('/')+'/.well-known/openid-configuration'
    async with httpx.AsyncClient(timeout=10) as c:
        cfg=(await c.get(cfg_url)).raise_for_status()
        discovery=cfg.json(); jwks=discovery['jwks_uri']
    signing_key=jwt.PyJWKClient(jwks).get_signing_key_from_jwt(token)
    return jwt.decode(token, signing_key.key, algorithms=['RS256','RS384','RS512','ES256','ES384','ES512'], audience=audience, issuer=issuer)

async def verify_saml_response(saml_response: str, request_data: dict[str, str], settings: dict):
    """Optional SAML 2.0 assertion verification through python3-saml."""
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
    except ImportError as exc:
        raise RuntimeError('python3-saml is required for SAML 2.0 support') from exc
    authn=OneLogin_Saml2_Auth(request_data, old_settings=settings)
    authn.process_response(saml_response)
    if authn.get_errors(): raise ValueError('; '.join(authn.get_errors()))
    return {'name_id':authn.get_nameid(),'attributes':authn.get_attributes()}
