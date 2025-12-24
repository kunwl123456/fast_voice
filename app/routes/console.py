from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.models import (
    ApiKey,
    ApiRequestLog,
    CreditAccount,
    CreditTransaction,
    SubscriptionPlan,
    TxType,
    User,
    Voice,
)
from app.responses import (
    success_response,
    created_response,
    conflict_response,
    unauthorized_response,
    forbidden_response,
    not_found_response,
    bad_request_response,
)
from app.services.billing import get_or_create_account, recharge
from app.services.storage import data_dir, ensure_dir, save_bytes, to_public_file_url
from app.subscription import get_plan_config, get_plan_features
from app.deps import get_db, require_admin, require_console_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_api_key,
    hash_password,
    verify_password,
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
    RegisterOut,
    RenameIn,
    RequestLogOut,
    SubscriptionInfo,
    TokenOut,
    UsageStatsOut,
    UpdateAvatarIn,
    UpgradeSubscriptionIn,
    PaginatedRequestLogs,
)

router = APIRouter(prefix="/console", tags=["console"])


@router.post("/auth/register")
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    existed = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existed:
        return conflict_response("该邮箱已被注册", {"email": payload.email})

    u = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
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

    user_data = RegisterOut(
        id=u.uuid,
        email=u.email,
        display_name=u.display_name,
        avatar_url=u.avatar_url,
        is_admin=u.is_admin,
        subscription_plan=u.subscription_plan.value,
        subscription_ends_at=(
            u.subscription_ends_at.isoformat() if u.subscription_ends_at else None
        ),
        credit_balance=acc.balance,
    )

    return created_response("注册成功", user_data.model_dump())


@router.post("/auth/login")
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    u = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if not u or not verify_password(payload.password, u.password_hash):
        return unauthorized_response("用户名或密码错误")

    token = create_access_token(subject=f"user:{u.uuid}")
    token_data = TokenOut(access_token=token)

    return success_response("登录成功", token_data.model_dump())


@router.get("/me")
async def me(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)
):
    """获取当前用户信息"""
    acc = await get_or_create_account(db, user.id)
    user_data = MeOut(
        id=user.uuid,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        subscription_plan=user.subscription_plan.value,
        subscription_ends_at=(
            user.subscription_ends_at.isoformat() if user.subscription_ends_at else None
        ),
        credit_balance=acc.balance,
    )
    return success_response("获取成功", user_data.model_dump())


@router.post("/me/rename")
async def rename(
    payload: RenameIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """修改用户昵称"""
    user.display_name = payload.display_name
    db.add(user)
    await db.flush()

    user_data = MeOut(
        id=user.uuid,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        subscription_plan=user.subscription_plan.value,
        subscription_ends_at=(
            user.subscription_ends_at.isoformat() if user.subscription_ends_at else None
        ),
    )
    return success_response("修改成功", user_data.model_dump())


@router.post("/me/avatar/upload")
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """上传用户头像图片
    
    支持的图片格式：jpg, jpeg, png, gif, webp
    文件大小限制：5MB
    """
    # 验证文件类型
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片格式")
    
    # 支持的图片扩展名
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    file_ext = Path(file.filename or "").suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式，仅支持：{', '.join(allowed_extensions)}"
        )
    
    # 读取文件内容并验证大小（5MB限制）
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(status_code=400, detail="图片文件不能超过5MB")
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")
    
    # 保存文件到 data/avatars/{user_uuid}{ext}
    avatars_dir = ensure_dir(os.path.join(data_dir(), "avatars"))
    avatar_filename = f"{user.uuid}{file_ext}"
    avatar_path = os.path.join(avatars_dir, avatar_filename)
    save_bytes(avatar_path, content)
    
    # 生成公开访问URL
    avatar_url = to_public_file_url(avatar_path)
    
    # 更新用户头像
    user.avatar_url = avatar_url
    db.add(user)
    await db.flush()
    
    # 获取积分余额
    acc = await get_or_create_account(db, user.id)
    
    user_data = MeOut(
        id=user.uuid,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        subscription_plan=user.subscription_plan.value,
        subscription_ends_at=(
            user.subscription_ends_at.isoformat() if user.subscription_ends_at else None
        ),
        credit_balance=acc.balance,
    )
    return success_response("头像上传成功", user_data.model_dump())


@router.post("/me/avatar")
async def update_avatar(
    payload: UpdateAvatarIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """更新用户头像URL（使用外部链接）"""
    user.avatar_url = payload.avatar_url
    db.add(user)
    await db.flush()
    
    # 获取积分余额
    acc = await get_or_create_account(db, user.id)

    user_data = MeOut(
        id=user.uuid,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        subscription_plan=user.subscription_plan.value,
        subscription_ends_at=(
            user.subscription_ends_at.isoformat() if user.subscription_ends_at else None
        ),
        credit_balance=acc.balance,
    )
    return success_response("头像更新成功", user_data.model_dump())


@router.post("/me/change-password")
async def change_password(
    payload: ChangePasswordIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """修改密码"""
    if not verify_password(payload.old_password, user.password_hash):
        return bad_request_response("原密码错误")
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    return success_response("密码修改成功")


@router.get("/subscription")
async def get_subscription(user: User = Depends(require_console_user)):
    """获取当前订阅信息"""
    plan_config = get_plan_config(user.subscription_plan.value)

    # 判断订阅状态
    status = "active"
    if user.subscription_ends_at:
        if user.subscription_ends_at < datetime.now():
            status = "expired"

    subscription_data = SubscriptionInfo(
        plan=user.subscription_plan.value,
        plan_name=plan_config.name,
        status=status,
        ends_at=(
            user.subscription_ends_at.isoformat() if user.subscription_ends_at else None
        ),
        features=get_plan_features(user.subscription_plan.value),
    )
    return success_response("获取成功", subscription_data.model_dump())


@router.post("/subscription/upgrade")
async def upgrade_subscription(
    payload: UpgradeSubscriptionIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """升级订阅计划"""
    if payload.plan not in ["pro", "enterprise"]:
        return bad_request_response(
            "无效的订阅计划", {"valid_plans": ["pro", "enterprise"]}
        )

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

    return success_response(
        "订阅升级成功",
        {
            "plan": payload.plan,
            "ends_at": ends_at.isoformat(),
            "credits_added": plan_config.monthly_credits * payload.months,
        },
    )


@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)
):
    """获取Dashboard数据"""
    acc = await get_or_create_account(db, user.id)
    plan_config = get_plan_config(user.subscription_plan.value)

    # 计算本月使用量（基于API请求日志）
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    monthly_usage = (
        await db.execute(
            select(func.count(ApiRequestLog.id)).where(
                ApiRequestLog.user_id == user.id,
                ApiRequestLog.created_at >= month_start,
                ApiRequestLog.status_code == 200,
            )
        )
    ).scalar() or 0

    usage_percent = (
        (monthly_usage / plan_config.monthly_quota * 100)
        if plan_config.monthly_quota > 0
        else 0
    )

    # 下一个账单日期（下个月1号）
    if now.month == 12:
        next_billing_date = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_billing_date = now.replace(month=now.month + 1, day=1)

    # 统计克隆音色数量
    clone_count = (
        await db.execute(
            select(func.count(Voice.id)).where(Voice.owner_user_id == user.id)
        )
    ).scalar() or 0

    # 判断计划状态
    plan_status = "active"
    if user.subscription_ends_at and user.subscription_ends_at < now:
        plan_status = "expired"

    dashboard_data = DashboardOut(
        user_id=user.uuid,
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

    return success_response("获取成功", dashboard_data.model_dump())


@router.get("/api-keys")
async def list_api_keys(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)
):
    """获取所有API Keys（仅企业版）"""
    if user.subscription_plan != SubscriptionPlan.enterprise:
        return forbidden_response("API访问需要企业版订阅")

    keys = (
        (
            await db.execute(
                select(ApiKey)
                .where(ApiKey.user_id == user.id)
                .order_by(desc(ApiKey.id))
            )
        )
        .scalars()
        .all()
    )

    api_keys_data = [
        ApiKeyListItem(
            id=k.id,
            name=k.name,
            api_key_masked=_mask_api_key(k.api_key),
            is_active=k.is_active,
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            created_at=k.created_at.isoformat(),
        ).model_dump()
        for k in keys
    ]

    return success_response("获取成功", api_keys_data)


@router.post("/api-keys")
async def create_api_key(
    payload: CreateApiKeyIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """创建新的API Key（仅企业版）"""
    if user.subscription_plan != SubscriptionPlan.enterprise:
        return forbidden_response("API访问需要企业版订阅")

    # 根据传入的天数计算有效期，None 表示永不过期
    expires_at = (
        None
        if payload.expires_days is None
        else datetime.now() + timedelta(days=payload.expires_days)
    )

    api_key_value = generate_api_key()
    api = ApiKey(
        user_id=user.id,
        api_key=api_key_value,
        name=payload.name,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(api)
    await db.flush()

    api_key_data = ApiKeyOut(
        api_key=api_key_value, expires_at=expires_at.isoformat() if expires_at else None
    )
    return created_response("API Key 创建成功", api_key_data.model_dump())


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """删除API Key"""
    key = (
        await db.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
        )
    ).scalar_one_or_none()

    if not key:
        return not_found_response("API Key 不存在", {"key_id": key_id})

    await db.delete(key)
    await db.flush()
    return success_response("删除成功")


@router.post("/api-keys/rotate")
async def rotate_api_key(
    payload: CreateApiKeyIn = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """轮换API Key（禁用旧的，创建新的，仅企业版）"""
    if user.subscription_plan != SubscriptionPlan.enterprise:
        return forbidden_response("API访问需要企业版订阅")

    # 如果提供了 payload，使用其中的有效期，否则默认不過期
    if payload and payload.expires_days is not None:
        expires_at = datetime.now() + timedelta(days=payload.expires_days)
    else:
        expires_at = None  # 永不过期

    api_key_value = generate_api_key()
    api = ApiKey(
        user_id=user.id,
        api_key=api_key_value,
        name="Production Key",
        is_active=True,
        expires_at=expires_at,
    )
    db.add(api)
    await db.flush()

    # 禁用所有旧的API Key
    keys = (
        (await db.execute(select(ApiKey).where(ApiKey.user_id == user.id)))
        .scalars()
        .all()
    )
    for k in keys:
        if k.id != api.id:
            k.is_active = False
            db.add(k)

    api_key_data = ApiKeyOut(
        api_key=api_key_value, expires_at=expires_at.isoformat() if expires_at else None
    )
    return created_response("API Key 轮换成功", api_key_data.model_dump())


def _mask_api_key(api_key: str) -> str:
    """脱敏显示API Key，只显示前后部分"""
    if len(api_key) <= 12:
        return api_key
    return f"{api_key[:8]}...{api_key[-4:]}"


@router.get("/usage-stats")
async def get_usage_stats(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """获取使用统计数据（按天聚合）"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    results = []
    for i in range(days):
        day_start = start_date + timedelta(days=i)
        day_end = day_start + timedelta(days=1)

        total = (
            await db.execute(
                select(func.count(ApiRequestLog.id)).where(
                    ApiRequestLog.user_id == user.id,
                    ApiRequestLog.created_at >= day_start,
                    ApiRequestLog.created_at < day_end,
                )
            )
        ).scalar() or 0

        successful = (
            await db.execute(
                select(func.count(ApiRequestLog.id)).where(
                    ApiRequestLog.user_id == user.id,
                    ApiRequestLog.created_at >= day_start,
                    ApiRequestLog.created_at < day_end,
                    ApiRequestLog.status_code == 200,
                )
            )
        ).scalar() or 0

        results.append(
            UsageStatsOut(
                date=day_start.strftime("%Y-%m-%d"),
                total_requests=total,
                successful_requests=successful,
                failed_requests=total - successful,
            ).model_dump()
        )

    return success_response("获取成功", results)


@router.get("/request-logs")
async def get_request_logs(
    page: int = Query(default=1, ge=1, description="页码，从1开始"),
    page_size: int = Query(default=50, ge=1, le=200, description="每页数量，最多200条"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """获取API请求日志（分页）"""
    # 计算偏移量
    offset = (page - 1) * page_size

    # 查询总数
    total_count = (
        await db.execute(
            select(func.count(ApiRequestLog.id)).where(ApiRequestLog.user_id == user.id)
        )
    ).scalar_one()

    # 查询日志
    logs = (
        (
            await db.execute(
                select(ApiRequestLog)
                .where(ApiRequestLog.user_id == user.id)
                .order_by(desc(ApiRequestLog.created_at))
                .limit(page_size)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )

    # 计算总页数
    total_pages = (total_count + page_size - 1) // page_size  # 向上取整

    items = [
        RequestLogOut(
            id=log.id,
            timestamp=log.created_at.isoformat(),
            endpoint=log.endpoint,
            method=log.method,
            status_code=log.status_code,
            latency_ms=log.latency_ms,
            response_size=log.response_size,
            error_message=log.error_message,
        ).model_dump()
        for log in logs
    ]

    pagination_data = PaginatedRequestLogs(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    return success_response("获取成功", pagination_data.model_dump())


@router.get("/credits")
async def credits(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)
):
    """获取积分余额"""
    acc = await get_or_create_account(db, user.id)
    credit_data = CreditAccountOut(user_id=user.uuid, balance=acc.balance)
    return success_response("获取成功", credit_data.model_dump())


@router.get("/credits/transactions")
async def credit_transactions(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)
):
    """获取积分交易记录"""
    acc = await get_or_create_account(db, user.id)
    txs = (
        (
            await db.execute(
                select(CreditTransaction)
                .where(CreditTransaction.account_id == acc.id)
                .order_by(desc(CreditTransaction.id))
                .limit(200)
            )
        )
        .scalars()
        .all()
    )

    transactions_data = [
        CreditTxOut(
            id=t.id,
            tx_type=t.tx_type.value,
            amount=t.amount,
            ref_type=t.ref_type,
            ref_id=t.ref_id,
            note=t.note,
            created_at=t.created_at.isoformat(),
        ).model_dump()
        for t in txs
    ]

    return success_response("获取成功", transactions_data)


@router.post("/admin/credits/recharge")
async def recharge_credits(
    payload: RechargeIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员充值积分"""
    await recharge(
        db=db, user_id=payload.user_id, amount=payload.amount, note=payload.note
    )
    return success_response(
        "充值成功", {"user_id": payload.user_id, "amount": payload.amount}
    )
