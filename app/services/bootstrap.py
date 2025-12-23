from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models import SubscriptionPlan, User


async def bootstrap_admin(db: AsyncSession) -> None:
    """初始化管理员账户"""
    if not settings.admin_bootstrap:
        return
    admin = (await db.execute(select(User).where(User.email == settings.admin_email))).scalar_one_or_none()
    if admin:
        return
    admin = User(
        email=settings.admin_email,
        password_hash=hash_password(settings.admin_password),
        display_name="admin",
        is_admin=True,
        subscription_plan=SubscriptionPlan.enterprise,  # 管理员默认企业版
    )
    db.add(admin)
    await db.flush()
