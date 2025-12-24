from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    display_name: str = Field(default="", max_length=100)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: str  # 用户UUID
    email: EmailStr
    display_name: str
    avatar_url: str  # 头像链接
    is_admin: bool
    subscription_plan: str  # free, pro, enterprise
    subscription_ends_at: str | None  # 订阅到期时间
    credit_balance: int  # 积分余额


class RegisterOut(BaseModel):
    """注册成功返回的数据"""
    id: str  # 用户UUID
    email: EmailStr
    display_name: str
    avatar_url: str  # 头像链接
    is_admin: bool
    subscription_plan: str  # free, pro, enterprise
    subscription_ends_at: str | None  # 订阅到期时间
    credit_balance: int  # 积分余额


class RenameIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class UpdateAvatarIn(BaseModel):
    avatar_url: str = Field(max_length=512, description="头像URL链接")


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=72)


class SubscriptionInfo(BaseModel):
    """订阅计划信息"""

    plan: str  # free, pro, enterprise
    plan_name: str  # 免费版、专业版、企业版
    status: str  # active, expired, cancelled
    ends_at: str | None
    features: dict  # 功能特性


class ApiKeyOut(BaseModel):
    api_key: str
    expires_at: str | None  # ISO 格式的过期时间，None 表示永不过期


class ApiKeyListItem(BaseModel):
    """API Key列表项"""

    id: int
    name: str
    api_key_masked: str  # 脱敏显示，如 sk-...844f
    is_active: bool
    expires_at: str | None  # 过期时间（为空表示永久有效）
    created_at: str


class CreateApiKeyIn(BaseModel):
    """创建API Key的请求（仅企业版可用）"""

    name: str = Field(default="", max_length=100, description="密钥名称（可选）")
    expires_days: int | None = Field(
        default=None, ge=1, description="有效期天数（null表示永不过期）"
    )


class DashboardOut(BaseModel):
    """Dashboard概览数据"""

    user_id: str  # 用户UUID
    email: str
    plan_name: str
    plan_status: str  # active, expired
    monthly_usage: int  # 本月使用量（请求数）
    monthly_quota: int  # 月度配额（根据计划不同）
    usage_percent: float  # 使用百分比
    next_billing_date: str  # 下一个账单日期
    credit_balance: int  # 积分余额
    clone_count: int  # 已克隆音色数量
    clone_limit: int  # 克隆位限制（-1表示无限）
    api_access_enabled: bool  # 是否可以使用API


class UsageStatsOut(BaseModel):
    """使用统计数据"""

    date: str
    total_requests: int
    successful_requests: int
    failed_requests: int


class RequestLogOut(BaseModel):
    """API请求日志"""

    id: int
    timestamp: str
    endpoint: str
    method: str
    status_code: int
    latency_ms: int
    response_size: int
    error_message: str


class PaginatedRequestLogs(BaseModel):
    """分页的API请求日志"""

    items: list[RequestLogOut]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class CreditAccountOut(BaseModel):
    user_id: str  # 用户UUID
    balance: int


class CreditTxOut(BaseModel):
    id: int
    tx_type: str
    amount: int
    ref_type: str
    ref_id: str
    note: str
    created_at: str


class RechargeIn(BaseModel):
    user_id: str  # 用户UUID
    amount: int = Field(gt=0, description="充值金额（必须为正数）")
    note: str = ""


class UpgradeSubscriptionIn(BaseModel):
    """升级订阅"""

    plan: str = Field(
        ..., pattern="^(pro|enterprise)$", description="目标计划：pro或enterprise"
    )
    months: int = Field(default=1, ge=1, le=12, description="订阅月数")


class VoiceOut(BaseModel):
    id: str  # Voice 的 UUID
    name: str
    avatar_url: str = ""
    description: str
    tags: list[str] = []
    is_public: bool
    preview_audio_url: str = ""
    likes_count: int = 0  # 点赞数
    generated_chars_count: int = 0  # 生成字符数
    usage_count: int = 0  # 使用次数
    created_at: str  # 创建时间


class VoiceUpdateIn(BaseModel):
    description: str | None = None
    is_public: bool | None = None


class VoiceRenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=120, description="音色名称")


class TTSCreatIn(BaseModel):
    clone_job_id: str = Field(..., description="克隆任务的 UUID（/console/clone/jobs 返回的 data.id）")
    text: str
    speed_factor: float | None = Field(
        default=None, description="语速，可选；未提供则使用默认值 1.0"
    )
    temperature: float | None = Field(
        default=None, description="采样温度，可选；未提供则使用默认值 1.0"
    )
    top_k: int | None = Field(default=None, description="采样 top_k，可选；默认 5")
    top_p: float | None = Field(default=None, description="采样 top_p，可选；默认 1.0")
    webhook_url: str | None = Field(
        default=None, max_length=512, description="Webhook 回调地址，任务完成时调用；可选"
    )


class JobOut(BaseModel):
    id: str  # UUID 字符串
    status: str
    error: str = ""


class TTSJobOut(JobOut):
    voice_uuid: str  # 使用的音色 UUID
    text_utf8_bytes: int
    cost_credits: int
    tags: list[str]
    speed_factor: float
    temperature: float
    top_k: int
    top_p: float
    output_audio_url: str = ""


class CloneCreateOut(JobOut):
    voice_name: str
    avatar_url: str = ""
    description: str = ""
    tags: list[str] = []
    user_id: str  # 用户UUID
    created_at: str
    preview_audio_url: str = ""


class CloneJobOut(JobOut):
    voice_name: str
    avatar_url: str = ""
    description: str = ""
    tags: list[str] = []
    user_id: str  # 用户UUID
    created_at: str
    preview_audio_url: str = ""
    result_voice_uuid: str | None = None  # 克隆成功后生成的音色 UUID
