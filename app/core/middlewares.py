"""
FastAPI 中间件
用于记录 OpenAPI 请求日志等功能
"""

from __future__ import annotations

import time

from fastapi import Request, Response
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from app.db import AsyncSessionLocal
from app.models import ApiKey, ApiRequestLog, format_timezone


class OpenAPILoggingMiddleware(BaseHTTPMiddleware):
    """
    OpenAPI 请求日志记录中间件

    功能：
    - 只记录以 /openapi 开头的请求
    - 记录请求方法、路径、状态码、延迟、响应大小
    - 自动关联 API Key 和用户
    - 捕获错误信息
    """

    async def dispatch(self, request: Request, call_next):
        # 只记录 /openapi 开头的请求
        if not request.url.path.startswith("/openapi"):
            return await call_next(request)

        # 记录开始时间
        start_time = time.time()

        # 提取 API Key（从 Authorization header）
        auth_header = request.headers.get("Authorization", "")
        api_key_value = None
        if auth_header.startswith("Bearer "):
            api_key_value = auth_header.removeprefix("Bearer ").strip()

        # 初始化日志数据
        log_data = {
            "endpoint": request.url.path,
            "method": request.method,
            "status_code": 500,  # 默认为 500，如果出错会使用这个值
            "error_message": "",
        }

        # 执行请求
        response: Response | None = None
        try:
            response = await call_next(request)
            log_data["status_code"] = response.status_code
        except Exception as e:
            # 捕获异常
            log_data["status_code"] = 500
            log_data["error_message"] = str(e)[:255]
            raise
        finally:
            # 计算延迟（毫秒）
            latency_ms = int((time.time() - start_time) * 1000)
            log_data["latency_ms"] = latency_ms

            # 计算响应大小（如果有响应）
            response_size = 0
            if response is not None and hasattr(response, "body"):
                try:
                    # 尝试获取响应体大小
                    if isinstance(response.body, bytes):
                        response_size = len(response.body)
                except Exception:
                    pass
            log_data["response_size"] = response_size

            # 异步保存日志到数据库
            await self._save_log(api_key_value, log_data)

        return response

    async def _save_log(self, api_key_value: str | None, log_data: dict) -> None:
        """
        保存日志到数据库

        Args:
            api_key_value: API Key 值
            log_data: 日志数据字典
        """
        if not api_key_value:
            # 没有 API Key，无法记录（因为需要关联用户和 API Key）
            return

        db = AsyncSessionLocal()
        try:
            # 查询 API Key
            api_key = (
                await db.execute(select(ApiKey).where(ApiKey.api_key == api_key_value))
            ).scalar_one_or_none()

            if not api_key:
                # API Key 不存在，无法记录
                return

            # 创建日志记录
            log = ApiRequestLog(
                user_id=api_key.user_id,
                api_key_id=api_key.id,
                endpoint=log_data["endpoint"],
                method=log_data["method"],
                status_code=log_data["status_code"],
                latency_ms=log_data["latency_ms"],
                response_size=log_data["response_size"],
                error_message=log_data["error_message"],
                created_at=format_timezone(),
            )
            db.add(log)
            await db.commit()
        except Exception as e:
            # 日志记录失败不应该影响主流程，只打印错误
            print(f"⚠️  保存 OpenAPI 请求日志失败: {e}")
            await db.rollback()
        finally:
            await db.close()
