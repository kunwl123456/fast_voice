"""
订阅计划和系统常量配置
统一管理所有订阅相关的配置，避免硬编码

注意：订阅计划的详细配置已迁移到数据库表 subscription_plans
此文件仅保留枚举类型和系统常量
"""

from enum import Enum


class TxType(str, Enum):
    """积分流水类型。"""

    recharge = "recharge"  # 充值
    consume = "consume"  # 消费（创建任务时预扣）
    refund = "refund"  # 退款（任务失败自动回滚）
    subscription = "subscription"  # 订阅赠送


class JobStatus(str, Enum):
    """异步任务状态机（TTS/克隆共用）。"""

    queued = "queued"  # 已入队等待 worker
    running = "running"  # worker 正在处理
    succeeded = "succeeded"  # 成功产出结果
    failed = "failed"  # 失败（并触发退款/记录错误）


class OrderStatus(str, Enum):
    """业务订单状态枚举"""

    pending = "pending"  # 待支付
    paid = "paid"  # 已支付
    fulfilled = "fulfilled"  # 已完成（业务处理完成）
    failed = "failed"  # 失败
    cancelled = "cancelled"  # 已取消
    expired = "expired"  # 已过期
    refunded = "refunded"  # 已退款


class OrderType(str, Enum):
    """业务订单类型枚举"""

    credit_recharge = "credit_recharge"  # 积分充值
    subscription = "subscription"  # 订阅购买


class PaymentProvider(str, Enum):
    """支付渠道（用于与支付网关 provider 对齐的业务枚举）。"""

    stripe = "stripe"
    alipay = "alipay"


class Currency(str, Enum):
    """货币类型"""

    USD = "USD"  # 美元
    CNY = "CNY"  # 人民币
    HKD = "HKD"  # 港币
    KRW = "KRW"  # 韩元
    THB = "THB"  # 泰铢
    EUR = "EUR"  # 欧元
    GBP = "GBP"  # 英镑
    JPY = "JPY"  # 日元
    INR = "INR"  # 印度卢比


# 订阅配置
# 订阅周期：每月天数
SUBSCRIPTION_DAYS_PER_MONTH = 30
# 订阅月数限制
SUBSCRIPTION_MIN_MONTHS = 1
SUBSCRIPTION_MAX_MONTHS = 12
# 默认订阅计划
DEFAULT_SUBSCRIPTION_PLAN: str = "free"
# 可升级的订阅计划
CAN_UPGRADE_PLANS = ["pro", "enterprise"]

# 订单配置
# 订单过期时间（分钟）
ORDER_EXPIRE_MINUTES = 30
