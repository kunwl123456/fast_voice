from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    payload = {
        "iss": settings.jwt_issuer,
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=settings.jwt_access_token_minutes)).timestamp()
        ),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer
        )
    except JWTError as e:
        raise ValueError("invalid_token") from e
    return payload


def generate_api_key() -> str:
    """生成 API Key，以 sk- 开头"""
    return "sk-" + secrets.token_urlsafe(32)


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
    canonical = "\n".join(
        [method.upper(), path, query or "", body_sha256, timestamp, nonce]
    )
    return hmac.new(
        secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def validate_timestamp(timestamp: str) -> bool:
    try:
        ts = int(timestamp)
    except Exception:
        return False
    now = int(time.time())
    return abs(now - ts) <= settings.signature_time_window_seconds
