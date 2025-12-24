from __future__ import annotations

import enum
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def format_timezone() -> datetime:
    """返回 Asia/Shanghai 时区的当前时间（timezone-aware）"""
    return datetime.now(ZoneInfo("Asia/Shanghai"))


class JobStatus(str, enum.Enum):
    """异步任务状态机（TTS/克隆共用）。"""

    queued = "queued"  # 已入队等待 worker
    running = "running"  # worker 正在处理
    succeeded = "succeeded"  # 成功产出结果
    failed = "failed"  # 失败（并触发退款/记录错误）


class TxType(str, enum.Enum):
    """积分流水类型。"""

    recharge = "recharge"  # 充值
    consume = "consume"  # 消费（创建任务时预扣）
    refund = "refund"  # 退款（任务失败自动回滚）
    subscription = "subscription"  # 订阅赠送


class SubscriptionPlan(str, enum.Enum):
    """订阅计划类型。"""

    free = "free"  # 免费版：每月少量积分
    pro = "pro"  # 专业版：每月一定量积分、商业使用权
    enterprise = "enterprise"  # 企业版：无限克隆位、大量积分、API访问


class User(Base):
    """
    表：users
    用途：用户账号（登录/改名/改密码），直接拥有API Key、积分账户等资源。
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 主键
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # 登录邮箱
    password_hash: Mapped[str] = mapped_column(String(255))  # bcrypt hash
    display_name: Mapped[str] = mapped_column(String(100), default="")  # 展示名
    avatar_url: Mapped[str] = mapped_column(String(512), default="")  # 头像链接
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # 管理员：可调账
    subscription_plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(SubscriptionPlan, name="subscription_plan"),
        default=SubscriptionPlan.free,
        index=True,
    )  # 订阅计划
    subscription_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # 订阅到期时间（免费版为空）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=format_timezone
    )  # 创建时间

    # 关联关系
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user")
    credit_account: Mapped["CreditAccount"] = relationship(
        back_populates="user", uselist=False
    )
    voices: Mapped[list["Voice"]] = relationship(back_populates="owner")
    tts_jobs: Mapped[list["TTSJob"]] = relationship(back_populates="user")
    clone_jobs: Mapped[list["CloneJob"]] = relationship(back_populates="user")


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
    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_voice_owner_name"),
    )

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
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)  # 标签列表
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True
    )  # 是否公开
    preview_audio_path: Mapped[str] = mapped_column(
        String(255), default=""
    )  # 本地预览音频路径
    clone_job_uuid: Mapped[str] = mapped_column(
        String(36), default="", index=True
    )  # 来源克隆任务的 UUID（用于追溯来源）
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
    webhook_url: Mapped[str] = mapped_column(String(512), default="")  # Webhook 回调地址（任务完成时调用）
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="job_status"), default=JobStatus.queued, index=True)
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
    remove_background_noise: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否去除背景音
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
