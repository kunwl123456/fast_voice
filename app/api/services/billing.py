from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import TxType
from app.core.models import CreditAccount, CreditTransaction


def utf8_bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def calc_cost(text: str) -> int:
    return utf8_bytes(text) * int(settings.credit_price_per_utf8_byte)


async def get_or_create_account(
    db: AsyncSession, user_id: int, *, lock: bool = False
) -> CreditAccount:
    """
    获取或创建积分账户

    Args:
        db: 数据库会话
        user_id: 用户ID
        lock: 是否加行锁(SELECT FOR UPDATE),用于防止并发竞态
    """
    stmt = select(CreditAccount).where(CreditAccount.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()

    acc = (await db.execute(stmt)).scalar_one_or_none()
    if acc:
        return acc

    # 账户不存在,创建新账户
    acc = CreditAccount(user_id=user_id, balance=0)
    db.add(acc)
    await db.flush()

    # 如果需要加锁,刷新后重新查询并加锁
    if lock:
        stmt = (
            select(CreditAccount)
            .where(CreditAccount.user_id == user_id)
            .with_for_update()
        )
        acc = (await db.execute(stmt)).scalar_one()

    return acc


async def ensure_sufficient_and_consume(
    *,
    db: AsyncSession,
    user_id: int,
    amount: int,
    ref_type: str,
    ref_id: str,
    note: str = "",
) -> None:
    """
    预扣费（创建任务时调用）：
    - 余额不足 -> 抛出 ValueError("insufficient_credits")
    - 成功 -> 写一条 consume(-amount) 流水

    注意：使用 SELECT FOR UPDATE 行锁防止并发竞态条件
    """
    # 🔒 使用行锁获取账户，防止并发超额消费
    acc = await get_or_create_account(db, user_id, lock=True)

    # 检查余额是否充足
    if acc.balance < amount:
        raise ValueError("insufficient_credits")

    # 扣减余额
    acc.balance -= amount

    # 记录消费流水（amount 为负数表示消费）
    db.add(
        CreditTransaction(
            account_id=acc.id,
            tx_type=TxType.consume,
            amount=-amount,
            ref_type=ref_type,
            ref_id=str(ref_id),
            note=note,
        )
    )


async def refund(
    *,
    db: AsyncSession,
    user_id: int,
    amount: int,
    ref_type: str,
    ref_id: str,
    note: str = "",
) -> None:
    """
    任务失败退款（V1：全额退款）

    注意：使用 SELECT FOR UPDATE 行锁保证退款操作的原子性
    """
    if amount <= 0:
        return

    # 🔒 使用行锁获取账户，保证退款操作的一致性
    acc = await get_or_create_account(db, user_id, lock=True)

    # 增加余额
    acc.balance += amount

    # 记录退款流水（amount 为正数表示退款）
    db.add(
        CreditTransaction(
            account_id=acc.id,
            tx_type=TxType.refund,
            amount=amount,
            ref_type=ref_type,
            ref_id=str(ref_id),
            note=note,
        )
    )


async def recharge(
    *,
    db: AsyncSession,
    user_id: int,
    amount: int,
    note: str,
    ref_id: str,
    ref_type: str,
    tx_type: TxType,
    commit: bool = True,
) -> None:
    """
    充值

    注意：使用 SELECT FOR UPDATE 行锁保证充值操作的原子性
    """
    # 🔒 使用行锁获取账户，保证充值操作的一致性
    acc = await get_or_create_account(db, user_id, lock=True)

    # 增加余额
    acc.balance += amount
    db.add(acc)

    # 记录积分流水
    db.add(
        CreditTransaction(
            account_id=acc.id,
            tx_type=tx_type,
            amount=amount,
            ref_type=ref_type,
            ref_id=str(ref_id),
            note=note,
        )
    )
    # 事务边界由调用方控制：默认兼容旧行为直接提交；
    # 在“回调履约”等需要原子性的场景，可传 commit=False 由外层统一 commit。
    if commit:
        await db.commit()
    else:
        await db.flush()
