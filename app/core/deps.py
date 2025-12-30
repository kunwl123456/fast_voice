from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import ApiKey, User
from app.core.db import AsyncSessionLocal
from app.core.error_codes import CommonError
from app.core.security import decode_access_token
from app.api.services.quota_limiter import QuotaLimiter
from app.core.exceptions import PermissionException, AuthenticationException


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


async def require_console(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    # 如果已经在 request.state 中有用户对象，直接返回（避免重复查询）
    if hasattr(request.state, "current_user"):
        return request.state.current_user

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthenticationException(
            "鉴权失败：缺少鉴权参数", error=CommonError.TOKEN_INVALID
        )

    token = auth.removeprefix("Bearer ").strip()
    payload = decode_access_token(token)
    sub = payload.get("sub")
    if not sub or not str(sub).startswith("user:"):
        raise AuthenticationException(
            "鉴权失败：请检查API Key是否存在", error=CommonError.TOKEN_INVALID
        )

    user_uuid = str(sub).split(":", 1)[1]
    user = (
        await db.execute(select(User).where(User.uuid == user_uuid))
    ).scalar_one_or_none()
    if not user:
        raise AuthenticationException(
            "鉴权失败：未找到用户", error=CommonError.TOKEN_INVALID
        )

    # 将用户对象存储到 request.state 中，供后续使用
    request.state.current_user = user

    return user


def require_admin(user: User = Depends(require_console)) -> User:
    if not user.is_admin:
        raise PermissionException("暂无权限操作！")

    return user


def get_current_user(request: Request) -> User:
    """
    直接从 request.state 获取当前用户

    前提条件：路由必须已经配置了 dependencies（如 require_admin 或 require_console_user）

    使用场景：
    - 路由器级别已配置 dependencies=[Depends(require_admin)]
    - 视图函数需要访问当前用户对象
    - 避免重复解析 token 和查询数据库

    示例：
        @admin_router.get("/example")
        async def example(user: User = Depends(get_current_user)):
            print(f"当前用户: {user.username}")
    """
    if not hasattr(request.state, "current_user"):
        raise AuthenticationException("未找到用户信息，请确保路由已配置身份验证依赖")
    return request.state.current_user


class OpenAPIPrincipal:
    """OpenAPI 调用方身份：绑定用户。"""

    def __init__(self, *, user: User, api_key: str):
        self.user = user
        self.api_key = api_key


async def require_openapi(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OpenAPIPrincipal:
    """OpenAPI 鉴权：使用 Authorization Bearer 头部携带 API Key"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthenticationException(
            "鉴权失败：缺少鉴权参数", error=CommonError.TOKEN_INVALID
        )

    api_key_value = auth.removeprefix("Bearer ").strip()
    if not api_key_value:
        raise AuthenticationException(
            "鉴权失败：缺少鉴权参数", error=CommonError.TOKEN_INVALID
        )

    if hasattr(request.state, "current_user"):
        return OpenAPIPrincipal(user=request.state.current_user, api_key=api_key_value)

    # 查询 API Key
    api = (
        await db.execute(select(ApiKey).where(ApiKey.api_key == api_key_value))
    ).scalar_one_or_none()

    if not api or not api.is_active:
        raise AuthenticationException(
            "鉴权失败：API Token不存在或已禁用", error=CommonError.TOKEN_INVALID
        )

    # 检查有效期（使用带时区的时间进行比较）
    if api.expires_at and api.expires_at < datetime.now(ZoneInfo("Asia/Shanghai")):
        raise AuthenticationException(
            "鉴权失败：API Token已过期", error=CommonError.TOKEN_INVALID
        )

    # 查询用户
    user = (
        await db.execute(select(User).where(User.id == api.user_id))
    ).scalar_one_or_none()
    if not user:
        raise AuthenticationException(
            "鉴权失败：未找到用户", error=CommonError.TOKEN_INVALID
        )

    # 检验 OpenAPI 请求次数配额
    await QuotaLimiter.check_and_increment(user)

    request.state.current_user = user
    return OpenAPIPrincipal(user=user, api_key=api_key_value)
