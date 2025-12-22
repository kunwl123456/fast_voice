from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import CreditAccount, CreditTransaction, TxType


def utf8_bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def calc_cost(text: str) -> int:
    return utf8_bytes(text) * int(settings.credit_price_per_utf8_byte)


def get_or_create_account(db: Session, project_id: int) -> CreditAccount:
    acc = db.execute(select(CreditAccount).where(CreditAccount.project_id == project_id)).scalar_one_or_none()
    if acc:
        return acc
    acc = CreditAccount(project_id=project_id, balance=0)
    db.add(acc)
    db.flush()
    return acc


def refund(*, db: Session, project_id: int, amount: int, ref_type: str, ref_id: str, note: str = "") -> None:
    if amount <= 0:
        return
    acc = get_or_create_account(db, project_id)
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


