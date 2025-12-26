"""控制台功能相关路由（仪表盘和统计）"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.responses import success_response
from app.core.deps import get_db, require_console_user
from app.controller.console import (
    get_user_dashboard,
    get_user_usage_stats,
    get_user_request_logs,
)
from app.core.schemas import (
    Response,
    DashboardOut,
    UsageStatsOut,
    PaginatedRequestLogs,
)

router = APIRouter(prefix="/console", tags=["控制台"])


@router.get(
    "/dashboard", summary="获取仪表盘信息", response_model=Response[DashboardOut]
)
async def get_dashboard(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)
):
    """
    获取用户控制台仪表盘数据

    ### 功能说明
    - 获取账户概览信息
    - 统计本月使用量
    - 显示订阅状态
    - 显示积分余额
    - 统计音色克隆数量

    ### 统计说明
    - 月度使用量从每月1号0点开始统计
    - 只统计成功的 API 请求（状态码 200）
    - 使用率 = (本月使用量 / 月度配额) × 100%
    """
    dashboard_data = await get_user_dashboard(db, user)
    return success_response("获取成功", dashboard_data.model_dump())


@router.get(
    "/usage-stats", summary="每日用量统计", response_model=Response[list[UsageStatsOut]]
)
async def get_usage_stats(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """
    获取 API 使用统计数据（按天聚合）

    ### 功能说明
    - 统计指定天数内的 API 调用情况
    - 按天聚合数据
    - 区分成功和失败的请求

    ### 统计规则
    - 从当前日期往前推算指定天数
    - 每天从 00:00:00 到 23:59:59
    - 按日期升序排列

    ### 使用场景
    - 查看 API 使用趋势
    - 监控服务质量
    - 分析使用模式
    - 生成使用报告
    """
    results = await get_user_usage_stats(db, user, days)
    stats_data = [s.model_dump() for s in results]
    return success_response("获取成功", stats_data)


@router.get(
    "/request-logs",
    summary="API 请求日志",
    response_model=Response[PaginatedRequestLogs],
)
async def get_request_logs(
    page: int = Query(default=1, ge=1, description="页码，从1开始"),
    page_size: int = Query(default=50, ge=1, le=200, description="每页数量，最多200条"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """
    获取 API 请求日志（分页查询）

    ### 功能说明
    - 查询用户的 API 请求历史记录
    - 支持分页浏览
    - 包含请求详情和性能指标

    ### 排序规则
    按请求时间倒序排列（最新的在前）

    ### 使用场景
    - 调试 API 调用问题
    - 分析性能瓶颈
    - 审计 API 使用情况
    - 排查错误原因
    """
    pagination_data = await get_user_request_logs(db, user, page, page_size)
    return success_response("获取成功", pagination_data.model_dump())
