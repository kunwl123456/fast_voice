from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User
from app.services.bootstrap import ensure_user_default_project


async def get_default_project(db: AsyncSession, user: User) -> Project:
    return await ensure_user_default_project(db, user)


async def ensure_project_owns_voice(db: AsyncSession, project_id: int, voice_id: int) -> None:
    from app.models import Voice

    v = (await db.execute(select(Voice).where(Voice.id == voice_id))).scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="voice_not_found")
    if v.owner_project_id != project_id and not v.is_public:
        # V1：允许使用公共音色；私有音色必须是自己的
        raise HTTPException(status_code=403, detail="voice_not_accessible")


