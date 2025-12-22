from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_api_key, generate_api_secret, encrypt_api_secret, hash_password
from app.models import ApiKey, CreditAccount, Project, User


async def ensure_user_default_project(db: AsyncSession, user: User) -> Project:
    proj = (await db.execute(select(Project).where(Project.owner_user_id == user.id))).scalars().first()
    if proj:
        return proj
    proj = Project(owner_user_id=user.id, name="default")
    db.add(proj)
    await db.flush()
    db.add(CreditAccount(project_id=proj.id, balance=0))
    await db.flush()
    # V1：默认创建一把 OpenAPI key 方便接入（用户可在 console 轮换）
    k = ApiKey(
        project_id=proj.id,
        api_key=generate_api_key(),
        api_secret_ciphertext=encrypt_api_secret(generate_api_secret()),
        is_active=True,
    )
    db.add(k)
    await db.flush()
    return proj


async def bootstrap_admin(db: AsyncSession) -> None:
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
    )
    db.add(admin)
    await db.flush()
    await ensure_user_default_project(db, admin)


