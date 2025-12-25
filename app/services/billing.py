from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import CreditAccount, CreditTransaction, TxType


def utf8_bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def calc_cost(text: str) -> int:
    return utf8_bytes(text) * int(settings.credit_price_per_utf8_byte)


async def get_or_create_account(db: AsyncSession, user_id: int) -> CreditAccount:
    acc = (
        await db.execute(select(CreditAccount).where(CreditAccount.user_id == user_id))
    ).scalar_one_or_none()
    if acc:
        return acc
    acc = CreditAccount(user_id=user_id, balance=0)
    db.add(acc)
    await db.flush()
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
    """
    acc = await get_or_create_account(db, user_id)
    if acc.balance < amount:
        raise ValueError("insufficient_credits")
    acc.balance -= amount
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
    """任务失败退款（V1：全额退款）。"""
    if amount <= 0:
        return
    acc = await get_or_create_account(db, user_id)
    acc.balance += amount
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
    ref_id: str = "",
) -> None:
    """充值。"""
    acc = await get_or_create_account(db, user_id)
    acc.balance += amount
    db.add(
        CreditTransaction(
            account_id=acc.id,
            tx_type=TxType.recharge,
            amount=amount,
            ref_type="recharge",
            ref_id=str(ref_id),
            note=note,
        )
    )
