"""
应用启动引导服务
负责初始化管理员账号和订阅计划配置数据
"""

from __future__ import annotations
import secrets

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, generate_api_key
from app.core.models import (
    User,
    ApiKey,
    InviteCode,
    CreditAccount,
    SubscriptionPlanConfig,
    CreditPackage,
)


async def init_subscription_plans(db: AsyncSession) -> None:
    """
    初始化订阅计划配置数据（幂等操作）

    如果数据库中已存在计划，则更新；否则创建新计划。
    确保应用启动时数据库与代码配置保持同步。

    Args:
        db: 数据库会话
    """
    plans_data = [
        {
            "plan_code": "free",
            "name": "免费版",
            "monthly_credits": 1000,
            "monthly_quota": 100,
            "clone_limit": 3,
            "api_access": False,
            "commercial_use": False,
            "priority_support": False,
            "monthly_price": 0,  # 免费
            "currency": "USD",
            "is_active": True,
        },
        {
            "plan_code": "pro",
            "name": "专业版",
            "monthly_credits": 10000,
            "monthly_quota": 5000,
            "clone_limit": 20,
            "api_access": False,
            "commercial_use": True,
            "priority_support": True,
            "monthly_price": 9900,  # 99 元/月
            "currency": "USD",
            "is_active": True,
        },
        {
            "plan_code": "enterprise",
            "name": "企业版",
            "monthly_credits": 100000,
            "monthly_quota": 500000,
            "clone_limit": -1,  # 无限
            "api_access": True,
            "commercial_use": True,
            "priority_support": True,
            "monthly_price": 99900,  # 999 元/月
            "currency": "USD",
            "is_active": True,
        },
    ]

    for plan_data in plans_data:
        # 查询是否已存在
        result = await db.execute(
            select(SubscriptionPlanConfig).where(
                SubscriptionPlanConfig.plan_code == plan_data["plan_code"]
            )
        )
        existing_plan = result.scalar_one_or_none()

        if existing_plan:
            # 更新现有计划
            for key, value in plan_data.items():
                if key != "plan_code":  # plan_code 不可修改
                    setattr(existing_plan, key, value)
            logger.info(f"已更新订阅计划配置: {plan_data['plan_code']}")
        else:
            # 创建新计划
            new_plan = SubscriptionPlanConfig(**plan_data)
            db.add(new_plan)
            logger.info(f"已创建订阅计划配置: {plan_data['plan_code']}")

    await db.commit()
    logger.info("订阅计划配置初始化完成")


async def init_credit_packages(db: AsyncSession) -> None:
    """
    初始化积分充值档位（幂等操作）
    """
    packages_data = [
        {
            "code": "credit_500",
            "name": "500 积分",
            "credits": 500,
            "currency": "USD",
            "price": 5000,  # 50 元
            "is_active": True,
        },
        {
            "code": "credit_1000",
            "name": "1,000 积分",
            "credits": 1000,
            "currency": "USD",
            "price": 9000,  # 90 元
            "is_active": True,
        },
        {
            "code": "credit_5000",
            "name": "5,000 积分",
            "credits": 5000,
            "currency": "USD",
            "price": 40000,  # 400 元
            "is_active": True,
        },
        {
            "code": "credit_10000",
            "name": "10,000 积分",
            "credits": 10000,
            "currency": "USD",
            "price": 70000,  # 700 元
            "is_active": True,
        },
    ]

    for pkg_data in packages_data:
        result = await db.execute(
            select(CreditPackage).where(CreditPackage.code == pkg_data["code"])
        )
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in pkg_data.items():
                if key != "code":  # code 不可修改
                    setattr(existing, key, value)
            logger.info(f"已更新积分档位: {pkg_data['code']}")
        else:
            db.add(CreditPackage(**pkg_data))
            logger.info(f"已创建积分档位: {pkg_data['code']}")

    await db.commit()
    logger.info("积分档位初始化完成")


async def bootstrap_admin(db: AsyncSession) -> None:
    """
    确保管理员账号存在（幂等操作）

    Args:
        db: 数据库会话
    """
    if not settings.admin_bootstrap:
        logger.info("跳过管理员账号初始化")
        return

    # 查询管理员是否存在
    admin = (
        await db.execute(select(User).where(User.email == settings.admin_email))
    ).scalar_one_or_none()

    # 获取企业版订阅计划
    enterprise_plan = (
        await db.execute(
            select(SubscriptionPlanConfig).where(
                SubscriptionPlanConfig.plan_code == "enterprise"
            )
        )
    ).scalar_one_or_none()

    if admin:
        logger.info(f"管理员账号已存在: {settings.admin_email}")
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
        if admin.subscription_plan_id != enterprise_plan.id:
            admin.subscription_plan_id = enterprise_plan.id

        db.add(admin)
        await db.commit()
        print("   - 账号信息已同步")
        return

    # 创建管理员账号
    admin = User(
        uuid="autogame",  # 固定 UUID
        email=settings.admin_email,
        password_hash=hash_password(settings.admin_password),
        display_name="AutoGameEnterprise",
        avatar_url="/files/static/avatars/autogame_icon.jpg",  # 官方头像
        is_admin=True,
        subscription_plan_id=(
            enterprise_plan.id if enterprise_plan else None
        ),  # 管理员默认企业版
    )
    db.add(admin)
    await db.commit()
    logger.info(f"已创建管理员账号: {settings.admin_email}")
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


async def bootstrap_pro(db: AsyncSession) -> None:
    """初始化 Pro 账户（包含积分账户和API Key）"""
    pro_email = settings.pro_email
    pro_password = settings.pro_password

    pro_user = (
        await db.execute(select(User).where(User.email == pro_email))
    ).scalar_one_or_none()

    # 获取 Pro 版订阅计划
    pro_plan = (
        await db.execute(
            select(SubscriptionPlanConfig).where(
                SubscriptionPlanConfig.plan_code == "pro"
            )
        )
    ).scalar_one_or_none()

    if pro_user:
        # Pro 账号已存在，更新密码、头像等信息（确保与配置一致）
        print(f"ℹ️  Pro 账号已存在：{pro_email}")

        # 更新密码（每次启动时同步配置文件中的密码）
        new_password_hash = hash_password(pro_password)
        if pro_user.password_hash != new_password_hash:
            pro_user.password_hash = new_password_hash
            print("   - 密码已更新")

        # 更新其他信息
        pro_user.display_name = "ProAutoGame"
        pro_user.avatar_url = "/files/static/avatars/autogame_icon.jpg"
        pro_user.is_admin = False
        # 确保管理员始终是企业版
        if pro_user.subscription_plan_id != pro_plan.id:
            pro_user.subscription_plan = pro_plan

        db.add(pro_user)
        await db.commit()
        print("   - 账号信息已同步")
        return

    # 创建管理员用户（UUID 固定为 autogame）
    pro_user = User(
        uuid="pro",  # 固定 UUID
        email=pro_email,
        password_hash=hash_password(pro_password),
        display_name="ProAutoGame",
        avatar_url="/files/static/avatars/autogame_icon.jpg",  # 官方头像
        is_admin=False,
        subscription_plan=pro_plan,  # 管理员默认企业版
    )
    db.add(pro_user)
    await db.flush()  # 获取 admin.id

    # 创建积分账户（初始 100,000 积分）
    credit_account = CreditAccount(
        user_id=pro_user.id,
        balance=10000,
    )
    db.add(credit_account)

    # 创建默认 API Key（有效期 10 年）
    api_key_value = generate_api_key()
    api_key = ApiKey(
        user_id=pro_user.id,
        api_key=api_key_value,
        name="默认密钥",
        is_active=True,
        expires_at=None,
    )
    db.add(api_key)

    # 提交事务
    await db.commit()
    print(f"✅ Pro 账号创建完成：{settings.admin_email}")
    print("   - 初始积分：10,000")
    print(f"   - API Key: {api_key_value}")
