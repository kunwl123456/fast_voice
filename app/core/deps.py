from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import ApiKey, User
from app.core.db import AsyncSessionLocal
from app.core.exceptions import PermissionException, AuthenticationException
from app.core.security import decode_access_token


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


async def require_console_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthenticationException("鉴权失败：缺少鉴权参数")

    token = auth.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise AuthenticationException("鉴权失败：请检查API Key是否存在")

    sub = payload.get("sub")
    if not sub or not str(sub).startswith("user:"):
        raise AuthenticationException("鉴权失败：请检查API Key是否存在")

    user_uuid = str(sub).split(":", 1)[1]
    user = (
        await db.execute(select(User).where(User.uuid == user_uuid))
    ).scalar_one_or_none()
    if not user:
        raise AuthenticationException("鉴权失败：未找到用户")

    return user


def require_admin(user: User = Depends(require_console_user)) -> User:
    if not user.is_admin:
        raise PermissionException("暂无权限操作！")

    return user


class OpenAPIPrincipal:
    """OpenAPI 调用方身份：绑定用户。"""

    def __init__(self, *, user: User, api_key: str):
        self.user = user
        self.api_key = api_key


async def require_openapi_principal(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OpenAPIPrincipal:
    """简化的 OpenAPI 鉴权：使用 Authorization Bearer 头部携带 API Key"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthenticationException("鉴权失败：缺少鉴权参数")

    api_key_value = auth.removeprefix("Bearer ").strip()
    if not api_key_value:
        raise AuthenticationException("鉴权失败：缺少鉴权参数")

    # 查询 API Key
    api = (
        await db.execute(select(ApiKey).where(ApiKey.api_key == api_key_value))
    ).scalar_one_or_none()

    if not api or not api.is_active:
        raise AuthenticationException("鉴权失败：API Token不存在或已禁用")

    # 检查有效期（使用带时区的时间进行比较）
    if api.expires_at and api.expires_at < datetime.now(ZoneInfo("Asia/Shanghai")):
        raise AuthenticationException("鉴权失败：API Token已过期")

    # 查询用户
    user = (
        await db.execute(select(User).where(User.id == api.user_id))
    ).scalar_one_or_none()

    if not user:
        raise AuthenticationException("鉴权失败：未找到用户")

    return OpenAPIPrincipal(user=user, api_key=api_key_value)
