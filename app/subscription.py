"""
订阅计划配置

定义三种订阅计划的功能和配额
"""

from dataclasses import dataclass


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


# 订阅计划配置
SUBSCRIPTION_PLANS = {
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


def get_plan_config(plan: str) -> PlanConfig:
    """获取计划配置"""
    return SUBSCRIPTION_PLANS.get(plan, SUBSCRIPTION_PLANS["free"])


def get_plan_features(plan: str) -> dict:
    """获取计划功能特性（用于前端展示）"""
    config = get_plan_config(plan)
    return {
        "monthly_credits": config.monthly_credits,
        "monthly_quota": config.monthly_quota,
        "clone_limit": config.clone_limit,
        "api_access": config.api_access,
        "commercial_use": config.commercial_use,
        "priority_support": config.priority_support,
    }
