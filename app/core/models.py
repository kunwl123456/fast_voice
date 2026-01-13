from __future__ import annotations

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.constants import (
    JobStatus,
    TxType,
    OrderType,
    PaymentType,
    PaymentStatus,
    PaymentProvider,
    OrderStatus,
)


def format_timezone() -> datetime:
    """返回 Asia/Shanghai 时区的当前时间（timezone-aware）"""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


class User(Base):
    """
    表：users
    用途：用户账号（登录/改名/改密码），直接拥有API Key、积分账户等资源。
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 主键（内部使用）
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )  # 对外唯一标识
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # 登录邮箱
    password_hash: Mapped[str] = mapped_column(String(255))  # bcrypt hash
    display_name: Mapped[str] = mapped_column(String(100), default="")  # 展示名
    avatar_url: Mapped[str] = mapped_column(String(512), default="")  # 头像链接
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # 管理员：可调账
    subscription_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscription_plans.id"),
        nullable=True,
        index=True,
    )  # 订阅计划ID（外键关联到 subscription_plans 表）
    subscription_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # 订阅到期时间（免费版为空）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )  # 创建时间

    # 关联关系
    subscription_plan: Mapped["SubscriptionPlanConfig | None"] = relationship(
        "SubscriptionPlanConfig", foreign_keys=[subscription_plan_id]
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user")
    credit_account: Mapped["CreditAccount"] = relationship(
        back_populates="user", uselist=False
    )
    voices: Mapped[list["Voice"]] = relationship(back_populates="owner")
    tts_jobs: Mapped[list["TTSJob"]] = relationship(back_populates="user")
    clone_jobs: Mapped[list["CloneJob"]] = relationship(back_populates="user")
    payments: Mapped[list["StripePayment"]] = relationship(
        "StripePayment", foreign_keys="StripePayment.user_id"
    )


class ApiKey(Base):
    """
    表：api_keys
    用途：OpenAPI 鉴权凭证（api_key 以 sk- 开头，直接用于 Bearer Token 鉴权）。
    直接关联到用户，企业版用户才能创建API Key。
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # 所属用户
    api_key: Mapped[str] = mapped_column(
        String(128), unique=True, index=True
    )  # API Key（以 sk- 开头，用于 Bearer Token）
    name: Mapped[str] = mapped_column(String(100), default="")  # 密钥名称（用于展示）
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否启用
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # 有效期（为空表示永久有效）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )

    user: Mapped["User"] = relationship(back_populates="api_keys")


class CreditAccount(Base):
    """
    表：credit_accounts
    用途：用户积分账户（余额）。
    """

    __tablename__ = "credit_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True
    )  # 1 user : 1 account
    balance: Mapped[int] = mapped_column(Integer, default=0)  # 当前余额（积分）
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )  # 最近更新时间

    user: Mapped["User"] = relationship(back_populates="credit_account")
    transactions: Mapped[list["CreditTransaction"]] = relationship(
        back_populates="account"
    )


class CreditTransaction(Base):
    """
    表：credit_transactions
    用途：积分流水（记账/对账/追踪扣费原因）。
    """

    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("credit_accounts.id"), index=True
    )  # 归属账户
    tx_type: Mapped[TxType] = mapped_column(
        Enum(TxType, name="tx_type"), index=True
    )  # 类型
    amount: Mapped[int] = mapped_column(Integer)  # + 入账 / - 扣费
    ref_type: Mapped[str] = mapped_column(
        String(50), default=""
    )  # 关联对象类型（tts/clone/admin）
    ref_id: Mapped[str] = mapped_column(
        String(100), default=""
    )  # 关联对象 id（job id）
    note: Mapped[str] = mapped_column(String(255), default="")  # 备注
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )

    account: Mapped["CreditAccount"] = relationship(back_populates="transactions")


class Voice(Base):
    """
    表：voices
    用途：音色实体（克隆结果）。公开音色即进入"声音大厅"。
    """

    __tablename__ = "voices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )  # 对外唯一标识
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True
    )  # 拥有者（用户）
    name: Mapped[str] = mapped_column(String(120))  # 音色名称
    avatar_url: Mapped[str] = mapped_column(String(512), default="")  # 音色头像
    description: Mapped[str] = mapped_column(String(500), default="")  # 描述
    tags: Mapped[list[str]] = mapped_column(
        JSONB, default=list
    )  # 标签列表（使用JSONB支持高效查询）
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True
    )  # 是否公开
    preview_audio_path: Mapped[str] = mapped_column(
        String(255), default=""
    )  # 本地预览音频路径
    clone_job_uuid: Mapped[str] = mapped_column(
        String(36), default="", index=True
    )  # 来源克隆任务的 UUID（用于追溯来源）
    likes_count: Mapped[int] = mapped_column(Integer, default=0, index=True)  # 点赞数
    generated_chars_count: Mapped[int] = mapped_column(
        Integer, default=0
    )  # 生成字符数（累计）
    usage_count: Mapped[int] = mapped_column(
        Integer, default=0, index=True
    )  # 使用次数（TTS任务成功次数）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )

    owner: Mapped["User"] = relationship(back_populates="voices")


class TTSJob(Base):
    """
    表：tts_jobs
    用途：TTS 合成任务（异步队列）。创建时预扣积分，失败自动退款。
    """

    __tablename__ = "tts_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )  # 对外暴露的唯一标识
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True
    )  # 调用方（用户）
    voice_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("voices.uuid"), index=True
    )  # 使用的音色 UUID
    text: Mapped[str] = mapped_column(Text)  # 输入文本
    text_utf8_bytes: Mapped[int] = mapped_column(
        Integer
    )  # 输入文本 UTF-8 字节数（计费依据）
    cost_credits: Mapped[int] = mapped_column(Integer)  # 扣费积分（= bytes * price）
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)  # 任务标签列表
    speed_factor: Mapped[float] = mapped_column(Float, default=1.0)  # 语速
    temperature: Mapped[float] = mapped_column(Float, default=1.0)  # 采样温度
    top_k: Mapped[int] = mapped_column(Integer, default=5)  # 采样 top_k
    top_p: Mapped[float] = mapped_column(Float, default=1.0)  # 采样 top_p
    webhook_url: Mapped[str] = mapped_column(
        String(512), default=""
    )  # Webhook 回调地址（任务完成时调用）
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.queued, index=True
    )
    error: Mapped[str] = mapped_column(String(255), default="")  # 错误码（失败时）
    output_audio_path: Mapped[str] = mapped_column(
        String(255), default=""
    )  # 产出音频本地路径
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )

    user: Mapped["User"] = relationship(back_populates="tts_jobs")


class CloneJob(Base):
    """
    表：clone_jobs
    用途：音色克隆任务（异步队列）。成功后产出 Voice（result_voice_id）。
    """

    __tablename__ = "clone_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )  # 对外暴露的唯一标识
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True
    )  # 调用方（用户）
    voice_name: Mapped[str] = mapped_column(String(120))  # 目标音色名
    avatar_url: Mapped[str] = mapped_column(String(512), default="")  # 音频特征头像
    description: Mapped[str] = mapped_column(String(500), default="")  # 音频特征描述
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)  # 标签列表
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # 产出音色是否公开
    remove_background_noise: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # 是否去除背景音
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.queued, index=True
    )
    error: Mapped[str] = mapped_column(String(255), default="")
    dataset_dir: Mapped[str] = mapped_column(
        String(255), default=""
    )  # 本地数据集目录（上传文件落这里）
    result_voice_uuid: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )  # 成功后生成的音色 UUID（关联 voices.uuid）
    external_request_id: Mapped[str] = mapped_column(
        String(64), default=""
    )  # 外部语音服务请求ID（如 uuid）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )

    user: Mapped["User"] = relationship(back_populates="clone_jobs")


class ApiRequestLog(Base):
    """
    表：api_request_logs
    用途：记录API请求日志，用于Dashboard展示和分析。
    """

    __tablename__ = "api_request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # 调用用户
    api_key_id: Mapped[int] = mapped_column(
        ForeignKey("api_keys.id"), index=True
    )  # 使用的API Key
    endpoint: Mapped[str] = mapped_column(String(255))  # 请求端点，如 /v1/completions
    method: Mapped[str] = mapped_column(String(10))  # HTTP方法：GET/POST/PUT/DELETE
    status_code: Mapped[int] = mapped_column(Integer, index=True)  # HTTP状态码
    latency_ms: Mapped[int] = mapped_column(Integer)  # 请求延迟（毫秒）
    response_size: Mapped[int] = mapped_column(Integer, default=0)  # 响应大小（字节）
    error_message: Mapped[str] = mapped_column(String(255), default="")  # 错误信息
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone, index=True
    )


class InviteCode(Base):
    """
    表：invite_codes
    用途：邀请码管理（邀请制注册）。
    """

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(
        String(32), unique=True, index=True
    )  # 邀请码（唯一）
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True
    )  # 创建者（管理员）
    used_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )  # 使用者（注册用户）
    is_used: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True
    )  # 是否已使用
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # 过期时间（null 表示永久有效）
    note: Mapped[str] = mapped_column(String(255), default="")  # 备注说明
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # 使用时间


class SubscriptionPlanConfig(Base):
    """
    表：subscription_plans
    用途：订阅计划配置（从代码常量落库，供计费/展示/运营使用）
    """

    __tablename__ = "subscription_plans"
    __table_args__ = (
        UniqueConstraint("plan_code", name="uq_subscription_plans_plan_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 自增主键

    plan_code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )  # 计划编码：free/pro/enterprise（对外稳定标识）
    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )  # 展示名（如：免费版/专业版/企业版）

    monthly_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )  # 每月赠送积分（>=0）
    monthly_quota: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )  # 每月请求配额（次数，>=0）
    clone_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )  # 克隆位上限：-1=无限，否则>=0

    api_access: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )  # 是否允许 API 访问
    commercial_use: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )  # 是否允许商业使用
    priority_support: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )  # 是否享受优先支持

    monthly_price: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )  # 月价（整数）
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="CNY",
    )  # ISO 4217 货币代码（默认 CNY）

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )  # 是否启用（下架但保留历史用）

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=format_timezone,
    )  # 创建时间（Asia/Shanghai）
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=format_timezone,
    )  # 更新时间（更新时自动刷新）


class Order(Base):
    """
    表：orders
    用途：业务订单（连接前端与支付中台）
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_no: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )  # 对外唯一标识（业务订单号）
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )  # 用户ID

    # 订单基本信息
    order_type: Mapped[OrderType] = mapped_column(
        Enum(OrderType, name="order_type"), index=True
    )  # 订单类型
    product_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("subscription_plans.id"),
        nullable=True,
        index=True,
    )  # 商品ID（外键：subscription_plans.id；积分充值订单为空，真实商品编码见 extra_metadata）
    quantity: Mapped[int] = mapped_column(Integer, default=1)  # 数量
    amount: Mapped[float] = mapped_column(Float)  # 应付金额
    currency: Mapped[str] = mapped_column(String(3), default="USD")  # 货币类型

    # 订单状态
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"),
        default=OrderStatus.pending,
        index=True,
    )  # 订单状态

    # 业务相关字段
    payment_id: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True
    )  # 支付网关订单号
    payment_method: Mapped[PaymentProvider | None] = mapped_column(
        Enum(PaymentProvider, name="payment_provider"),
        nullable=True,
    )  # 支付渠道
    return_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )  # 支付完成跳转URL
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # 额外的元数据

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )  # 创建时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone, onupdate=format_timezone
    )  # 更新时间
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # 支付时间
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # 订单过期时间

    # 关联关系
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    subscription_plan_config: Mapped["SubscriptionPlanConfig | None"] = relationship(
        "SubscriptionPlanConfig",
        foreign_keys=[product_id],
    )


# ============================================================================


class StripePayment(Base):
    """
    表：stripe_payments
    用途：记录 Stripe 支付订单和状态
    """

    __tablename__ = "stripe_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )  # 对外唯一标识
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )  # 用户ID
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="payment_type"), index=True
    )  # 支付类型
    amount: Mapped[float] = mapped_column(Float)  # 支付金额（美元）
    currency: Mapped[str] = mapped_column(String(3), default="usd")  # 货币类型
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.pending,
        index=True,
    )  # 支付状态

    # Stripe 相关字段
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )  # Stripe PaymentIntent ID
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), index=True, nullable=True
    )  # Stripe Customer ID
    client_secret: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )  # 客户端密钥（用于前端确认支付）

    # 业务相关字段
    credits_amount: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 充值的积分数量（仅用于积分充值）
    subscription_plan: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # 订阅计划代码（仅用于订阅支付，存储 plan_code）
    subscription_months: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 订阅月数（仅用于订阅支付）

    # 元数据
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # 额外的元数据
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # 错误信息（支付失败时）

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )  # 创建时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone, onupdate=format_timezone
    )  # 更新时间
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # 完成时间（支付成功或失败时）

    # 关联关系
    user: Mapped["User"] = relationship(
        "User", foreign_keys=[user_id], overlaps="payments"
    )


class StripeWebhookEvent(Base):
    """
    表：stripe_webhook_events
    用途：记录 Stripe Webhook 事件，防止重复处理
    """

    __tablename__ = "stripe_webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True
    )  # Stripe Event ID
    event_type: Mapped[str] = mapped_column(String(100), index=True)  # 事件类型
    payload: Mapped[dict] = mapped_column(JSONB)  # 完整的事件数据
    processed: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True
    )  # 是否已处理
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # 处理时间
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # 处理错误信息
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )  # 创建时间


# ============================================================================
