from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from passlib.context import CryptContext
from jose import jwt, JWTError, ExpiredSignatureError

from app.core.config import settings
from app.core.error_codes import CommonError
from app.core.exceptions import AuthenticationException


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
    except ExpiredSignatureError:
        raise AuthenticationException(
            "鉴权失败：登录状态已过期", error=CommonError.TOKEN_EXPIRED
        )
    except JWTError as err:
        raise AuthenticationException(
            f"鉴权失败：{err}", error=CommonError.TOKEN_INVALID
        )
    return payload


def generate_api_key() -> str:
    """生成 API Key，以 sk- 开头"""
    return "sk-" + secrets.token_urlsafe(32)
