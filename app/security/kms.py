from __future__ import annotations
import base64, hashlib, hmac, os
from abc import ABC, abstractmethod

class KMS(ABC):
    @abstractmethod
    def sign(self, data: bytes, key_id: str) -> bytes: ...
    @abstractmethod
    def verify(self, data: bytes, signature: bytes, key_id: str) -> bool: ...

class HMACKMS(KMS):
    """Development-compatible KMS interface. Production must use managed KMS/HSM."""
    def __init__(self, secret: str): self.secret = secret.encode()
    def sign(self, data: bytes, key_id: str) -> bytes:
        return hmac.new(self.secret + key_id.encode(), data, hashlib.sha256).digest()
    def verify(self, data: bytes, signature: bytes, key_id: str) -> bool:
        return hmac.compare_digest(self.sign(data, key_id), signature)

class AWSKMS(KMS):
    def __init__(self, client=None):
        import boto3
        self.client = client or boto3.client('kms')
    def sign(self, data: bytes, key_id: str) -> bytes:
        digest = hashlib.sha256(data).digest()
        r = self.client.sign(KeyId=key_id, Message=digest, MessageType='DIGEST', SigningAlgorithm='RSASSA_PKCS1_V1_5_SHA_256')
        return r['Signature']
    def verify(self, data: bytes, signature: bytes, key_id: str) -> bool:
        digest = hashlib.sha256(data).digest()
        try:
            self.client.verify(KeyId=key_id, Message=digest, MessageType='DIGEST', Signature=signature, SigningAlgorithm='RSASSA_PKCS1_V1_5_SHA_256')
            return True
        except Exception: return False

def build_kms():
    provider = os.getenv('AAI_KMS_PROVIDER', 'hmac').lower()
    if provider == 'aws': return AWSKMS()
    return HMACKMS(os.getenv('AAI_SIGNING_SECRET', 'development-signing-secret-change-me'))
