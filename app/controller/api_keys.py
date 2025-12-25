"""API Key 管理业务逻辑"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey, User
from app.core.security import generate_api_key
from app.schemas import ApiKeyListItem, ApiKeyOut
from app.core.constants import SubscriptionPlanType


def _mask_api_key(api_key: str) -> str:
    """脱敏显示API Key,只显示前后部分"""
    if len(api_key) <= 12:
        return api_key
    return f"{api_key[:8]}...{api_key[-4:]}"


async def list_user_api_keys(db: AsyncSession, user: User) -> list[ApiKeyListItem]:
    """
    获取用户的所有 API Keys

    ### 参数
    - db: 数据库会话
    - user: 用户对象

    ### 返回
    - API Key 列表（脱敏显示）
    """
    keys = (
        (
            await db.execute(
                select(ApiKey)
                .where(ApiKey.user_id == user.id)
                .order_by(desc(ApiKey.id))
            )
        )
        .scalars()
        .all()
    )

    return [
        ApiKeyListItem(
            id=k.id,
            name=k.name,
            api_key_masked=_mask_api_key(k.api_key),
            is_active=k.is_active,
            expires_at=k.expires_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


async def create_user_api_key(
    db: AsyncSession, user: User, name: str, expires_days: int | None
) -> ApiKeyOut:
    """
    创建新的 API Key

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - name: API Key 名称
    - expires_days: 有效期天数（None 表示永不过期）

    ### 返回
    - 完整的 API Key 信息（包含未脱敏的 Key）
    """
    # 根据传入的天数计算有效期，None 表示永不过期
    expires_at = (
        None if expires_days is None else datetime.now() + timedelta(days=expires_days)
    )

    api_key_value = generate_api_key()
    api = ApiKey(
        user_id=user.id,
        api_key=api_key_value,
        name=name,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(api)
    await db.flush()

    return ApiKeyOut(api_key=api_key_value, expires_at=expires_at)


async def delete_user_api_key(
    db: AsyncSession, user: User, key_id: int
) -> ApiKey | None:
    """
    删除用户的 API Key

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - key_id: API Key ID

    ### 返回
    - 被删除的 API Key 对象，如果不存在则返回 None
    """
    key = (
        await db.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
        )
    ).scalar_one_or_none()

    if not key:
        return None

    await db.delete(key)
    await db.flush()
    return key


async def rotate_user_api_key(
    db: AsyncSession, user: User, name: str, expires_days: int | None
) -> ApiKeyOut:
    """
    轮换用户的 API Key（禁用所有旧 Key，创建新 Key）

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - name: 新 API Key 的名称
    - expires_days: 有效期天数（None 表示永不过期）

    ### 返回
    - 新创建的 API Key 信息
    """
    # 计算有效期
    expires_at = (
        None if expires_days is None else datetime.now() + timedelta(days=expires_days)
    )

    # 创建新 API Key
    api_key_value = generate_api_key()
    api = ApiKey(
        user_id=user.id,
        api_key=api_key_value,
        name=name,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(api)
    await db.flush()

    # 禁用所有旧的 API Key
    keys = (
        (await db.execute(select(ApiKey).where(ApiKey.user_id == user.id)))
        .scalars()
        .all()
    )
    for k in keys:
        if k.id != api.id:
            k.is_active = False
            db.add(k)

    return ApiKeyOut(api_key=api_key_value, expires_at=expires_at)


def check_enterprise_permission(user: User) -> bool:
    """
    检查用户是否有企业版权限

    ### 参数
    - user: 用户对象

    ### 返回
    - 是否有企业版权限
    """
    return bool(user.subscription_plan.value == SubscriptionPlanType.enterprise.value)
