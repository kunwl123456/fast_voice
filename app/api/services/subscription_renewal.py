"""
订阅计划自动续赠服务
功能：每月自动为付费用户续赠积分
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import TxType
from app.core.models import User, CreditTransaction
from app.api.services.billing import get_or_create_account
from app.api.services.plan_config import get_plan_config_by_id


async def renew_monthly_credits_for_user(db: AsyncSession, user: User) -> int:
    """
    为单个用户续赠月度积分（Anniversary Logic）
    """
    # 获取计划配置
    plan_config = await get_plan_config_by_id(db, user.subscription_plan_id)

    # 免费用户不续赠（注册时已给初始积分）
    if not plan_config or plan_config.plan_code == "free":
        return 0

    # 检查订阅是否有效（防止已过期但未降级的用户）
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    if user.subscription_ends_at and user.subscription_ends_at < now:
        logger.info(f"用户 {user.email} 订阅已过期，跳过续赠")
        return 0

    if not plan_config:
        logger.warning(f"未找到用户 {user.email} 的计划配置")
        return 0

    # 获取积分账户
    acc = await get_or_create_account(db, user.id)

    # 策略：查询该用户最近一次订阅积分发放时间
    # 注意：ref_type='monthly_renewal' 是定时任务发的，ref_type='subscription' 是下单发的
    # 这两者都属于"订阅积分"，需要一起查
    last_tx = await db.execute(
        select(CreditTransaction)
        .where(
            CreditTransaction.account_id == acc.id,
            CreditTransaction.tx_type == TxType.subscription,
        )
        .order_by(CreditTransaction.created_at.desc())
        .limit(1)
    )
    last_tx_obj = last_tx.scalars().first()

    should_renew = False

    if not last_tx_obj:
        # 异常情况：付费用户没有流水？（可能是历史数据或手动改表）
        # 补发一次，作为新的起点
        logger.warning(f"用户 {user.email} 是付费用户但无订阅积分流水，执行补发")
        should_renew = True
    else:
        # 检查是否距离上次发放超过 30 天
        # 这里使用 29 天 23 小时作为缓冲，防止时间偏移导致漏发
        days_since = (now - last_tx_obj.created_at).total_seconds() / 86400
        if days_since >= 30:
            should_renew = True
            logger.info(
                f"用户 {user.email} 距离上次续赠已过 {days_since:.1f} 天，准备续赠"
            )
        else:
            # 还没到时间
            return 0

    if should_renew:
        # 二次检查：如果这次发了，会不会超出订阅有效期？
        # 如果当前时间 + 1天 > 订阅结束时间，说明是临期，不应该发下个月的了
        # 例如：订阅结束时间是 10月1日 12:00。
        # 现在是 10月1日 03:00。
        # 此时 days_since >= 30 可能成立（假设上次是 9月1日 03:00）。
        # 但既然还有几小时就过期了，是否应该发？
        # 逻辑：订阅是“预付费”制。
        # 下单时（9月1日）发了 Month 1。
        # 10月1日是 Month 1 结束，Month 2 开始。
        # 如果用户只买了 1 个月，subscription_ends_at 是 10月1日。
        # 此时 check_expired_task 还没跑（或者跑了但还没过期）。
        # 如果我们发了，就是 Month 2 的积分。但用户并没有付 Month 2 的钱。
        # 所以必须确保：next_renewal_date < subscription_ends_at

        # 假设今天是续赠日。续赠的是"未来30天"的积分。
        # 所以只有当用户的 subscription_ends_at 足够覆盖未来这段时间（或大部分）才发？
        # 或者更简单的原则：只要用户还剩 > 1天的订阅时长，就发？
        # 实际上，如果 subscription_ends_at 就在今天，说明是最后一天，不应该发新周期的分。
        # 只有当 subscription_ends_at 至少比现在晚 28 天（大约一个月）时才发？
        # 假设用户买了 2 个月。
        # T0: 发 Month 1。 EndsAt = T60。
        # T30: LastTx = T0。 Diff=30。 EndsAt - T30 = 30 days。 发 Month 2。 OK。
        # T60: LastTx = T30。 Diff=30。 EndsAt - T60 = 0。 不发。 OK。

        days_remaining = (user.subscription_ends_at - now).total_seconds() / 86400
        if days_remaining < 20:  # 宽松一点，少于20天认为不包含下一个完整月
            logger.info(
                f"用户 {user.email} 剩余订阅时长不足 ({days_remaining:.1f}天)，不予续赠"
            )
            return 0

        credits_to_add = plan_config.monthly_credits

        # 增加积分
        acc.balance += credits_to_add
        db.add(acc)

        # 记录流水
        # 使用新的 ref_id 格式：plan_YYYYMMDD，方便排查
        ref_id = f"{plan_config.plan_code}_{now.strftime('%Y%m%d')}"

        tx = CreditTransaction(
            account_id=acc.id,
            tx_type=TxType.subscription,
            amount=credits_to_add,
            ref_type="monthly_renewal",
            ref_id=ref_id,
            note=f"月度自动续赠积分（{plan_config.name}）",
        )
        db.add(tx)

        logger.info(
            f"为用户 {user.email} 续赠 {credits_to_add} 积分" f"（{plan_config.name}）"
        )
        return credits_to_add

    return 0


async def renew_monthly_credits_batch(db: AsyncSession) -> dict:
    """
    批量为所有付费用户续赠月度积分

    定时任务：每日凌晨执行（轮询所有付费用户，检查是否到期）

    Returns:
        dict: 续赠统计信息
    """
    logger.info("开始执行月度积分续赠任务（每日轮询）")

    now = datetime.now(ZoneInfo("Asia/Shanghai"))

    stats = {
        "total_users": 0,
        "success_count": 0,
        "failed_count": 0,
        "total_credits": 0,
    }

    # 分批处理配置
    BATCH_SIZE = 100
    last_id = 0

    while True:
        # 分页查询用户（Keyset Pagination）
        users = (
            (
                await db.execute(
                    select(User)
                    .where(
                        User.subscription_plan_id.isnot(None),
                        User.subscription_ends_at > now,
                        User.id > last_id,
                    )
                    .order_by(User.id)
                    .limit(BATCH_SIZE)
                )
            )
            .scalars()
            .all()
        )

        if not users:
            break

        stats["total_users"] += len(users)
        last_id = users[-1].id

        for user in users:
            try:
                # 使用嵌套事务隔离单个用户的失败
                async with db.begin_nested():
                    credits = await renew_monthly_credits_for_user(db, user)
                    if credits > 0:
                        stats["success_count"] += 1
                        stats["total_credits"] += credits
            except Exception as e:
                stats["failed_count"] += 1
                logger.error(f"为用户 {user.email} 续赠积分失败: {e}")

        # 每批次提交一次，释放锁和内存
        try:
            await db.commit()
        except Exception as e:
            logger.error(f"批次提交失败 (last_id={last_id}): {e}")
            await db.rollback()

    logger.info(
        f"月度积分续赠任务完成: "
        f"处理 {stats['success_count']}/{stats['total_users']} 用户, "
        f"总计发放 {stats['total_credits']} 积分"
    )

    return stats


async def downgrade_expired_users(db: AsyncSession) -> dict:
    """
    检查并降级已过期的订阅用户

    定时任务：每日执行
    """
    logger.info("开始检查过期订阅")

    # 获取免费计划配置
    from app.api.services.plan_config import query_plan_config
    from app.core.constants import DEFAULT_SUBSCRIPTION_PLAN

    free_plan = await query_plan_config(db, DEFAULT_SUBSCRIPTION_PLAN)
    if not free_plan:
        logger.error(f"未找到默认订阅计划配置: {DEFAULT_SUBSCRIPTION_PLAN}")
        return {"error": "default_plan_not_found"}

    now = datetime.now(ZoneInfo("Asia/Shanghai"))

    stats = {
        "downgraded_count": 0,
        "failed_count": 0,
    }

    BATCH_SIZE = 100
    last_id = 0

    while True:
        # 分批查询过期用户
        users = (
            (
                await db.execute(
                    select(User)
                    .where(
                        User.subscription_plan_id != free_plan.id,
                        User.subscription_ends_at < now,
                        User.subscription_ends_at.isnot(None),
                        User.id > last_id,
                    )
                    .order_by(User.id)
                    .limit(BATCH_SIZE)
                )
            )
            .scalars()
            .all()
        )

        if not users:
            break

        last_id = users[-1].id

        for user in users:
            try:
                # 嵌套事务隔离
                async with db.begin_nested():
                    old_plan_id = user.subscription_plan_id
                    user.subscription_plan_id = free_plan.id
                    user.subscription_ends_at = None
                    db.add(user)

                    logger.info(
                        f"用户 {user.email} 订阅已过期，降级为 {DEFAULT_SUBSCRIPTION_PLAN} "
                        f"(原计划ID: {old_plan_id})"
                    )
                    stats["downgraded_count"] += 1
            except Exception as e:
                stats["failed_count"] += 1
                logger.error(f"降级用户 {user.email} 失败: {e}")

        try:
            await db.commit()
        except Exception as e:
            logger.error(f"批次提交失败 (降级, last_id={last_id}): {e}")
            await db.rollback()

    logger.info(
        f"过期订阅检查完成: 降级 {stats['downgraded_count']} 用户, "
        f"失败 {stats['failed_count']}"
    )

    return stats
