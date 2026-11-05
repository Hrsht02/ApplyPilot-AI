import base64,hashlib
from cryptography.fernet import Fernet
from app.config import settings
def cipher():
    secret=settings.credential_encryption_key
    if not secret: raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY must be configured")
    key=secret.encode() if len(secret)==44 else base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)
def encrypt_secret(value:str)->str: return cipher().encrypt(value.encode()).decode()
def decrypt_secret(value:str)->str: return cipher().decrypt(value.encode()).decode()
