"""
Stripe 支付服务

提供 Stripe 支付相关的核心功能：
- 创建支付意图（PaymentIntent）
- 查询支付状态
- 处理支付成功后的业务逻辑（积分充值、订阅升级）
"""

from __future__ import annotations

import stripe
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.models import (
    StripePayment,
    StripeWebhookEvent,
    PaymentStatus,
    PaymentType,
    User,
    CreditAccount,
    CreditTransaction,
    TxType,
    SubscriptionPlan,
)
from app.core.exceptions import BadRequestException, NotFoundException

# 初始化 Stripe
if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key


class StripeService:
    """Stripe 支付服务类"""

    @staticmethod
    async def create_payment_intent(
        db: AsyncSession,
        user: User,
        payment_type: str,
        amount: float,
        currency: str | None = None,
        payment_method: str | None = None,
        credits_amount: int | None = None,
        subscription_plan: str | None = None,
        subscription_months: int | None = None,
    ) -> tuple[StripePayment, str]:
        """
        创建 Stripe PaymentIntent

        Args:
            db: 数据库会话
            user: 用户对象
            payment_type: 支付类型（credit_recharge 或 subscription）
            amount: 支付金额
            currency: 货币类型，不指定则根据支付方式自动选择
            payment_method: 支付方式
            credits_amount: 充值的积分数量（仅用于积分充值）
            subscription_plan: 订阅计划（仅用于订阅支付）
            subscription_months: 订阅月数（仅用于订阅支付）

        Returns:
            (StripePayment对象, client_secret)
        """
        if not settings.stripe_secret_key:
            raise BadRequestException("Stripe 支付未配置")

        # 验证支付类型
        try:
            payment_type_enum = PaymentType(payment_type)
        except ValueError:
            raise BadRequestException(f"无效的支付类型: {payment_type}")

        # 验证参数
        if payment_type_enum == PaymentType.credit_recharge:
            if not credits_amount or credits_amount <= 0:
                raise BadRequestException("积分充值必须指定有效的积分数量")
        elif payment_type_enum == PaymentType.subscription:
            if not subscription_plan or not subscription_months:
                raise BadRequestException("订阅支付必须指定订阅计划和月数")
            try:
                SubscriptionPlan(subscription_plan)
            except ValueError:
                raise BadRequestException(f"无效的订阅计划: {subscription_plan}")
            if subscription_months < 1 or subscription_months > 12:
                raise BadRequestException("订阅月数必须在 1-12 之间")

        # 创建或获取 Stripe Customer
        customer_id = await StripeService._get_or_create_customer(user)

        # 自动选择货币
        if not currency:
            # 根据支付方式自动选择货币
            if payment_method in ["alipay", "wechat_pay"]:
                currency = "cny"  # 支付宝和微信支付默认使用人民币
                logger.info(f"支付方式 {payment_method} 自动选择货币: CNY")
            else:
                currency = "usd"  # 其他支付方式默认使用美元
                logger.info(f"支付方式 {payment_method or '自动'} 默认使用货币: USD")
        else:
            currency = currency.lower()
            logger.info(f"使用指定货币: {currency.upper()}")

        # 创建 PaymentIntent
        try:
            # 根据是否指定支付方式，使用不同的配置
            payment_intent_params = {
                "amount": int(amount * 100),  # Stripe 使用分为单位
                "currency": currency,
                "customer": customer_id,
                "metadata": {
                    "user_id": user.id,
                    "user_email": user.email,
                    "payment_type": payment_type,
                    "credits_amount": credits_amount if credits_amount else "",
                    "subscription_plan": subscription_plan if subscription_plan else "",
                    "subscription_months": subscription_months if subscription_months else "",
                },
            }
            
            # 如果明确指定了支付方式，使用 payment_method_types
            if payment_method:
                payment_intent_params["payment_method_types"] = [payment_method]
                logger.info(f"创建支付订单，指定支付方式: {payment_method}")
            else:
                # 否则使用自动支付方式（支持所有已启用的支付方式）
                payment_intent_params["automatic_payment_methods"] = {
                    "enabled": True,
                    "allow_redirects": "always"  # 允许重定向支付方式（支付宝、微信等）
                }
                logger.info("创建支付订单，使用自动支付方式")
            
            payment_intent = stripe.PaymentIntent.create(**payment_intent_params)
        except stripe.error.StripeError as e:
            logger.error(f"创建 Stripe PaymentIntent 失败: {e}")
            raise BadRequestException(f"创建支付失败: {str(e)}")

        # 创建支付记录
        payment = StripePayment(
            user_id=user.id,
            payment_type=payment_type_enum,
            amount=amount,
            currency=currency,
            status=PaymentStatus.pending,
            stripe_payment_intent_id=payment_intent.id,
            stripe_customer_id=customer_id,
            client_secret=payment_intent.client_secret,
            credits_amount=credits_amount,
            subscription_plan=SubscriptionPlan(subscription_plan)
            if subscription_plan
            else None,
            subscription_months=subscription_months,
            extra_metadata={"payment_intent": payment_intent.id},
        )

        db.add(payment)
        await db.commit()
        await db.refresh(payment)

        logger.info(
            f"创建支付订单成功: payment_id={payment.uuid}, user_id={user.id}, amount=${amount}"
        )

        return payment, payment_intent.client_secret

    @staticmethod
    async def _get_or_create_customer(user: User) -> str:
        """
        获取或创建 Stripe Customer

        Args:
            user: 用户对象

        Returns:
            Stripe Customer ID
        """
        # 这里可以在 User 模型中添加 stripe_customer_id 字段来缓存
        # 为了简化，每次都创建新的 Customer（实际应用中应该缓存）
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.display_name or user.email,
                metadata={"user_id": user.id, "user_uuid": user.uuid},
            )
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"创建 Stripe Customer 失败: {e}")
            raise BadRequestException(f"创建客户信息失败: {str(e)}")

    @staticmethod
    async def get_payment_by_uuid(
        db: AsyncSession, payment_uuid: str
    ) -> StripePayment:
        """
        根据 UUID 获取支付记录

        Args:
            db: 数据库会话
            payment_uuid: 支付订单UUID

        Returns:
            StripePayment对象
        """
        result = await db.execute(
            select(StripePayment).where(StripePayment.uuid == payment_uuid)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            raise NotFoundException("支付订单不存在")

        return payment

    @staticmethod
    async def get_payment_by_intent_id(
        db: AsyncSession, intent_id: str
    ) -> StripePayment | None:
        """
        根据 Stripe PaymentIntent ID 获取支付记录

        Args:
            db: 数据库会话
            intent_id: Stripe PaymentIntent ID

        Returns:
            StripePayment对象或None
        """
        result = await db.execute(
            select(StripePayment).where(
                StripePayment.stripe_payment_intent_id == intent_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_payments(
        db: AsyncSession, user_id: int, limit: int = 50
    ) -> list[StripePayment]:
        """
        获取用户的支付历史

        Args:
            db: 数据库会话
            user_id: 用户ID
            limit: 返回记录数量限制

        Returns:
            支付记录列表
        """
        result = await db.execute(
            select(StripePayment)
            .where(StripePayment.user_id == user_id)
            .order_by(StripePayment.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def handle_payment_succeeded(
        db: AsyncSession, payment_intent_id: str
    ) -> None:
        """
        处理支付成功事件

        Args:
            db: 数据库会话
            payment_intent_id: Stripe PaymentIntent ID
        """
        # 获取支付记录
        payment = await StripeService.get_payment_by_intent_id(db, payment_intent_id)
        if not payment:
            logger.warning(f"未找到支付记录: payment_intent_id={payment_intent_id}")
            return

        # 如果已经处理过，跳过
        if payment.status == PaymentStatus.succeeded:
            logger.info(f"支付已处理过: payment_id={payment.uuid}")
            return

        # 更新支付状态
        payment.status = PaymentStatus.succeeded
        payment.completed_at = datetime.now()

        # 根据支付类型处理业务逻辑
        if payment.payment_type == PaymentType.credit_recharge:
            await StripeService._handle_credit_recharge(db, payment)
        elif payment.payment_type == PaymentType.subscription:
            await StripeService._handle_subscription_payment(db, payment)

        await db.commit()

        logger.info(
            f"支付成功处理完成: payment_id={payment.uuid}, type={payment.payment_type.value}"
        )

    @staticmethod
    async def _handle_credit_recharge(
        db: AsyncSession, payment: StripePayment
    ) -> None:
        """
        处理积分充值

        Args:
            db: 数据库会话
            payment: 支付记录
        """
        if not payment.credits_amount:
            logger.error(f"积分充值订单缺少积分数量: payment_id={payment.uuid}")
            return

        # 获取用户的积分账户
        result = await db.execute(
            select(CreditAccount).where(CreditAccount.user_id == payment.user_id)
        )
        credit_account = result.scalar_one_or_none()

        if not credit_account:
            logger.error(f"用户积分账户不存在: user_id={payment.user_id}")
            return

        # 增加积分
        credit_account.balance += payment.credits_amount

        # 创建积分流水
        transaction = CreditTransaction(
            user_id=payment.user_id,
            tx_type=TxType.recharge,
            amount=payment.credits_amount,
            balance_after=credit_account.balance,
            description=f"Stripe 充值 ${payment.amount:.2f}",
            metadata={"payment_id": payment.uuid, "stripe_intent_id": payment.stripe_payment_intent_id},
        )

        db.add(transaction)

        logger.info(
            f"积分充值成功: user_id={payment.user_id}, credits={payment.credits_amount}"
        )

    @staticmethod
    async def _handle_subscription_payment(
        db: AsyncSession, payment: StripePayment
    ) -> None:
        """
        处理订阅支付

        Args:
            db: 数据库会话
            payment: 支付记录
        """
        if not payment.subscription_plan or not payment.subscription_months:
            logger.error(f"订阅支付订单缺少订阅信息: payment_id={payment.uuid}")
            return

        # 获取用户
        result = await db.execute(select(User).where(User.id == payment.user_id))
        user = result.scalar_one_or_none()

        if not user:
            logger.error(f"用户不存在: user_id={payment.user_id}")
            return

        # 更新订阅计划
        user.subscription_plan = payment.subscription_plan

        # 计算订阅到期时间
        now = datetime.now()
        if user.subscription_ends_at and user.subscription_ends_at > now:
            # 如果当前订阅未过期，在原有基础上延长
            new_end_time = user.subscription_ends_at + timedelta(
                days=30 * payment.subscription_months
            )
        else:
            # 如果当前订阅已过期或没有订阅，从现在开始计算
            new_end_time = now + timedelta(days=30 * payment.subscription_months)

        user.subscription_ends_at = new_end_time

        logger.info(
            f"订阅升级成功: user_id={payment.user_id}, plan={payment.subscription_plan.value}, "
            f"months={payment.subscription_months}, ends_at={new_end_time}"
        )

    @staticmethod
    async def handle_payment_failed(db: AsyncSession, payment_intent_id: str) -> None:
        """
        处理支付失败事件

        Args:
            db: 数据库会话
            payment_intent_id: Stripe PaymentIntent ID
        """
        payment = await StripeService.get_payment_by_intent_id(db, payment_intent_id)
        if not payment:
            logger.warning(f"未找到支付记录: payment_intent_id={payment_intent_id}")
            return

        # 更新支付状态
        payment.status = PaymentStatus.failed
        payment.completed_at = datetime.now()
        payment.error_message = "支付失败"

        await db.commit()

        logger.info(f"支付失败: payment_id={payment.uuid}")

    @staticmethod
    async def record_webhook_event(
        db: AsyncSession, event_id: str, event_type: str, payload: dict
    ) -> bool:
        """
        记录 Webhook 事件（防止重复处理）

        Args:
            db: 数据库会话
            event_id: Stripe Event ID
            event_type: 事件类型
            payload: 事件数据

        Returns:
            是否是新事件（True=新事件，False=已处理过）
        """
        # 检查事件是否已存在
        result = await db.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == event_id)
        )
        existing_event = result.scalar_one_or_none()

        if existing_event:
            logger.info(f"Webhook 事件已处理过: event_id={event_id}")
            return False

        # 创建新的事件记录
        webhook_event = StripeWebhookEvent(
            event_id=event_id, event_type=event_type, payload=payload, processed=True
        )

        db.add(webhook_event)
        await db.commit()

        logger.info(f"记录 Webhook 事件: event_id={event_id}, type={event_type}")
        return True

