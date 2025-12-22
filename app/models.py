from __future__ import annotations

import enum
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
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


class User(Base):
    """
    表：users
    用途：Console 用户账号（登录/改名/改密码），并拥有一个或多个 Project。
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 主键
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # 登录邮箱
    password_hash: Mapped[str] = mapped_column(String(255))  # bcrypt hash
    display_name: Mapped[str] = mapped_column(String(100), default="")  # 展示名
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # 管理员：可调账
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=format_timezone)  # 创建时间

    projects: Mapped[list["Project"]] = relationship(back_populates="owner")  # 拥有的项目


class Project(Base):
    """
    表：projects
    用途：OpenAPI 的调用主体（B 端按 project 计费/限流/额度）。
    V1：默认每个用户一个 default project。
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # 所属用户
    name: Mapped[str] = mapped_column(String(120), default="default")  # 项目名
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=format_timezone)

    owner: Mapped["User"] = relationship(back_populates="projects")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="project")
    credit_account: Mapped["CreditAccount"] = relationship(back_populates="project", uselist=False)


class ApiKey(Base):
    """
    表：api_keys
    用途：OpenAPI 鉴权凭证（api_key 公开，api_secret 仅用于签名，服务端加密存储）。
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    api_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)  # 公开 key（请求头 X-API-Key）
    api_secret_ciphertext: Mapped[str] = mapped_column(Text)  # Fernet 加密后的 secret
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否启用
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=format_timezone)

    project: Mapped["Project"] = relationship(back_populates="api_keys")


class CreditAccount(Base):
    """
    表：credit_accounts
    用途：项目积分账户（余额）。
    """

    __tablename__ = "credit_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), unique=True, index=True)  # 1 project : 1 account
    balance: Mapped[int] = mapped_column(Integer, default=0)  # 当前余额（积分）
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=format_timezone)  # 最近更新时间

    project: Mapped["Project"] = relationship(back_populates="credit_account")
    transactions: Mapped[list["CreditTransaction"]] = relationship(back_populates="account")


class CreditTransaction(Base):
    """
    表：credit_transactions
    用途：积分流水（记账/对账/追踪扣费原因）。
    """

    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("credit_accounts.id"), index=True)  # 归属账户
    tx_type: Mapped[TxType] = mapped_column(Enum(TxType), index=True)  # 类型
    amount: Mapped[int] = mapped_column(Integer)  # + 入账 / - 扣费
    ref_type: Mapped[str] = mapped_column(String(50), default="")  # 关联对象类型（tts/clone/admin）
    ref_id: Mapped[str] = mapped_column(String(100), default="")  # 关联对象 id（job id）
    note: Mapped[str] = mapped_column(String(255), default="")  # 备注
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=format_timezone)

    account: Mapped["CreditAccount"] = relationship(back_populates="transactions")


class Voice(Base):
    """
    表：voices
    用途：音色实体（克隆结果）。公开音色即进入“声音大厅”。
    """

    __tablename__ = "voices"
    __table_args__ = (UniqueConstraint("owner_project_id", "name", name="uq_voice_owner_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)  # 拥有者（project）
    name: Mapped[str] = mapped_column(String(120))  # 音色名称
    description: Mapped[str] = mapped_column(String(255), default="")  # 描述
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)  # 是否公开
    preview_audio_path: Mapped[str] = mapped_column(String(255), default="")  # 本地预览音频路径
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=format_timezone)


class TTSJob(Base):
    """
    表：tts_jobs
    用途：TTS 合成任务（异步队列）。创建时预扣积分，失败自动退款。
    """

    __tablename__ = "tts_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)  # 调用方（project）
    voice_id: Mapped[int] = mapped_column(ForeignKey("voices.id"), index=True)  # 使用的音色
    text: Mapped[str] = mapped_column(Text)  # 输入文本
    text_utf8_bytes: Mapped[int] = mapped_column(Integer)  # 输入文本 UTF-8 字节数（计费依据）
    cost_credits: Mapped[int] = mapped_column(Integer)  # 扣费积分（= bytes * price）
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued, index=True)
    error: Mapped[str] = mapped_column(String(255), default="")  # 错误码（失败时）
    output_audio_path: Mapped[str] = mapped_column(String(255), default="")  # 产出音频本地路径
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=format_timezone)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=format_timezone)


class CloneJob(Base):
    """
    表：clone_jobs
    用途：音色克隆任务（异步队列）。成功后产出 Voice（result_voice_id）。
    """

    __tablename__ = "clone_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)  # 调用方（project）
    voice_name: Mapped[str] = mapped_column(String(120))  # 目标音色名
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # 产出音色是否公开
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued, index=True)
    error: Mapped[str] = mapped_column(String(255), default="")
    dataset_dir: Mapped[str] = mapped_column(String(255), default="")  # 本地数据集目录（上传文件落这里）
    result_voice_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 成功后关联 voices.id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=format_timezone)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=format_timezone)


