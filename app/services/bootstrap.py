from __future__ import annotations
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_api_key, hash_password
from app.core.models import ApiKey, CreditAccount, SubscriptionPlan, User, InviteCode


async def bootstrap_admin(db: AsyncSession) -> None:
    """初始化管理员账户（包含积分账户和API Key）"""
    if not settings.admin_bootstrap:
        return

    # 检查管理员是否已存在
    admin = (
        await db.execute(select(User).where(User.email == settings.admin_email))
    ).scalar_one_or_none()

    if admin:
        # 管理员已存在，更新密码、头像等信息（确保与配置一致）
        print(f"ℹ️  管理员账号已存在：{settings.admin_email}")

        # 更新密码（每次启动时同步配置文件中的密码）
        new_password_hash = hash_password(settings.admin_password)
        if admin.password_hash != new_password_hash:
            admin.password_hash = new_password_hash
            print("   - 密码已更新")

        # 更新其他信息
        admin.display_name = "AutoGame"
        admin.avatar_url = "/files/static/avatars/autogame_icon.jpg"
        admin.is_admin = True
        # 确保管理员始终是企业版
        if admin.subscription_plan.value != SubscriptionPlan.enterprise.value:
            admin.subscription_plan = SubscriptionPlan.enterprise

        db.add(admin)
        await db.commit()
        print("   - 账号信息已同步")
        return

    # 创建管理员用户（UUID 固定为 autogame）
    admin = User(
        uuid="autogame",  # 固定 UUID
        email=settings.admin_email,
        password_hash=hash_password(settings.admin_password),
        display_name="AutoGame",
        avatar_url="/files/static/avatars/autogame_icon.jpg",  # 官方头像
        is_admin=True,
        subscription_plan=SubscriptionPlan.enterprise,  # 管理员默认企业版
    )
    db.add(admin)
    await db.flush()  # 获取 admin.id

    # 创建积分账户（初始 100,000 积分）
    credit_account = CreditAccount(
        user_id=admin.id,
        balance=100000,
    )
    db.add(credit_account)

    # 创建默认 API Key（有效期 10 年）
    api_key_value = generate_api_key()
    api_key = ApiKey(
        user_id=admin.id,
        api_key=api_key_value,
        name="默认密钥",
        is_active=True,
        expires_at=None,
    )
    db.add(api_key)

    # 创建初始邀请码（5个永久有效的邀请码）
    initial_codes = []
    for i in range(5):
        code = secrets.token_urlsafe(24)[:32]
        invite = InviteCode(
            code=code,
            created_by_user_id=admin.id,
            expires_at=None,  # 永久有效
            note=f"系统初始邀请码 #{i+1}",
        )
        db.add(invite)
        initial_codes.append(code)

    # 提交事务
    await db.commit()
    print(f"✅ 管理员账号创建完成：{settings.admin_email}")
    print("   - 初始积分：100,000")
    print(f"   - API Key: {api_key_value}")
    print("   - 初始邀请码：")
    for i, code in enumerate(initial_codes, 1):
        print(f"     {i}. {code}")
