from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    # bcrypt 会把超过 72 bytes 的密码截断；V1 做长度限制（schemas 已限制 72 chars）
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(*, subject: str, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "iss": settings.jwt_issuer,
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_access_token_minutes)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer)
    except JWTError as e:
        raise ValueError("invalid_token") from e
    return payload


def _get_fernet() -> Fernet:
    if not settings.api_secret_enc_key:
        raise RuntimeError("API_SECRET_ENC_KEY is required for OpenAPI api_secret storage")
    raw = settings.api_secret_enc_key.encode("utf-8")
    try:
        return Fernet(raw)
    except Exception:
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
        return Fernet(derived)


def generate_api_key() -> str:
    return "fvk_" + secrets.token_urlsafe(24)


def generate_api_secret() -> str:
    return "fvs_" + secrets.token_urlsafe(40)


def encrypt_api_secret(secret: str) -> str:
    f = _get_fernet()
    return f.encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_api_secret(ciphertext: str) -> str:
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("invalid_api_secret_ciphertext") from e


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sign_openapi_request(
    *,
    secret: str,
    method: str,
    path: str,
    query: str,
    body_sha256: str,
    timestamp: str,
    nonce: str,
) -> str:
    canonical = "\n".join([method.upper(), path, query or "", body_sha256, timestamp, nonce])
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def validate_timestamp(timestamp: str) -> bool:
    try:
        ts = int(timestamp)
    except Exception:
        return False
    now = int(time.time())
    return abs(now - ts) <= settings.signature_time_window_seconds


