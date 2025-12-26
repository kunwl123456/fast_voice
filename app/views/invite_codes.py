"""邀请码管理相关路由"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import APIRouter, Depends, Query

from app.core.responses import (
    success_response,
    created_response,
    bad_request_response,
    forbidden_response,
)
from app.core.deps import get_db, require_console_user
from app.core.models import User, InviteCode
from app.controller.invite_codes import (
    create_invite_codes,
    get_invite_codes,
    delete_invite_code,
)
from app.core.schemas import (
    Response,
    CreateInviteCodeIn,
    BatchInviteCodesOut,
    InviteCodeOut,
)

router = APIRouter(prefix="/console/invite-codes", tags=["邀请码管理"])


@router.post(
    "/", summary="生成邀请码（管理员）", response_model=Response[BatchInviteCodesOut]
)
async def create_codes(
    payload: CreateInviteCodeIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """
    批量生成邀请码（仅管理员可用）

    ### 功能说明
    - 管理员可批量生成邀请码
    - 支持设置有效期
    - 支持添加备注说明

    ### 权限要求
    - 仅管理员可以调用此接口

    ### 返回内容
    - 生成的邀请码列表
    - 生成数量
    - 过期时间
    """
    if not user.is_admin:
        return forbidden_response("仅管理员可以生成邀请码")

    codes, error = await create_invite_codes(
        db, user, payload.count, payload.expires_days, payload.note
    )
    if error:
        return bad_request_response(error)

    # 获取过期时间
    expires_at = None
    if payload.expires_days and codes:
        # 查询第一个生成的邀请码获取过期时间
        invite = (
            await db.execute(select(InviteCode).where(InviteCode.code == codes[0]))
        ).scalar_one_or_none()
        if invite:
            expires_at = invite.expires_at

    result = BatchInviteCodesOut(codes=codes, count=len(codes), expires_at=expires_at)
    return created_response("邀请码生成成功", result.model_dump())


@router.get(
    "/",
    summary="获取邀请码列表（管理员）",
    response_model=Response[list[InviteCodeOut]],
)
async def list_codes(
    only_unused: bool = Query(False, description="是否仅显示未使用的邀请码"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """
    获取邀请码列表（仅管理员可用）

    ### 功能说明
    - 管理员可查看所有邀请码
    - 支持筛选未使用的邀请码
    - 显示邀请码的使用状态、使用者信息

    ### 权限要求
    - 仅管理员可以调用此接口

    ### 返回内容
    - 邀请码列表（按创建时间倒序）
    """
    if not user.is_admin:
        return forbidden_response("仅管理员可以查看邀请码")

    invites = await get_invite_codes(db, user, only_unused)

    # 构建响应数据
    result = []
    for invite in invites:
        used_by_email = None
        if invite.used_by_user_id:
            used_user = (
                await db.execute(select(User).where(User.id == invite.used_by_user_id))
            ).scalar_one_or_none()
            if used_user:
                used_by_email = used_user.email

        result.append(
            InviteCodeOut(
                id=invite.id,
                code=invite.code,
                is_used=invite.is_used,
                used_by_email=used_by_email,
                expires_at=invite.expires_at,
                note=invite.note,
                created_at=invite.created_at,
                used_at=invite.used_at,
            )
        )

    return success_response("获取成功", [item.model_dump() for item in result])


@router.delete(
    "/{code_id}", summary="删除邀请码（管理员）", response_model=Response[None]
)
async def delete_code(
    code_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """
    删除邀请码（仅管理员可用）

    ### 功能说明
    - 管理员可删除未使用的邀请码
    - 已使用的邀请码不能删除

    ### 权限要求
    - 仅管理员可以调用此接口

    ### 注意事项
    - 已使用的邀请码无法删除（保留历史记录）
    """
    if not user.is_admin:
        return forbidden_response("仅管理员可以删除邀请码")

    success, error = await delete_invite_code(db, user, code_id)
    if not success:
        return bad_request_response(error)

    return success_response("删除成功")
