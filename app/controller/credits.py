"""积分管理业务逻辑"""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CreditTransaction, User
from app.services.billing import get_or_create_account, recharge
from app.schemas import CreditAccountOut, CreditTxOut


async def get_user_credit_balance(db: AsyncSession, user: User) -> CreditAccountOut:
    """
    获取用户的积分余额

    ### 参数
    - db: 数据库会话
    - user: 用户对象

    ### 返回
    - 积分账户信息
    """
    acc = await get_or_create_account(db, user.id)
    return CreditAccountOut(user_id=user.uuid, balance=acc.balance)


async def get_user_credit_transactions(
    db: AsyncSession, user: User
) -> list[CreditTxOut]:
    """
    获取用户的积分交易记录

    ### 参数
    - db: 数据库会话
    - user: 用户对象

    ### 返回
    - 积分交易记录列表（最多 200 条）
    """
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

    return [
        CreditTxOut(
            id=t.id,
            tx_type=t.tx_type.value,
            amount=t.amount,
            ref_type=t.ref_type,
            ref_id=t.ref_id,
            note=t.note,
            created_at=t.created_at,
        )
        for t in txs
    ]


async def recharge_user_credits(
    db: AsyncSession, user_uuid: str, amount: int, note: str
) -> tuple[User | None, dict | None]:
    """
    管理员为用户充值积分

    ### 参数
    - db: 数据库会话
    - user_uuid: 目标用户的 UUID
    - amount: 充值金额
    - note: 备注说明

    ### 返回
    - (用户对象, 充值结果字典)，如果用户不存在则返回 (None, None)
    """
    recharge_user = (
        await db.execute(select(User).where(User.uuid == user_uuid))
    ).scalar_one_or_none()

    if not recharge_user:
        return None, None

    await recharge(db=db, user_id=recharge_user.id, amount=amount, note=note)

    return recharge_user, {"user_id": user_uuid, "amount": amount}
