"""账户管理业务逻辑"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import CreditAccount, CreditTransaction, SubscriptionPlan, TxType, User
from app.schemas import MeOut, RegisterOut
from app.services.billing import get_or_create_account
from app.core.security import create_access_token, hash_password, verify_password
from app.services.storage import data_dir, ensure_dir, save_bytes, to_public_file_url


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


async def build_register_response(db: AsyncSession, user: User) -> RegisterOut:
    """
    构建注册响应对象

    ### 功能说明
    - 与 build_user_response 类似，但返回 RegisterOut 类型
    - 用于注册接口的响应

    ### 参数
    - db: 数据库会话
    - user: 用户对象

    ### 返回
    - RegisterOut: 注册响应对象
    """
    acc = await get_or_create_account(db, user.id)

    return RegisterOut(
        id=user.uuid,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        subscription_plan=user.subscription_plan.value,
        subscription_ends_at=user.subscription_ends_at,
        credit_balance=acc.balance,
    )


async def register_user(
    db: AsyncSession, email: str, password: str, display_name: str
) -> tuple[User | None, str]:
    """
    用户注册业务逻辑

    ### 参数
    - db: 数据库会话
    - email: 邮箱
    - password: 密码
    - display_name: 显示名称

    ### 返回
    - (用户对象, 错误信息)，如果注册成功则错误信息为空字符串
    """
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
        subscription_plan=SubscriptionPlan.free,
    )
    db.add(u)
    await db.flush()

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


async def login_user(db: AsyncSession, email: str, password: str) -> tuple[str, str]:
    """
    用户登录业务逻辑

    ### 参数
    - db: 数据库会话
    - email: 邮箱
    - password: 密码

    ### 返回
    - (访问令牌, 错误信息)，如果登录成功则错误信息为空字符串
    """
    u = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not u or not verify_password(password, u.password_hash):
        return "", "用户名或密码错误"

    token = create_access_token(subject=f"user:{u.uuid}")
    return token, ""


async def update_user_name(db: AsyncSession, user: User, display_name: str) -> None:
    """
    更新用户昵称

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - display_name: 新的显示名称
    """
    user.display_name = display_name
    db.add(user)
    await db.flush()


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
    user.avatar_url = avatar_url
    db.add(user)
    await db.flush()

    return avatar_url, ""


async def update_user_avatar_url(db: AsyncSession, user: User, avatar_url: str) -> None:
    """
    更新用户头像URL（外部链接）

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - avatar_url: 头像URL
    """
    user.avatar_url = avatar_url
    db.add(user)
    await db.flush()


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

    user.password_hash = hash_password(new_password)
    db.add(user)
    await db.flush()

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
