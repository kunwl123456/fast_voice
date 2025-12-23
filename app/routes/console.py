from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.deps import get_db, require_admin, require_console_user
from app.models import ApiKey, ApiRequestLog, CreditAccount, CreditTransaction, SubscriptionPlan, TxType, User, Voice
from app.services.billing import get_or_create_account, recharge
from app.subscription import get_plan_config, get_plan_features
from app.core.security import (
    create_access_token,
    encrypt_api_secret,
    generate_api_key,
    generate_api_secret,
    hash_password,
    verify_password
)
from app.schemas import (
    ApiKeyListItem,
    ApiKeyOut,
    ChangePasswordIn,
    CreateApiKeyIn,
    CreditAccountOut,
    CreditTxOut,
    DashboardOut,
    LoginIn,
    MeOut,
    RechargeIn,
    RegisterIn,
    RenameIn,
    RequestLogOut,
    SubscriptionInfo,
    TokenOut,
    UpdateAvatarIn,
    UpgradeSubscriptionIn,
    UsageStatsOut,
)

router = APIRouter(prefix="/console", tags=["console"])


@router.post("/auth/register", response_model=MeOut)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    existed = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if existed:
        raise HTTPException(status_code=409, detail="email_exists")
    u = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        subscription_plan=SubscriptionPlan.free,
    )
    db.add(u)
    await db.flush()
    
    # 创建积分账户并赠送免费版初始积分
    acc = CreditAccount(user_id=u.id, balance=1000)
    db.add(acc)
    await db.flush()
    
    # 记录积分流水
    tx = CreditTransaction(
        account_id=acc.id,
        tx_type=TxType.subscription,
        amount=1000,
        ref_type="subscription",
        ref_id=f"free_welcome",
        note="注册赠送免费版积分",
    )
    db.add(tx)
    
    return MeOut(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        avatar_url=u.avatar_url,
        is_admin=u.is_admin,
        subscription_plan=u.subscription_plan.value,
        subscription_ends_at=u.subscription_ends_at.isoformat() if u.subscription_ends_at else None,
    )


@router.post("/auth/login", response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    u = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if not u or not verify_password(payload.password, u.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token = create_access_token(subject=f"user:{u.id}")
    return TokenOut(access_token=token)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(require_console_user)):
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        subscription_plan=user.subscription_plan.value,
        subscription_ends_at=user.subscription_ends_at.isoformat() if user.subscription_ends_at else None,
    )


@router.post("/me/rename", response_model=MeOut)
async def rename(payload: RenameIn, db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)):
    user.display_name = payload.display_name
    db.add(user)
    await db.flush()
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        subscription_plan=user.subscription_plan.value,
        subscription_ends_at=user.subscription_ends_at.isoformat() if user.subscription_ends_at else None,
    )


@router.post("/me/avatar", response_model=MeOut)
async def update_avatar(payload: UpdateAvatarIn, db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)):
    """更新用户头像"""
    user.avatar_url = payload.avatar_url
    db.add(user)
    await db.flush()
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        subscription_plan=user.subscription_plan.value,
        subscription_ends_at=user.subscription_ends_at.isoformat() if user.subscription_ends_at else None,
    )


@router.post("/me/change-password")
async def change_password(payload: ChangePasswordIn, db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="wrong_old_password")
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    return {"ok": True}


@router.get("/subscription", response_model=SubscriptionInfo)
async def get_subscription(user: User = Depends(require_console_user)):
    """获取当前订阅信息"""
    plan_config = get_plan_config(user.subscription_plan.value)
    
    # 判断订阅状态
    status = "active"
    if user.subscription_ends_at:
        if user.subscription_ends_at < datetime.now():
            status = "expired"
    
    return SubscriptionInfo(
        plan=user.subscription_plan.value,
        plan_name=plan_config.name,
        status=status,
        ends_at=user.subscription_ends_at.isoformat() if user.subscription_ends_at else None,
        features=get_plan_features(user.subscription_plan.value),
    )


@router.post("/subscription/upgrade")
async def upgrade_subscription(
    payload: UpgradeSubscriptionIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user)
):
    """升级订阅计划"""
    if payload.plan not in ["pro", "enterprise"]:
        raise HTTPException(status_code=400, detail="invalid_plan")
    
    # 计算订阅到期时间
    now = datetime.now()
    ends_at = now + timedelta(days=30 * payload.months)
    
    # 更新用户订阅
    user.subscription_plan = SubscriptionPlan(payload.plan)
    user.subscription_ends_at = ends_at
    db.add(user)
    await db.flush()
    
    # 赠送对应的月度积分
    plan_config = get_plan_config(payload.plan)
    acc = await get_or_create_account(db, user.id)
    acc.balance += plan_config.monthly_credits * payload.months
    db.add(acc)
    await db.flush()
    
    # 记录积分流水
    tx = CreditTransaction(
        account_id=acc.id,
        tx_type=TxType.subscription,
        amount=plan_config.monthly_credits * payload.months,
        ref_type="subscription",
        ref_id=f"{payload.plan}_{payload.months}m",
        note=f"订阅{plan_config.name}{payload.months}个月赠送积分",
    )
    db.add(tx)
    
    return {"ok": True, "ends_at": ends_at.isoformat()}


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user)
):
    """获取Dashboard数据"""
    acc = await get_or_create_account(db, user.id)
    plan_config = get_plan_config(user.subscription_plan.value)
    
    # 计算本月使用量（基于API请求日志）
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    monthly_usage = (await db.execute(
        select(func.count(ApiRequestLog.id))
        .where(
            ApiRequestLog.user_id == user.id,
            ApiRequestLog.created_at >= month_start,
            ApiRequestLog.status_code == 200
        )
    )).scalar() or 0
    
    usage_percent = (monthly_usage / plan_config.monthly_quota * 100) if plan_config.monthly_quota > 0 else 0
    
    # 下一个账单日期（下个月1号）
    if now.month == 12:
        next_billing_date = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_billing_date = now.replace(month=now.month + 1, day=1)
    
    # 统计克隆音色数量
    clone_count = (await db.execute(
        select(func.count(Voice.id)).where(Voice.owner_user_id == user.id)
    )).scalar() or 0
    
    # 判断计划状态
    plan_status = "active"
    if user.subscription_ends_at and user.subscription_ends_at < now:
        plan_status = "expired"
    
    return DashboardOut(
        user_id=user.id,
        email=user.email,
        plan_name=plan_config.name,
        plan_status=plan_status,
        monthly_usage=monthly_usage,
        monthly_quota=plan_config.monthly_quota,
        usage_percent=round(usage_percent, 2),
        next_billing_date=next_billing_date.strftime("%b %d, %Y"),
        credit_balance=acc.balance,
        clone_count=clone_count,
        clone_limit=plan_config.clone_limit,
        api_access_enabled=plan_config.api_access,
    )


@router.get("/api-keys", response_model=list[ApiKeyListItem])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user)
):
    """获取所有API Keys（仅企业版）"""
    if user.subscription_plan != SubscriptionPlan.enterprise:
        raise HTTPException(status_code=403, detail="api_access_requires_enterprise_plan")
    
    keys = (await db.execute(
        select(ApiKey).where(ApiKey.user_id == user.id).order_by(desc(ApiKey.id))
    )).scalars().all()
    
    return [
        ApiKeyListItem(
            id=k.id,
            api_key=k.api_key,
            api_key_masked=_mask_api_key(k.api_key),
            is_active=k.is_active,
            created_at=k.created_at.isoformat(),
        )
        for k in keys
    ]


@router.post("/api-keys", response_model=ApiKeyOut)
async def create_api_key(
    payload: CreateApiKeyIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user)
):
    """创建新的API Key（仅企业版）"""
    if user.subscription_plan != SubscriptionPlan.enterprise:
        raise HTTPException(status_code=403, detail="api_access_requires_enterprise_plan")
    
    secret = generate_api_secret()
    api = ApiKey(
        user_id=user.id,
        api_key=generate_api_key(),
        api_secret_ciphertext=encrypt_api_secret(secret),
        name=payload.name,
        is_active=True,
    )
    db.add(api)
    await db.flush()
    return ApiKeyOut(api_key=api.api_key, api_secret=secret)


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user)
):
    """删除API Key"""
    key = (await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )).scalar_one_or_none()
    
    if not key:
        raise HTTPException(status_code=404, detail="api_key_not_found")
    
    await db.delete(key)
    await db.flush()
    return {"ok": True}


@router.post("/api-keys/rotate", response_model=ApiKeyOut)
async def rotate_api_key(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user)
):
    """轮换API Key（禁用旧的，创建新的，仅企业版）"""
    if user.subscription_plan != SubscriptionPlan.enterprise:
        raise HTTPException(status_code=403, detail="api_access_requires_enterprise_plan")
    
    secret = generate_api_secret()
    api = ApiKey(
        user_id=user.id,
        api_key=generate_api_key(),
        api_secret_ciphertext=encrypt_api_secret(secret),
        name="Production Key",
        is_active=True,
    )
    db.add(api)
    await db.flush()
    
    # 禁用所有旧的API Key
    keys = (await db.execute(select(ApiKey).where(ApiKey.user_id == user.id))).scalars().all()
    for k in keys:
        if k.id != api.id:
            k.is_active = False
            db.add(k)
    
    return ApiKeyOut(api_key=api.api_key, api_secret=secret)


def _mask_api_key(api_key: str) -> str:
    """脱敏显示API Key，只显示前后部分"""
    if len(api_key) <= 12:
        return api_key
    return f"{api_key[:8]}...{api_key[-4:]}"


@router.get("/usage-stats", response_model=list[UsageStatsOut])
async def get_usage_stats(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user)
):
    """获取使用统计数据（按天聚合）"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    results = []
    for i in range(days):
        day_start = start_date + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        
        total = (await db.execute(
            select(func.count(ApiRequestLog.id))
            .where(
                ApiRequestLog.user_id == user.id,
                ApiRequestLog.created_at >= day_start,
                ApiRequestLog.created_at < day_end
            )
        )).scalar() or 0
        
        successful = (await db.execute(
            select(func.count(ApiRequestLog.id))
            .where(
                ApiRequestLog.user_id == user.id,
                ApiRequestLog.created_at >= day_start,
                ApiRequestLog.created_at < day_end,
                ApiRequestLog.status_code == 200
            )
        )).scalar() or 0
        
        results.append(UsageStatsOut(
            date=day_start.strftime("%Y-%m-%d"),
            total_requests=total,
            successful_requests=successful,
            failed_requests=total - successful,
        ))
    
    return results


@router.get("/request-logs", response_model=list[RequestLogOut])
async def get_request_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user)
):
    """获取最近的API请求日志"""
    logs = (await db.execute(
        select(ApiRequestLog)
        .where(ApiRequestLog.user_id == user.id)
        .order_by(desc(ApiRequestLog.created_at))
        .limit(limit)
    )).scalars().all()
    
    return [
        RequestLogOut(
            id=log.id,
            timestamp=log.created_at.isoformat(),
            endpoint=log.endpoint,
            method=log.method,
            status_code=log.status_code,
            latency_ms=log.latency_ms,
            response_size=log.response_size,
            error_message=log.error_message,
        )
        for log in logs
    ]


@router.get("/credits", response_model=CreditAccountOut)
async def credits(db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)):
    acc = await get_or_create_account(db, user.id)
    return CreditAccountOut(user_id=user.id, balance=acc.balance)


@router.get("/credits/transactions", response_model=list[CreditTxOut])
async def credit_transactions(db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)):
    acc = await get_or_create_account(db, user.id)
    txs = (await db.execute(
        select(CreditTransaction).where(CreditTransaction.account_id == acc.id).order_by(desc(CreditTransaction.id)).limit(200)
    )).scalars().all()
    return [
        CreditTxOut(
            id=t.id,
            tx_type=t.tx_type.value,
            amount=t.amount,
            ref_type=t.ref_type,
            ref_id=t.ref_id,
            note=t.note,
            created_at=t.created_at.isoformat(),
        )
        for t in txs
    ]


@router.post("/admin/credits/recharge")
async def recharge_credits(payload: RechargeIn, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    await recharge(db=db, user_id=payload.user_id, amount=payload.amount, note=payload.note)
    return {"ok": True}
