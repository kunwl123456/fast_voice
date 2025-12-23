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
    id: int
    email: EmailStr
    display_name: str
    avatar_url: str  # 头像链接
    is_admin: bool
    subscription_plan: str  # free, pro, enterprise
    subscription_ends_at: str | None  # 订阅到期时间


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
    api_secret: str


class ApiKeyListItem(BaseModel):
    """API Key列表项（不包含secret）"""
    id: int
    api_key: str
    api_key_masked: str  # 脱敏显示，如 sk_live_...844f
    is_active: bool
    created_at: str


class CreateApiKeyIn(BaseModel):
    """创建API Key的请求（仅企业版可用）"""
    name: str = Field(default="", max_length=100, description="密钥名称（可选）")


class DashboardOut(BaseModel):
    """Dashboard概览数据"""
    user_id: int
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


class CreditAccountOut(BaseModel):
    user_id: int
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
    user_id: int
    amount: int = Field(gt=0, description="充值金额（必须为正数）")
    note: str = ""


class UpgradeSubscriptionIn(BaseModel):
    """升级订阅"""
    plan: str = Field(..., pattern="^(pro|enterprise)$", description="目标计划：pro或enterprise")
    months: int = Field(default=1, ge=1, le=12, description="订阅月数")


class VoiceOut(BaseModel):
    id: int
    name: str
    description: str
    is_public: bool
    preview_audio_url: str = ""


class VoiceUpdateIn(BaseModel):
    description: str | None = None
    is_public: bool | None = None


class TTSCreatIn(BaseModel):
    voice_id: int
    text: str


class JobOut(BaseModel):
    id: int
    status: str
    error: str = ""


class TTSJobOut(JobOut):
    voice_id: int
    text_utf8_bytes: int
    cost_credits: int
    output_audio_url: str = ""


class CloneCreateOut(JobOut):
    voice_name: str


class CloneJobOut(JobOut):
    voice_name: str
    result_voice_id: int | None = None
