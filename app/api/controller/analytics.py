"""数据分析和统计业务逻辑"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import ApiRequestLog, User, Voice
from app.api.services.billing import get_or_create_account
from app.api.controller.subscription import get_plan_config
from app.core.schemas import (
    DashboardOut,
    RequestLogOut,
    UsageStatsOut,
    PaginatedRequestLogs,
)


async def get_user_dashboard(db: AsyncSession, user: User) -> DashboardOut:
    """
    获取用户仪表盘数据

    ### 参数
    - db: 数据库会话
    - user: 用户对象

    ### 返回
    - 仪表盘数据对象
    """
    acc = await get_or_create_account(db, user.id)
    plan_config = get_plan_config(user.subscription_plan.value)

    # 计算本月使用量（基于API请求日志）
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
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

    # 下一个账单日期（订阅到期时间）
    next_billing_date = ""  # 免费版，无需续费
    if user.subscription_ends_at:
        # 有付费订阅，显示订阅到期时间
        next_billing_date = user.subscription_ends_at.strftime("%Y-%m-%d")

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

    return DashboardOut(
        user_id=user.uuid,
        email=user.email,
        plan_name=plan_config.name,
        plan_status=plan_status,
        monthly_usage=monthly_usage,
        monthly_quota=plan_config.monthly_quota,
        usage_percent=round(usage_percent, 2),
        next_billing_date=next_billing_date,
        credit_balance=acc.balance,
        clone_count=clone_count,
        clone_limit=plan_config.clone_limit,
        api_access_enabled=plan_config.api_access,
    )


async def get_user_usage_stats(
    db: AsyncSession, user: User, days: int
) -> list[UsageStatsOut]:
    """
    获取用户的 API 使用统计（按天聚合）

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - days: 统计天数

    ### 返回
    - 每日统计数据列表
    """
    end_date = datetime.now(ZoneInfo("Asia/Shanghai"))
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
            )
        )

    return results


async def get_user_request_logs(
    db: AsyncSession, user: User, page: int, page_size: int
) -> PaginatedRequestLogs:
    """
    获取用户的 API 请求日志（分页）

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - page: 页码（从 1 开始）
    - page_size: 每页数量

    ### 返回
    - 分页的请求日志数据
    """
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
            timestamp=log.created_at,
            endpoint=log.endpoint,
            method=log.method,
            status_code=log.status_code,
            latency_ms=log.latency_ms,
            response_size=log.response_size,
            error_message=log.error_message,
        )
        for log in logs
    ]

    return PaginatedRequestLogs(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
