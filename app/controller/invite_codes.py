"""邀请码管理业务逻辑"""

from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InviteCode, User, format_timezone


def generate_invite_code() -> str:
    """
    生成随机邀请码

    ### 返回
    - 32字符的随机邀请码
    """
    return secrets.token_urlsafe(24)[:32]


async def create_invite_codes(
    db: AsyncSession,
    admin_user: User,
    count: int = 1,
    expires_days: int | None = None,
    note: str = "",
) -> tuple[list[str], str]:
    """
    批量创建邀请码

    ### 参数
    - db: 数据库会话
    - admin_user: 管理员用户对象
    - count: 生成数量
    - expires_days: 有效期天数（None 表示永久有效）
    - note: 备注说明

    ### 返回
    - (邀请码列表, 错误信息)
    """
    if not admin_user.is_admin:
        return [], "仅管理员可以生成邀请码"

    codes = []
    expires_at = None
    if expires_days:
        expires_at = format_timezone() + timedelta(days=expires_days)

    for _ in range(count):
        code = generate_invite_code()
        invite = InviteCode(
            code=code,
            created_by_user_id=admin_user.id,
            expires_at=expires_at,
            note=note,
        )
        db.add(invite)
        codes.append(code)

    await db.flush()
    return codes, ""


async def get_invite_codes(
    db: AsyncSession, admin_user: User, only_unused: bool = False
) -> list[InviteCode]:
    """
    获取邀请码列表

    ### 参数
    - db: 数据库会话
    - admin_user: 管理员用户对象
    - only_unused: 是否仅显示未使用的邀请码

    ### 返回
    - 邀请码列表
    """
    query = select(InviteCode).order_by(InviteCode.created_at.desc())

    if only_unused:
        query = query.where(InviteCode.is_used == False)

    result = await db.execute(query)
    return list(result.scalars().all())


async def delete_invite_code(
    db: AsyncSession, admin_user: User, code_id: int
) -> tuple[bool, str]:
    """
    删除邀请码

    ### 参数
    - db: 数据库会话
    - admin_user: 管理员用户对象
    - code_id: 邀请码 ID

    ### 返回
    - (是否成功, 错误信息)
    """
    if not admin_user.is_admin:
        return False, "仅管理员可以删除邀请码"

    invite = (
        await db.execute(select(InviteCode).where(InviteCode.id == code_id))
    ).scalar_one_or_none()

    if not invite:
        return False, "邀请码不存在"

    if invite.is_used:
        return False, "已使用的邀请码不能删除"

    await db.delete(invite)
    await db.flush()
    return True, ""
