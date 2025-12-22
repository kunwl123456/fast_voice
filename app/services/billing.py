from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import CreditAccount, CreditTransaction, TxType


def utf8_bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def calc_cost(text: str) -> int:
    return utf8_bytes(text) * int(settings.credit_price_per_utf8_byte)


async def get_or_create_account(db: AsyncSession, project_id: int) -> CreditAccount:
    acc = (await db.execute(select(CreditAccount).where(CreditAccount.project_id == project_id))).scalar_one_or_none()
    if acc:
        return acc
    acc = CreditAccount(project_id=project_id, balance=0)
    db.add(acc)
    await db.flush()
    return acc


async def ensure_sufficient_and_consume(
    *,
    db: AsyncSession,
    project_id: int,
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
    acc = await get_or_create_account(db, project_id)
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
    project_id: int,
    amount: int,
    ref_type: str,
    ref_id: str,
    note: str = "",
) -> None:
    """任务失败退款（V1：全额退款）。"""
    if amount <= 0:
        return
    acc = await get_or_create_account(db, project_id)
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


async def admin_adjust(
    *,
    db: AsyncSession,
    project_id: int,
    amount: int,
    note: str,
    ref_id: str = "",
) -> None:
    """管理员调账（V1 代替充值）。"""
    acc = await get_or_create_account(db, project_id)
    acc.balance += amount
    db.add(
        CreditTransaction(
            account_id=acc.id,
            tx_type=TxType.admin_adjust,
            amount=amount,
            ref_type="admin",
            ref_id=str(ref_id),
            note=note,
        )
    )


