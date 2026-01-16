"""积分管理业务逻辑"""

from __future__ import annotations


from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.controller.orders import create_order
from app.api.services.billing import get_or_create_account
from app.core.error_codes import CreditError
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.models import CreditTransaction, User, CreditPackage
from app.core.schemas import (
    CreditAccountOut,
    CreditTxOut,
    CreditPackageOut,
    BuyCreditIn,
    BuyCreditOut,
    CreateOrderIn,
)
from app.core.constants import (
    OrderType,
    PaymentProvider,
    Currency,
)


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


async def list_credit_packages(db: AsyncSession) -> list[CreditPackageOut]:
    """
    获取可用的积分充值档位列表
    """
    result = await db.execute(
        select(CreditPackage)
        .where(CreditPackage.is_active.is_(True))
        .order_by(CreditPackage.price.asc(), CreditPackage.credits.asc())
    )
    packages = result.scalars().all()
    return [
        CreditPackageOut(
            code=p.code,
            name=p.name,
            credits=p.credits,
            currency=p.currency,
            price=p.price,
            is_active=p.is_active,
        )
        for p in packages
    ]


async def buy_credits(
    db: AsyncSession, user: User, payload: BuyCreditIn
) -> BuyCreditOut:
    """
    创建积分购买订单并返回支付信息
    """
    all_pay_types = list(PaymentProvider.__members__.keys())
    if payload.pay_type not in all_pay_types:
        raise BadRequestException(
            error=CreditError.INVALID_PAY_TYPE,
            data={"valid_pay_types": all_pay_types},
        )

    # 防御性校验：理论上已由 Pydantic 校验（ge=1），但这里保证错误码一一对应
    quantity = int(payload.quantity or 1)
    if quantity <= 0:
        raise BadRequestException(
            error=CreditError.INVALID_QUANTITY,
            data={"quantity": payload.quantity},
        )

    # 查找档位
    result = await db.execute(
        select(CreditPackage).where(
            CreditPackage.code == payload.package_code,
            CreditPackage.is_active.is_(True),
        )
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise NotFoundException(
            error=CreditError.CREDIT_PACKAGE_NOT_FOUND,
            message="积分档位不存在或已下架",
            data={"package_code": payload.package_code},
        )

    total_price = int(pkg.price) * quantity
    total_credits = int(pkg.credits) * quantity
    extra_metadata = {
        "credit_package_code": pkg.code,
        "credit_package_name": pkg.name,
        "credits_per_unit": int(pkg.credits),
        "quantity": quantity,
        "credits_total": total_credits,
        "unit_price": int(pkg.price),
        "total_price": total_price,
        "currency": pkg.currency,
        "product_name": pkg.name,
    }
    res = await create_order(
        db,
        user,
        CreateOrderIn(
            order_type=OrderType.credit_recharge,
            currency=Currency(pkg.currency),
            quantity=quantity,
            product_id=pkg.id,
            product_name=pkg.name,
            unit_price=pkg.price,
            payment_method=payload.pay_type,
            extra_metadata=extra_metadata,
        ),
    )
    return BuyCreditOut(
        package_code=pkg.code,
        name=pkg.name,
        pay_type=payload.pay_type,
        credits=total_credits,
        currency=pkg.currency,
        price=total_price,
        extra=res.extra,
        expires_at=res.expires_at,
    )
