from __future__ import annotations

import os
from loguru import logger
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer

from app.models import *  # noqa: F401,F403 (ensure models imported for metadata)
from app.core.openapi import setup_openapi, OPENAPI_DESCRIPTION
from app.core.middlewares import OpenAPILoggingMiddleware
from app.responses import (
    server_error_response,
    bad_request_response,
    unauthorized_response,
    forbidden_response,
    not_found_response,
)
from app.exceptions import (
    NotFoundException,
    PermissionException,
    AuthenticationException,
)
from app.core.config import settings
from app.services.storage import ensure_dir
from app.services.bootstrap import bootstrap_admin
from app.db import Base, engine, AsyncSessionLocal
from app.views.console import router as console_router
from app.views.credits import router as credits_router
from app.views.account import router as account_router
from app.views.api_keys import router as api_keys_router
from app.views.tts import console_router as tts_console_router
from app.views.tts import openapi_router as tts_openapi_router
from app.views.invite_codes import router as invite_codes_router
from app.views.subscription import router as subscription_router
from app.views.clone import console_router as clone_console_router
from app.views.clone import openapi_router as clone_openapi_router
from app.views.voices import console_router as voices_console_router
from app.views.voices import openapi_router as voices_openapi_router


app = FastAPI(
    title="FastVoice",
    version="0.1.0",
    description=OPENAPI_DESCRIPTION,
    # 配置 Bearer Token 认证
    swagger_ui_parameters={
        "persistAuthorization": True,  # 持久化认证信息（刷新页面后不需要重新输入）
    },
)

# 配置自定义 OpenAPI schema
setup_openapi(app)

# 定义安全方案（用于在路由中引用，如果需要显示锁图标）
security = HTTPBearer(
    scheme_name="Bearer Authentication",
    description="输入你的 JWT Token 或 API Key（自动添加 'Bearer ' 前缀）",
)

# 添加 OpenAPI 请求日志中间件（必须在其他中间件之前）
app.add_middleware(OpenAPILoggingMiddleware)


@app.middleware("http")
async def capture_raw_body(request: Request, call_next):
    """
    OpenAPI 签名需要"原始 body bytes"的 sha256，因此这里缓存 raw body 到 request.state。

    注意：对于 SSE 端点（/events），跳过此中间件，因为重写 receive() 会干扰长连接
    """
    # 跳过 SSE 端点
    if request.url.path.endswith("/events"):
        return await call_next(request)

    body = await request.body()
    request.state.raw_body = body

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # type: ignore[attr-defined]
    return await call_next(request)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    """处理 ValueError 并返回统一格式"""
    return bad_request_response(str(exc))


@app.exception_handler(AuthenticationException)
async def authentication_error_handler(_: Request, exc: AuthenticationException):
    """处理 AuthenticationException 并返回统一格式"""
    return unauthorized_response(str(exc))


@app.exception_handler(PermissionException)
async def permission_error_handler(_: Request, exc: PermissionException):
    """处理 PermissionException 并返回统一格式"""
    return forbidden_response(str(exc))


@app.exception_handler(NotFoundException)
async def notfound_error_handler(_: Request, exc: NotFoundException):
    """处理 NotFoundException 并返回统一格式"""
    return not_found_response(str(exc))


@app.exception_handler(Exception)
async def general_exception_handler(_: Request, exc: Exception):
    """处理所有未捕获的异常"""
    # 对于 StreamingResponse 相关的 ASGI 协议错误，不做处理，让连接自然关闭
    if isinstance(exc, (RuntimeError, ExceptionGroup)):
        exc_str = str(exc)
        if "Unexpected message" in exc_str or "StreamingResponse" in exc_str:
            logger.debug(f"StreamingResponse connection closed: {exc}")
            # 这是正常的流关闭，不做任何处理
            raise exc

    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    # 生产环境不暴露详细错误（通过环境变量判断）
    is_dev = os.getenv("ENV", "production").lower() in ("development", "dev", "local")

    # server_error_response 已经返回 JSONResponse，直接返回即可
    if is_dev:
        return server_error_response("服务器内部错误", {"detail": str(exc)})
    else:
        return server_error_response("服务器内部错误")


async def init_db() -> None:
    """初始化数据库：确保表存在，可选清空旧表"""
    if settings.auto_create_db:
        # 🗑️ 开发模式：每次启动都清空所有表
        print("⚠️  清空所有表...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        print("✅ 所有表已清空")

    # 🏗️ 确保所有表存在（如果不存在则创建）
    print("📦 确保表结构存在...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 表结构已就绪")

    # 👤 确保管理员账号存在
    async with AsyncSessionLocal() as db:
        await bootstrap_admin(db)


def init_files() -> None:
    ensure_dir(settings.data_dir)
    app.mount("/files", StaticFiles(directory=settings.data_dir), name="files")


@app.on_event("startup")
async def _startup():
    await init_db()
    init_files()


app.include_router(account_router)
app.include_router(subscription_router)
app.include_router(api_keys_router)
app.include_router(credits_router)
app.include_router(invite_codes_router)
app.include_router(console_router)
app.include_router(voices_console_router)
app.include_router(voices_openapi_router)
app.include_router(tts_console_router)
app.include_router(tts_openapi_router)
app.include_router(clone_console_router)
app.include_router(clone_openapi_router)
