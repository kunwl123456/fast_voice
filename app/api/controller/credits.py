"""积分管理业务逻辑"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import CreditTransaction, User, CreditPackage, Order
from app.core.schemas import (
    CreditAccountOut,
    CreditTxOut,
    CreditPackageOut,
    BuyCreditIn,
    BuyCreditOut,
)
from app.api.services.billing import get_or_create_account
from app.api.services.payment_gateway_client import (
    get_payment_gateway_client,
    PaymentGatewayError,
)
from app.core.constants import (
    OrderType,
    OrderStatus,
    PaymentProvider,
    ORDER_EXPIRE_MINUTES,
)
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.error_codes import CreditError, PaymentError
from app.core.config import settings
from app.tools.common import tz_now


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
    payment_method = payload.pay_type or PaymentProvider.alipay

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

    expires_at = tz_now() + timedelta(minutes=ORDER_EXPIRE_MINUTES)

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

    # 创建订单
    order = Order(
        user_id=user.id,
        order_type=OrderType.credit_recharge,
        product_id=None,
        quantity=quantity,
        amount=total_price,
        currency=pkg.currency,
        status=OrderStatus.pending,
        payment_method=payment_method,
        expires_at=expires_at,
        extra_metadata=extra_metadata,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)

    # 创建支付
    try:
        try:
            payment_client = get_payment_gateway_client()
        except ValueError as e:
            # 支付网关配置缺失/不合法
            order.status = OrderStatus.failed
            em = order.extra_metadata or {}
            em["error_message"] = str(e)
            order.extra_metadata = em
            await db.commit()
            raise BadRequestException(
                error=PaymentError.PAYMENT_GATEWAY_CONFIG_ERROR,
                message=str(e),
            )

        payment_result = await payment_client.create_payment(
            merchant_order_no=order.order_no,
            provider=str(payment_method.value),
            currency=pkg.currency,
            quantity=quantity,
            unit_amount=int(pkg.price),
            product_name=pkg.name,
            product_desc=f"用户 {user.email} 购买 {pkg.name}（{total_credits}积分）",
            notify_url=settings.payment_callback_url,
            expire_minutes=ORDER_EXPIRE_MINUTES,
            success_url=settings.payment_success_url,
            cancel_url=settings.payment_cancel_url,
            metadata={
                "customer_name": user.display_name,
                "customer_email": user.email,
                "merchant_order_no": order.order_no,
                "package_code": pkg.code,
                "credits_total": str(total_credits),
            },
        )
        order.payment_id = str(payment_result.payment_id)
    except PaymentGatewayError as e:
        order.status = OrderStatus.failed
        em = order.extra_metadata or {}
        em["error_message"] = e.message
        em["gateway_error_code"] = e.code
        order.extra_metadata = em
        await db.commit()
        raise BadRequestException(
            error=PaymentError.CREATE_PAYMENT_FAILED,
            message=e.message,
            data={"gateway_error_code": e.code},
        )
    except Exception as e:
        order.status = OrderStatus.failed
        em = order.extra_metadata or {}
        em["error_message"] = str(e)
        order.extra_metadata = em
        await db.commit()
        raise BadRequestException(
            error=PaymentError.CREATE_PAYMENT_FAILED,
            message=str(e),
        )

    await db.commit()
    await db.refresh(order)

    return BuyCreditOut(
        package_code=pkg.code,
        name=pkg.name,
        pay_type=str(payment_method.value),
        credits=total_credits,
        currency=pkg.currency,
        price=total_price,
        extra=payment_result.payload,
        expires_at=order.expires_at,
    )
