"""账户管理业务逻辑"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas import MeOut, LoginOut
from app.services.account import update_user_field
from app.services.billing import get_or_create_account
from app.core.constants import DEFAULT_SUBSCRIPTION_PLAN
from app.core.security import create_access_token, hash_password, verify_password
from app.services.storage import data_dir, ensure_dir, save_bytes, to_public_file_url
from app.models import CreditAccount, CreditTransaction, SubscriptionPlan, TxType, User


async def build_user_response(db: AsyncSession, user: User) -> MeOut:
    """
    构建用户信息响应对象

    ### 功能说明
    - 自动获取或创建积分账户
    - 统一构建用户信息响应格式
    - 避免重复代码

    ### 参数
    - db: 数据库会话
    - user: 用户对象

    ### 返回
    - MeOut: 标准化的用户信息对象
    """
    acc = await get_or_create_account(db, user.id)

    return MeOut(
        id=user.uuid,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        subscription_plan=user.subscription_plan.value,
        subscription_ends_at=user.subscription_ends_at,
        credit_balance=acc.balance,
    )


async def build_login_response(
    db: AsyncSession, user: User, access_token: str
) -> LoginOut:
    """
    构建登录响应对象
    """
    acc = await get_or_create_account(db, user.id)
    return LoginOut(
        id=user.uuid,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        subscription_plan=user.subscription_plan.value,
        subscription_ends_at=user.subscription_ends_at,
        credit_balance=acc.balance,
        access_token=access_token,
    )


async def validate_invite_code(
    db: AsyncSession, invite_code: str
) -> tuple[object | None, str]:
    """
    验证邀请码是否有效

    ### 功能说明
    - 支持特殊测试邀请码（配置在 settings.test_invite_code）
    - 验证邀请码是否存在、是否已使用、是否过期
    - 测试邀请码直接通过验证，返回特殊标记对象

    ### 参数
    - db: 数据库会话
    - invite_code: 邀请码

    ### 返回
    - (邀请码对象/特殊标记, 错误信息)
    - 如果验证成功，错误信息为空字符串
    - 对于测试邀请码，返回 "TEST" 字符串作为特殊标记

    ### 测试用法
    使用配置的测试邀请码（默认: TEST-INVITE-CODE-2024）可以绕过数据库验证
    """
    from app.models import InviteCode, format_timezone

    # 检查是否为特殊测试邀请码
    if invite_code == settings.test_invite_code:
        return "TEST", ""  # 返回特殊标记，表示是测试邀请码

    # 验证邀请码
    invite = (
        await db.execute(
            select(InviteCode).where(
                InviteCode.code == invite_code, InviteCode.is_used == False
            )
        )
    ).scalar_one_or_none()

    if not invite:
        return None, "邀请码不存在或已被使用"

    # 检查邀请码是否过期
    if invite.expires_at and invite.expires_at < format_timezone():
        return None, "邀请码已过期"

    return invite, ""


async def register_user(
    db: AsyncSession, email: str, password: str, display_name: str, invite_code: str
) -> tuple[User | None, str]:
    """
    用户注册业务逻辑

    ### 参数
    - db: 数据库会话
    - email: 邮箱
    - password: 密码
    - display_name: 显示名称
    - invite_code: 邀请码

    ### 注册流程
    1. 验证邀请码（是否存在、是否已使用、是否过期）
    2. 检查邮箱是否已存在
    3. 创建用户记录（默认为免费版订阅）
    4. 标记邀请码为已使用（测试邀请码跳过此步）
    5. 创建积分账户（初始积分根据系统配置）
    6. 记录积分流水
    7. 返回用户基本信息

    ### 返回
    - (用户对象, 错误信息)，如果注册成功则错误信息为空字符串
    """
    from app.models import format_timezone

    # 验证邀请码
    invite, error = await validate_invite_code(db, invite_code)
    if error:
        return None, error

    # 检查邮箱是否已存在
    existed = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existed:
        return None, "该邮箱已被注册"

    # 创建用户
    u = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        subscription_plan=SubscriptionPlan(DEFAULT_SUBSCRIPTION_PLAN),
    )
    db.add(u)
    await db.flush()

    # 如果未提供昵称，生成默认昵称：用户_{uuid前6位}
    if not display_name or display_name.strip() == "":
        u.display_name = f"用户_{u.uuid[:6]}"
        db.add(u)

    # 标记邀请码为已使用（测试邀请码跳过）
    if invite != "TEST":  # 测试邀请码不需要标记为已使用
        invite.is_used = True
        invite.used_by_user_id = u.id
        invite.used_at = format_timezone()
        db.add(invite)

    # 创建积分账户并赠送免费版初始积分
    acc = CreditAccount(user_id=u.id, balance=settings.register_free_point)
    db.add(acc)
    await db.flush()

    # 记录积分流水
    tx = CreditTransaction(
        account_id=acc.id,
        tx_type=TxType.subscription,
        amount=settings.register_free_point,
        ref_type="subscription",
        ref_id="free_welcome",
        note="注册赠送免费版积分",
    )
    db.add(tx)

    return u, ""


async def login_user(
    db: AsyncSession, email: str, password: str
) -> tuple[str, str, User | None]:
    """
    用户登录业务逻辑

    ### 参数
    - db: 数据库会话
    - email: 邮箱
    - password: 密码

    ### 登录流程
    1. 根据邮箱查找用户
    2. 验证密码是否正确
    3. 生成访问令牌（包含用户标识）
    4. 返回 Token

    ### 返回
    - (访问令牌, 错误信息)，如果登录成功则错误信息为空字符串
    """
    u = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not u or not verify_password(password, str(u.password_hash)):
        return "", "用户名或密码错误", None

    token = create_access_token(subject=f"user:{u.uuid}")
    return token, "", u


async def upload_user_avatar(
    db: AsyncSession, user: User, file_content: bytes, file_ext: str
) -> tuple[str, str]:
    """
    上传用户头像

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - file_content: 文件内容（字节）
    - file_ext: 文件扩展名（如 .jpg）

    ### 返回
    - (头像URL, 错误信息)，如果上传成功则错误信息为空字符串
    """
    # 保存文件到 data/avatars/{user_uuid}{ext}
    avatars_dir = ensure_dir(os.path.join(data_dir(), "avatars"))
    avatar_filename = f"{user.uuid}{file_ext}"
    avatar_path = os.path.join(avatars_dir, avatar_filename)
    save_bytes(avatar_path, file_content)

    # 生成公开访问URL
    avatar_url = to_public_file_url(avatar_path)

    # 更新用户头像
    await update_user_field(db, user, "avatar_url", avatar_url)

    return avatar_url, ""


async def change_user_password(
    db: AsyncSession, user: User, old_password: str, new_password: str
) -> tuple[bool, str]:
    """
    修改用户密码

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - old_password: 原密码
    - new_password: 新密码

    ### 返回
    - (是否成功, 错误信息)
    """
    if not verify_password(old_password, user.password_hash):
        return False, "原密码错误"

    await update_user_field(db, user, "password_hash", hash_password(new_password))

    return True, ""


def validate_avatar_file(
    content_type: str | None, filename: str | None, content: bytes
) -> tuple[bool, str, str]:
    """
    验证头像文件

    ### 参数
    - content_type: 文件 Content-Type
    - filename: 文件名
    - content: 文件内容

    ### 返回
    - (是否有效, 错误信息, 文件扩展名)
    """
    # 验证文件类型
    if not content_type or not content_type.startswith("image/"):
        return False, "只支持图片格式", ""

    # 支持的图片扩展名
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    file_ext = Path(filename or "").suffix.lower()

    if file_ext not in allowed_extensions:
        return False, f"不支持的图片格式，仅支持：{', '.join(allowed_extensions)}", ""

    # 验证大小（5MB限制）
    if len(content) > 5 * 1024 * 1024:
        return False, "图片文件不能超过5MB", ""

    if len(content) == 0:
        return False, "文件内容为空", ""

    return True, "", file_ext
