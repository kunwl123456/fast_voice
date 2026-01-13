"""
FastVoice API 路由统一注册中心

所有路由器都在这里统一创建和导出，views 模块从此处引用
"""

from fastapi import APIRouter, Depends
from app.core.deps import require_admin

# ============= Console 路由 =============
# 账户与认证
account_router = APIRouter(prefix="/console", tags=["账户与认证"])

# API Key 管理
api_keys_router = APIRouter(prefix="/console/api-keys", tags=["API Key 管理"])

# 数据分析与统计
analytics_router = APIRouter(prefix="/console/analytics", tags=["数据分析"])

# 积分管理
credits_router = APIRouter(prefix="/console/credits", tags=["积分管理"])

# 订阅管理
subscription_router = APIRouter(prefix="/console/subscription", tags=["订阅管理"])

# 订单管理
orders_router = APIRouter(prefix="/console/orders", tags=["订单管理"])

# 音色克隆 - Console
clone_console_router = APIRouter(prefix="/console/clone", tags=["音色克隆"])

# TTS - Console
tts_console_router = APIRouter(prefix="/console/tts", tags=["TTS"])

# 声音管理 - Console
voices_console_router = APIRouter(prefix="/console/voices", tags=["声音管理"])


# ============= OpenAPI 路由 =============
# 音色克隆 - OpenAPI
clone_openapi_router = APIRouter(prefix="/openapi/clone", tags=["音色克隆"])

# TTS - OpenAPI
tts_openapi_router = APIRouter(prefix="/openapi/tts", tags=["TTS"])

# 声音管理 - OpenAPI
voices_openapi_router = APIRouter(prefix="/openapi/voices", tags=["声音管理"])


# ============= Admin 路由 =============
# 积分管理 - Admin
admin_credit_router = APIRouter(
    prefix="/admin/credits", tags=["积分管理"], dependencies=[Depends(require_admin)]
)

# 订单管理 - Admin
admin_order_router = APIRouter(
    prefix="/admin/orders", tags=["订单管理"], dependencies=[Depends(require_admin)]
)

# 邀请码管理 - Admin
admin_invite_codes_router = APIRouter(
    prefix="/admin/invite-codes",
    tags=["邀请码管理"],
    dependencies=[Depends(require_admin)],
)


# ============= 文档路由 =============
docs_router = APIRouter(prefix="/docs", tags=["文档"])


# ============= Webhook 路由 =============
# Stripe Webhook（不需要认证）
webhook_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


# ============= 回调路由 =============
# 支付中台回调（内部接口，不需要用户认证）
callback_router = APIRouter(prefix="/callback", tags=["回调接口"])


# ============= 导出所有路由器 =============
__all__ = [
    # Console 路由
    "account_router",
    "api_keys_router",
    "analytics_router",
    "credits_router",
    "subscription_router",
    "orders_router",
    "clone_console_router",
    "tts_console_router",
    "voices_console_router",
    # OpenAPI 路由
    "clone_openapi_router",
    "tts_openapi_router",
    "voices_openapi_router",
    # Admin 路由
    "admin_credit_router",
    "admin_invite_codes_router",
    "admin_order_router",
    # Webhook 路由
    "webhook_router",
    # 回调路由
    "callback_router",
    # 文档路由
    "docs_router",
]
