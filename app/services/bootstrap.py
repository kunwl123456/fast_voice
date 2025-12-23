from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_api_key, generate_api_secret, encrypt_api_secret, hash_password
from app.models import ApiKey, CreditAccount, SubscriptionPlan, User


async def bootstrap_admin(db: AsyncSession) -> None:
    """初始化管理员账户（包含积分账户和API Key）"""
    if not settings.admin_bootstrap:
        return
    
    # 检查管理员是否已存在
    admin = (await db.execute(select(User).where(User.email == settings.admin_email))).scalar_one_or_none()
    if admin:
        print(f"ℹ️  管理员账号已存在：{settings.admin_email}")
        return
    
    # 创建管理员用户
    admin = User(
        email=settings.admin_email,
        password_hash=hash_password(settings.admin_password),
        display_name="admin",
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
    
    # 创建默认 API Key
    api_key = ApiKey(
        user_id=admin.id,
        api_key=generate_api_key(),
        api_secret_ciphertext=encrypt_api_secret(generate_api_secret()),
        name="默认密钥",
        is_active=True,
    )
    db.add(api_key)
    
    # 提交事务
    await db.commit()
    print(f"✅ 管理员账号创建完成：{settings.admin_email}")
    print(f"   - 初始积分：100,000")
    print(f"   - API Key: {api_key.api_key}")
