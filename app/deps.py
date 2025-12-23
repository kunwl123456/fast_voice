from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token, decrypt_api_secret, sha256_hex, sign_openapi_request, validate_timestamp
from app.db import AsyncSessionLocal
from app.models import ApiKey, User
from app.services.kv import KV


async def get_db():
    """
    FastAPI DB 依赖：成功自动 commit，异常自动 rollback。
    这是 V1 里保证“注册后能登录/创建任务能落库”的关键点。
    """
    db: AsyncSession = AsyncSessionLocal()
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


async def require_console_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    token = auth.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_token")
    sub = payload.get("sub")
    if not sub or not str(sub).startswith("user:"):
        raise HTTPException(status_code=401, detail="invalid_token_subject")
    user_id = int(str(sub).split(":", 1)[1])
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="user_not_found")
    return user


def require_admin(user: User = Depends(require_console_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin_required")
    return user


class OpenAPIPrincipal:
    """OpenAPI 调用方身份：绑定用户。"""

    def __init__(self, *, user: User, api_key: str):
        self.user = user
        self.api_key = api_key


async def require_openapi_principal(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_api_key: str = Header(..., alias="X-API-Key"),
    x_timestamp: str = Header(..., alias="X-Timestamp"),
    x_nonce: str = Header(..., alias="X-Nonce"),
    x_signature: str = Header(..., alias="X-Signature"),
) -> OpenAPIPrincipal:
    if not validate_timestamp(x_timestamp):
        raise HTTPException(status_code=401, detail="invalid_timestamp")

    api = (await db.execute(select(ApiKey).where(ApiKey.api_key == x_api_key))).scalar_one_or_none()
    if not api or not api.is_active:
        raise HTTPException(status_code=401, detail="invalid_api_key")
    user = (await db.execute(select(User).where(User.id == api.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="invalid_user")

    # nonce 防重放：同一个 api_key 下 nonce 在窗口内必须唯一
    kv = KV.from_settings()
    nonce_key = f"nonce:{x_api_key}:{x_nonce}"
    if not kv.setnx_ttl(nonce_key, "1", settings.signature_time_window_seconds):
        raise HTTPException(status_code=401, detail="replayed_nonce")

    body = request.state.raw_body if hasattr(request.state, "raw_body") else b""
    body_sha = sha256_hex(body)
    query = request.url.query
    expected = sign_openapi_request(
        secret=decrypt_api_secret(api.api_secret_ciphertext),
        method=request.method,
        path=request.url.path,
        query=query,
        body_sha256=body_sha,
        timestamp=x_timestamp,
        nonce=x_nonce,
    )
    if not secrets_compare(expected, x_signature):
        raise HTTPException(status_code=401, detail="invalid_signature")
    return OpenAPIPrincipal(user=user, api_key=x_api_key)


def secrets_compare(a: str, b: str) -> bool:
    """常量时间比较，避免 timing attack。"""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a.encode("utf-8"), b.encode("utf-8")):
        result |= x ^ y
    return result == 0


