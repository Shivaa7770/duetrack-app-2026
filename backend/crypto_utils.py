import base64
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple
import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import jwt

JWT_SECRET = os.environ.get("JWT_SECRET", "duetrack-secret-key-32-chars-long-development")
JWT_ALGORITHM = "HS256"
AUTH_COOKIE_NAME = "token"
COOKIE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7 days

def get_encryption_key() -> bytes:
    key_hex = os.environ.get("PASSWORD_ENCRYPTION_KEY")
    if not key_hex:
        key_hex = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    key = bytes.fromhex(key_hex)
    if len(key) != 32:
        raise ValueError("PASSWORD_ENCRYPTION_KEY must be a 32-byte key encoded as 64 hex characters")
    return key

def hash_password(plaintext: str) -> str:
    salt = bcrypt.gensalt(10)
    return bcrypt.hashpw(plaintext.encode("utf-8"), salt).decode("utf-8")

def compare_password(candidate: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(candidate.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def encrypt_password(plaintext: str) -> str:
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    iv = os.urandom(12)
    # AESGCM.encrypt in cryptography appends the 16-byte authentication tag to the ciphertext
    data = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    ciphertext = data[:-16]
    auth_tag = data[-16:]
    return f"{base64.b64encode(iv).decode('utf-8')}:{base64.b64encode(auth_tag).decode('utf-8')}:{base64.b64encode(ciphertext).decode('utf-8')}"

def decrypt_password(payload: str) -> str:
    parts = payload.split(":")
    if len(parts) != 3:
        raise ValueError("Malformed encrypted payload")
    iv = base64.b64decode(parts[0])
    auth_tag = base64.b64decode(parts[1])
    ciphertext = base64.b64decode(parts[2])
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    # Reconstruct data = ciphertext + auth_tag
    data = ciphertext + auth_tag
    plaintext = aesgcm.decrypt(iv, data, None)
    return plaintext.decode("utf-8")

def sign_token(sub: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(seconds=COOKIE_MAX_AGE_SECONDS)
    payload = {
        "sub": sub,
        "role": role,
        "exp": exp,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

def compute_status(total_amount: float, received_amount: float) -> str:
    if received_amount <= 0:
        return "PENDING"
    if received_amount >= total_amount:
        return "COMPLETED"
    return "PARTIALLY_COLLECTED"
