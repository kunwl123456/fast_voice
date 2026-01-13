from __future__ import annotations

from typing import Generic, TypeVar
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_serializer

from app.core.constants import (
    CAN_UPGRADE_PLANS,
    SUBSCRIPTION_MIN_MONTHS,
    SUBSCRIPTION_MAX_MONTHS,
    PaymentProvider,
    Currency,
)

# 定义泛型类型变量
T = TypeVar("T")


def format_datetime(dt: datetime | str | None) -> str | None:
    """
    格式化时间字段为统一格式

    Args:
        dt: datetime 对象、字符串或 None

    Returns:
        格式化后的时间字符串（格式：2025-12-12 12:00:00）或 None
    """
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class Response(BaseModel, Generic[T]):
    """统一的 API 响应格式（支持泛型）"""

    message: str = Field(description="提示信息")
    data: T = Field(description="响应体数据")


class RegisterIn(BaseModel):
    email: EmailStr = Field(description="用户邮箱地址")
    password: str = Field(
        min_length=6, max_length=72, description="登录密码（6-72个字符）"
    )
    display_name: str = Field(
        default="", max_length=100, description="显示名称（最多100个字符，可选）"
    )
    invite_code: str = Field(description="邀请码（必须）")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "liuyulin@autogame.ai",
                "password": "123456",
                "display_name": "",
                "invite_code": "autogame-fast-voice",
            }
        }
    )


class LoginIn(BaseModel):
    email: EmailStr = Field(description="用户邮箱地址")
    password: str = Field(description="登录密码")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "liuyulin@autogame.ai",
                "password": "123456",
            }
        }
    )


class TokenOut(BaseModel):
    access_token: str = Field(description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class MeOut(BaseModel):
    id: str = Field(description="用户 UUID")
    email: EmailStr = Field(description="邮箱地址")
    display_name: str = Field(description="显示名称")
    avatar_url: str = Field(description="头像 URL")
    is_admin: bool = Field(description="是否管理员")
    subscription_plan: str = Field(description="订阅计划（free/pro/enterprise）")
    subscription_ends_at: datetime | str | None = Field(description="订阅到期时间")
    credit_balance: int = Field(description="积分余额")

    @field_serializer("subscription_ends_at")
    def serialize_datetime(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class LoginOut(MeOut):
    """登录成功返回的数据"""

    access_token: str = Field(description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class RenameIn(BaseModel):
    display_name: str = Field(
        min_length=1, max_length=100, description="新的显示名称（1-100个字符）"
    )


class UpdateAvatarIn(BaseModel):
    avatar_url: str = Field(max_length=512, description="头像URL链接")


class ChangePasswordIn(BaseModel):
    old_password: str = Field(description="原密码")
    new_password: str = Field(
        min_length=6, max_length=72, description="新密码（6-72个字符）"
    )


class SubscriptionInfo(BaseModel):
    """订阅计划信息"""

    plan: str = Field(description="订阅计划代码（free/pro/enterprise）")
    plan_name: str = Field(description="计划名称（免费版/专业版/企业版）")
    status: str = Field(description="订阅状态（active/expired/cancelled）")
    ends_at: datetime | str | None = Field(description="订阅到期时间")
    features: dict = Field(description="功能特性列表")

    @field_serializer("ends_at")
    def serialize_datetime(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class ApiKeyOut(BaseModel):
    api_key: str = Field(description="完整的 API Key（仅创建时显示一次）")
    expires_at: datetime | str | None = Field(
        description="过期时间（null 表示永不过期）"
    )

    @field_serializer("expires_at")
    def serialize_datetime(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class ApiKeyListItem(BaseModel):
    """API Key列表项"""

    id: int = Field(description="API Key ID")
    name: str = Field(description="密钥名称")
    api_key_masked: str = Field(description="脱敏显示的 Key（如 sk-...）")
    is_active: bool = Field(description="是否激活")
    expires_at: datetime | str | None = Field(
        description="过期时间（null 表示永久有效）"
    )
    created_at: datetime | str = Field(description="创建时间")

    @field_serializer("expires_at", "created_at")
    def serialize_datetime(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class CreateApiKeyIn(BaseModel):
    """创建API Key的请求（仅企业版可用）"""

    name: str = Field(default="", max_length=100, description="密钥名称（可选）")
    expires_days: int | None = Field(
        default=None, ge=1, description="有效期天数（null表示永不过期）"
    )


class DashboardOut(BaseModel):
    """Dashboard概览数据"""

    user_id: str = Field(description="用户 UUID")
    email: str = Field(description="邮箱地址")
    plan_name: str = Field(description="订阅计划名称")
    plan_status: str = Field(description="订阅状态（active/expired）")
    monthly_usage: int = Field(description="本月使用量（API 调用次数）")
    monthly_quota: int = Field(description="月度配额（根据计划不同）")
    usage_percent: float = Field(description="使用率百分比")
    next_billing_date: str = Field(description="下一个账单日期")
    credit_balance: int = Field(description="积分余额")
    clone_count: int = Field(description="已克隆音色数量")
    clone_limit: int = Field(description="音色克隆上限（-1表示无限）")
    api_access_enabled: bool = Field(description="是否启用 API 访问")


class UsageStatsOut(BaseModel):
    """使用统计数据"""

    date: str = Field(description="日期（YYYY-MM-DD 格式）")
    total_requests: int = Field(description="总请求数")
    successful_requests: int = Field(description="成功请求数（状态码 200）")
    failed_requests: int = Field(description="失败请求数")


class RequestLogOut(BaseModel):
    """API请求日志"""

    id: int = Field(description="日志 ID")
    timestamp: datetime | str = Field(description="请求时间")
    endpoint: str = Field(description="请求路径")
    method: str = Field(description="HTTP 方法")
    status_code: int = Field(description="响应状态码")
    latency_ms: int = Field(description="响应延迟（毫秒）")
    response_size: int = Field(description="响应大小（字节）")
    error_message: str = Field(description="错误消息（如有）")

    @field_serializer("timestamp")
    def serialize_datetime(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class PaginatedRequestLogs(BaseModel):
    """分页的API请求日志"""

    items: list[RequestLogOut] = Field(description="日志列表")
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    total_pages: int = Field(description="总页数")
    has_next: bool = Field(description="是否有下一页")
    has_prev: bool = Field(description="是否有上一页")


class CreditAccountOut(BaseModel):
    user_id: str = Field(description="用户 UUID")
    balance: int = Field(description="积分余额")


class CreditTxOut(BaseModel):
    id: int = Field(description="交易 ID")
    tx_type: str = Field(description="交易类型（subscription/recharge/consume/refund）")
    amount: int = Field(description="金额（正数为收入，负数为支出）")
    ref_type: str = Field(description="关联类型")
    ref_id: str = Field(description="关联 ID")
    note: str = Field(description="备注说明")
    created_at: datetime | str = Field(description="交易时间")

    @field_serializer("created_at")
    def serialize_datetime(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class RechargeIn(BaseModel):
    user_id: str = Field(description="目标用户的 UUID")
    amount: int = Field(gt=0, description="充值金额（必须为正整数）")
    note: str = Field(default="", description="备注说明（可选）")


class PlanConfigOut(BaseModel):
    """订阅计划配置信息"""

    id: int = Field(description="主键ID")
    plan: str = Field(description="订阅计划代码（free/pro/enterprise）")
    name: str = Field(description="计划名称（免费版/专业版/企业版）")
    monthly_credits: int = Field(description="每月赠送积分")
    monthly_quota: int = Field(description="月度请求配额")
    clone_limit: int = Field(description="克隆位限制（-1表示无限）")
    api_access: bool = Field(description="是否提供API访问")
    commercial_use: bool = Field(description="是否允许商业使用")
    priority_support: bool = Field(description="是否提供优先支持")
    monthly_price: int = Field(description="月价（整数）")
    currency: str = Field(description="ISO 4217 货币代码（默认 CNY）")


class UpgradeSubscriptionIn(BaseModel):
    """升级订阅"""

    plan: str = Field(
        description=f"目标计划：{' 或 '.join(CAN_UPGRADE_PLANS)}",
    )
    months: int = Field(
        default=1,
        description=f"订阅月数（{SUBSCRIPTION_MIN_MONTHS}-{SUBSCRIPTION_MAX_MONTHS}个月）",
    )
    pay_type: str | None = Field(
        default=None,
        description=f"支付方式：{list(PaymentProvider.__members__.keys())}",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan": "pro",
                "months": 1,
                "pay_type": "",
            }
        }
    )


class UpgradeSubscriptionOut(BaseModel):
    """升级订阅成功返回的数据"""

    plan: str = Field(description="订阅计划（pro/enterprise）")
    ends_at: str = Field(description="订阅到期时间")
    credits_added: int = Field(description="赠送的积分数")


class VoiceOut(BaseModel):
    id: str = Field(description="音色 UUID")
    name: str = Field(description="音色名称")
    avatar_url: str = Field(default="", description="音色头像 URL")
    description: str = Field(description="音色描述")
    tags: list[str] = Field(default=[], description="音色标签列表")
    is_public: bool = Field(description="是否公开")
    preview_audio_url: str = Field(default="", description="预览音频 URL")
    clone_job_uuid: str = Field(default="", description="克隆任务 UUID（用于 TTS）")
    likes_count: int = Field(default=0, description="点赞数")
    generated_chars_count: int = Field(default=0, description="生成字符数")
    usage_count: int = Field(default=0, description="使用次数")
    created_at: datetime | str = Field(description="创建时间")

    @field_serializer("created_at")
    def serialize_datetime(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class VoiceUpdateIn(BaseModel):
    description: str | None = Field(None, description="音色描述（可选）")
    is_public: bool | None = Field(None, description="是否公开（可选）")
    tags: list[str] | None = Field(None, description="音色标签列表（只能使用预设标签）")


class VoiceRenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=120, description="音色名称")


class TTSCreatIn(BaseModel):
    clone_job_id: str = Field(
        ..., description="克隆任务的 UUID（/console/clone/jobs 返回的 data.id）"
    )
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
        default=None,
        max_length=512,
        description="Webhook 回调地址，任务完成时调用；可选",
    )


class JobOut(BaseModel):
    id: str = Field(description="任务 UUID")
    status: str = Field(description="任务状态")
    error: str = Field(default="", description="错误信息（如有）")


class TTSJobOut(JobOut):
    voice_uuid: str = Field(description="使用的音色 UUID")
    text_utf8_bytes: int = Field(description="文本字节数（UTF-8编码）")
    cost_credits: int = Field(description="消耗的积分数")
    tags: list[str] = Field(description="音色标签")
    speed_factor: float = Field(description="语速系数")
    temperature: float = Field(description="采样温度")
    top_k: int = Field(description="采样 top_k 参数")
    top_p: float = Field(description="采样 top_p 参数")
    output_audio_url: str = Field(default="", description="输出音频 URL")


class TTSHistoryItemOut(BaseModel):
    """TTS 生成历史记录项"""

    id: str = Field(description="任务 UUID")
    status: str = Field(description="任务状态")
    text: str = Field(description="输入文本")
    voice_uuid: str = Field(description="使用的音色 UUID")
    voice_name: str = Field(description="音色名称")
    voice_avatar_url: str = Field(default="", description="音色头像 URL")
    output_audio_url: str = Field(default="", description="输出音频 URL")
    cost_credits: int = Field(description="消耗的积分数")
    created_at: str = Field(description="创建时间（ISO 8601格式）")
    error: str = Field(default="", description="错误信息（如有）")


class TTSHistoryListOut(BaseModel):
    """TTS 生成历史列表"""

    items: list[TTSHistoryItemOut] = Field(description="历史记录列表")
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")


class CloneCreateIn(BaseModel):
    voice_name: str = Field(description="音色名称")
    avatar_url: str = Field(default="", description="头像 URL（可选）")
    description: str = Field(default="", description="音色描述（可选）")
    tags: list = Field(default=[], description="标签列表（JSON 数组）")
    is_public: bool = Field(default=False, description="是否公开（默认为 false）")
    remove_background_noise: bool = Field(
        default=False, description="是否去除背景噪音（默认为 false）"
    )


class CloneCreateOut(JobOut):
    voice_name: str = Field(description="音色名称")
    avatar_url: str = Field(default="", description="头像 URL")
    description: str = Field(default="", description="音色描述")
    tags: list[str] = Field(default=[], description="标签列表")
    user_id: str = Field(description="用户 UUID")
    created_at: datetime | str = Field(description="创建时间")
    preview_audio_url: str = Field(default="", description="预览音频 URL")

    @field_serializer("created_at")
    def serialize_datetime(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class CloneJobOut(JobOut):
    voice_name: str = Field(description="音色名称")
    avatar_url: str = Field(default="", description="头像 URL")
    description: str = Field(default="", description="音色描述")
    tags: list[str] = Field(default=[], description="标签列表")
    user_id: str = Field(description="用户 UUID")
    created_at: datetime | str = Field(description="创建时间")
    preview_audio_url: str = Field(default="", description="预览音频 URL")
    result_voice_uuid: str | None = Field(None, description="克隆成功后生成的音色 UUID")

    @field_serializer("created_at")
    def serialize_datetime(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class InviteCodeOut(BaseModel):
    """邀请码信息"""

    id: int = Field(description="邀请码 ID")
    code: str = Field(description="邀请码")
    is_used: bool = Field(description="是否已使用")
    used_by_email: str | None = Field(None, description="使用者邮箱")
    expires_at: datetime | str | None = Field(description="过期时间")
    note: str = Field(description="备注说明")
    created_at: datetime | str = Field(description="创建时间")
    used_at: datetime | str | None = Field(None, description="使用时间")

    @field_serializer("expires_at", "created_at", "used_at")
    def serialize_datetime(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class CreateInviteCodeIn(BaseModel):
    """创建邀请码请求"""

    count: int = Field(default=1, ge=1, le=100, description="生成数量（1-100）")
    expires_days: int | None = Field(
        default=None, ge=1, description="有效期天数（null表示永不过期）"
    )
    note: str = Field(default="", max_length=255, description="备注说明（可选）")


class BatchInviteCodesOut(BaseModel):
    """批量生成邀请码的响应"""

    codes: list[str] = Field(description="生成的邀请码列表")
    count: int = Field(description="生成数量")
    expires_at: datetime | str | None = Field(description="过期时间")

    @field_serializer("expires_at")
    def serialize_datetime(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


# ============= 订单相关 =============


class CreateOrderIn(BaseModel):
    """创建订单请求"""

    order_type: str = Field(
        description="订单类型：credit_recharge（积分充值）或 subscription（订阅购买）"
    )
    currency: Currency = Field(description="货币类型")
    product_id: int = Field(description="商品ID")
    product_name: str = Field(description="商品名称")
    unit_price: int = Field(description="单价")
    quantity: int = Field(
        default=1,
        ge=1,
        le=12,
        description="数量：订阅=月数（1-12），积分包=份数（通常为1）",
    )
    payment_method: PaymentProvider | None = Field(
        default=None,
        description="支付方式：stripe 或 wechatpay；不指定则默认 stripe",
    )
    extra_metadata: dict | None = Field(None, description="附加元数据")


class CreateOrderOut(BaseModel):
    """创建订单响应"""

    order_id: str = Field(description="业务订单号")
    order_type: str = Field(description="订单类型")
    product_id: int = Field(description="商品ID")
    product_name: str = Field(description="商品名称")
    quantity: int = Field(description="数量")
    amount: float = Field(description="应付金额")
    currency: str = Field(description="货币类型")
    status: str = Field(description="订单状态")

    # 支付信息
    payment_id: str | None = Field(description="支付网关订单号")
    extra: dict | None = Field(description="前端支付时所需的额外字段")
    expires_at: datetime | str | None = Field(description="订单过期时间")

    @field_serializer("expires_at")
    def serialize_expires_at(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class OrderDetailOut(BaseModel):
    """订单详情响应"""

    order_id: str = Field(description="业务订单号")
    order_type: str = Field(description="订单类型")
    product_id: str = Field(description="商品ID")
    product_name: str = Field(description="商品名称")
    quantity: int = Field(description="数量")
    amount: float = Field(description="应付金额")
    currency: str = Field(description="货币类型")
    status: str = Field(
        description="订单状态：pending/paid/fulfilled/cancelled/expired/refunded"
    )

    # 支付信息
    payment_id: str | None = Field(description="支付网关订单号")
    payment_method: PaymentProvider | None = Field(description="支付方式")

    # 时间信息
    created_at: datetime | str = Field(description="创建时间")
    paid_at: datetime | str | None = Field(description="支付时间")
    expires_at: datetime | str | None = Field(description="订单过期时间")

    @field_serializer("created_at", "paid_at", "expires_at")
    def serialize_datetime_fields(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class OrderListOut(BaseModel):
    """订单列表项"""

    order_id: str = Field(description="业务订单号")
    order_type: str = Field(description="订单类型")
    product_name: str = Field(description="商品名称")
    amount: float = Field(description="应付金额")
    currency: str = Field(description="货币类型")
    status: str = Field(description="订单状态")
    created_at: datetime | str = Field(description="创建时间")

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class PaymentCallbackIn(BaseModel):
    """支付中台回调请求"""

    order_id: str = Field(description="业务订单号")
    payment_id: str = Field(description="支付中台订单号")
    status: str = Field(description="支付状态：succeeded/failed/cancelled")
    paid_amount: float | None = Field(default=None, description="实际支付金额")
    paid_at: datetime | str | None = Field(default=None, description="支付时间")
    error_message: str | None = Field(default=None, description="错误信息（失败时）")
    signature: str | None = Field(
        default=None, description="签名（用于验证回调合法性）"
    )


# ============= 退款相关 =============


class CreateRefundIn(BaseModel):
    """创建退款请求"""

    order_id: str = Field(description="业务订单号")
    refund_amount: int | None = Field(
        default=None,
        gt=0,
        description="退款金额（最小货币单位，如分）。不填则为全额退款",
    )
    reason: str | None = Field(default=None, max_length=500, description="退款原因")


class RefundOut(BaseModel):
    """退款响应"""

    refund_id: str = Field(description="退款ID")
    order_id: str = Field(description="业务订单号")
    payment_id: str = Field(description="支付网关支付ID")
    refund_amount: int = Field(description="退款金额（最小货币单位，如分）")
    reason: str | None = Field(description="退款原因")
    status: str = Field(
        description="退款状态：pending/processing/succeeded/failed/cancelled"
    )
    provider: str = Field(description="支付渠道")
    provider_refund_id: str | None = Field(description="支付渠道退款ID")
    created_at: datetime | str = Field(description="创建时间")
    updated_at: datetime | str = Field(description="更新时间")
    refunded_at: datetime | str | None = Field(description="退款完成时间")

    @field_serializer("created_at", "updated_at", "refunded_at")
    def serialize_datetime_fields(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


# ============================================================================
# Stripe 支付相关 Schemas
# ============================================================================


class CreatePaymentIntentIn(BaseModel):
    """创建支付意图的请求参数"""

    payment_type: str = Field(description="支付类型：credit_recharge 或 subscription")
    amount: float = Field(gt=0, description="支付金额")
    currency: str | None = Field(
        default=None,
        description="货币类型：usd、cny、hkd 等。不指定则根据支付方式自动选择（card默认usd，alipay/wechat_pay默认cny）",
    )
    payment_method: PaymentProvider | None = Field(
        default=None,
        description="指定支付方式：stripe 或 wechatpay；不指定则默认 stripe",
    )
    credits_amount: int | None = Field(
        default=None, description="充值的积分数量（仅用于积分充值）"
    )
    subscription_plan: str | None = Field(
        default=None, description="订阅计划（仅用于订阅支付）：pro 或 enterprise"
    )
    subscription_months: int | None = Field(
        default=None, ge=1, le=12, description="订阅月数（仅用于订阅支付，1-12个月）"
    )


class CreatePaymentIntentOut(BaseModel):
    """创建支付意图的响应"""

    payment_id: str = Field(description="支付订单ID")
    client_secret: str = Field(description="客户端密钥（用于前端确认支付）")
    publishable_key: str = Field(description="Stripe 公钥（用于前端初始化）")
    amount: float = Field(description="支付金额（美元）")
    currency: str = Field(description="货币类型")
    return_url: str = Field(description="支付完成后返回的 URL（前端确认支付时需要）")


class PaymentStatusOut(BaseModel):
    """支付状态查询响应"""

    payment_id: str = Field(description="支付订单ID")
    status: str = Field(description="支付状态")
    payment_type: str = Field(description="支付类型")
    amount: float = Field(description="支付金额（美元）")
    currency: str = Field(description="货币类型")
    credits_amount: int | None = Field(description="充值的积分数量")
    subscription_plan: str | None = Field(description="订阅计划")
    subscription_months: int | None = Field(description="订阅月数")
    error_message: str | None = Field(description="错误信息")
    created_at: datetime | str = Field(description="创建时间")
    completed_at: datetime | str | None = Field(description="完成时间")

    @field_serializer("created_at", "completed_at")
    def serialize_datetime_fields(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class PaymentHistoryOut(BaseModel):
    """支付历史记录"""

    payment_id: str = Field(description="支付订单ID")
    payment_type: str = Field(description="支付类型")
    amount: float = Field(description="支付金额（美元）")
    currency: str = Field(description="货币类型")
    status: str = Field(description="支付状态")
    credits_amount: int | None = Field(description="充值的积分数量")
    subscription_plan: str | None = Field(description="订阅计划")
    subscription_months: int | None = Field(description="订阅月数")
    created_at: datetime | str = Field(description="创建时间")
    completed_at: datetime | str | None = Field(description="完成时间")

    @field_serializer("created_at", "completed_at")
    def serialize_datetime_fields(self, dt: datetime | str | None, _info) -> str | None:
        return format_datetime(dt)


class StripeConfigOut(BaseModel):
    """Stripe 配置信息（公开信息）"""

    publishable_key: str = Field(description="Stripe 公钥")
    currency: str = Field(default="usd", description="货币类型")
