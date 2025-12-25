"""
订阅计划和系统常量配置
统一管理所有订阅相关的配置，避免硬编码
"""

from enum import Enum
from dataclasses import dataclass


class SubscriptionPlanType(Enum):
    """订阅计划类型枚举"""

    free = "free"
    pro = "pro"
    enterprise = "enterprise"

    @classmethod
    def values(cls) -> list[str]:
        """获取所有订阅计划值列表"""
        return [member.value for member in cls]

    @classmethod
    def can_upgrade_plans(cls) -> list[str]:
        """获取可升级的订阅计划列表（不包括免费版）"""
        return [cls.pro.value, cls.enterprise.value]


# ============================================================================
# 订阅计划配置数据类
# ============================================================================


@dataclass
class PlanConfig:
    """订阅计划配置"""

    name: str  # 计划名称
    monthly_credits: int  # 每月赠送积分
    monthly_quota: int  # 月度请求配额
    clone_limit: int  # 克隆位限制（-1表示无限）
    api_access: bool  # 是否提供API访问
    commercial_use: bool  # 是否允许商业使用
    priority_support: bool  # 是否提供优先支持


# ============================================================================
# 订阅计划配置
# ============================================================================

SUBSCRIPTION_PLANS: dict[str, PlanConfig] = {
    "free": PlanConfig(
        name="免费版",
        monthly_credits=1000,  # 每月1000积分
        monthly_quota=100,  # 每月100次请求
        clone_limit=3,  # 最多3个克隆音色
        api_access=False,  # 无API访问
        commercial_use=False,  # 不允许商业使用
        priority_support=False,
    ),
    "pro": PlanConfig(
        name="专业版",
        monthly_credits=10000,  # 每月10000积分
        monthly_quota=5000,  # 每月5000次请求
        clone_limit=20,  # 最多20个克隆音色
        api_access=False,  # 无API访问（仅企业版）
        commercial_use=True,  # 允许商业使用
        priority_support=True,
    ),
    "enterprise": PlanConfig(
        name="企业版",
        monthly_credits=100000,  # 每月100000积分
        monthly_quota=500000,  # 每月500000次请求
        clone_limit=-1,  # 无限克隆位
        api_access=True,  # 提供API访问
        commercial_use=True,  # 允许商业使用
        priority_support=True,
    ),
}


# 订阅周期：每月天数
SUBSCRIPTION_DAYS_PER_MONTH = 30

# 订阅月数限制
SUBSCRIPTION_MIN_MONTHS = 1
SUBSCRIPTION_MAX_MONTHS = 12

# 默认订阅计划
DEFAULT_SUBSCRIPTION_PLAN: str = SubscriptionPlanType.free.value
