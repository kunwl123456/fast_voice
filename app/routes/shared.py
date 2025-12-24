from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Voice
from app.exceptions import AuthenticationException, NotFoundException


async def ensure_user_owns_voice(db: AsyncSession, user_id: int, voice_id: int) -> None:
    """确保用户拥有该音色或该音色是公开的"""
    v = (
        await db.execute(select(Voice).where(Voice.id == voice_id))
    ).scalar_one_or_none()
    if not v:
        raise NotFoundException("voice_not_found")
    if v.owner_user_id != user_id and not v.is_public:
        # 允许使用公共音色；私有音色必须是自己的
        raise AuthenticationException("voice_not_accessible")
