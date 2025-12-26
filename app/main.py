from __future__ import annotations

import os
from loguru import logger
from fastapi import FastAPI, Request
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.models import *  # noqa: F401,F403 (ensure models imported for metadata)
from app.core.config import settings
from app.core.error_codes import CommonError
from app.core.exceptions import AppException
from app.core.responses import error_response
from app.api.services.storage import ensure_dir
from app.api.services.bootstrap import bootstrap_admin
from app.core.db import Base, engine, AsyncSessionLocal
from app.core.middlewares import OpenAPILoggingMiddleware
from app.core.openapi import setup_openapi, OPENAPI_DESCRIPTION

# 从统一的路由注册中心导入所有路由
from app.routers import (
    account_router,
    api_keys_router,
    console_router,
    credits_router,
    subscription_router,
    clone_console_router,
    clone_openapi_router,
    tts_console_router,
    tts_openapi_router,
    voices_console_router,
    voices_openapi_router,
    admin_credit_router,
    admin_invite_codes_router,
    docs_router,
)

# 注册各个 views 模块的路由处理器
import app.api.views.account  # noqa: F401
import app.api.views.api_keys  # noqa: F401
import app.api.views.console  # noqa: F401
import app.api.views.credits  # noqa: F401
import app.api.views.subscription  # noqa: F401
import app.api.views.clone  # noqa: F401
import app.api.views.tts  # noqa: F401
import app.api.views.voices  # noqa: F401
import app.api.views.docs  # noqa: F401
import app.admin.views.credit  # noqa: F401
import app.admin.views.invite_codes  # noqa: F401


_app = FastAPI(
    title="FastVoice",
    version="0.1.0",
    description=OPENAPI_DESCRIPTION,
    # 配置 Bearer Token 认证
    swagger_ui_parameters={
        "persistAuthorization": True,  # 持久化认证信息（刷新页面后不需要重新输入）
    },
)

# 配置自定义 OpenAPI schema
setup_openapi(_app)

# 定义安全方案（用于在路由中引用，如果需要显示锁图标）
security = HTTPBearer(
    scheme_name="Bearer Authentication",
    description="输入你的 JWT Token 或 API Key（自动添加 'Bearer ' 前缀）",
)

_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加 OpenAPI 请求日志中间件
_app.add_middleware(OpenAPILoggingMiddleware)


@_app.middleware("http")
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


@_app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    """处理 ValueError 并返回统一格式"""
    return error_response(CommonError.BAD_REQUEST, message=str(exc))


@_app.exception_handler(AppException)
async def app_exception_handler(_: Request, exc: AppException):
    """
    统一处理所有业务异常（AppException 及其子类）

    包括：AuthenticationException, PermissionException, NotFoundException,
    BadRequestException, ConflictException, InternalServerException 等
    """
    return error_response(exc.error, message=exc.message, data=exc.data)


@_app.exception_handler(Exception)
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

    if is_dev:
        return error_response(CommonError.INTERNAL_ERROR, data={"detail": str(exc)})
    else:
        return error_response(CommonError.INTERNAL_ERROR)


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
    _app.mount("/files", StaticFiles(directory=settings.data_dir), name="files")


@_app.on_event("startup")
async def _startup():
    await init_db()
    init_files()


# 注册所有路由到应用
_app.include_router(account_router)
_app.include_router(subscription_router)
_app.include_router(api_keys_router)
_app.include_router(credits_router)
_app.include_router(admin_credit_router)
_app.include_router(admin_invite_codes_router)
_app.include_router(console_router)
_app.include_router(voices_console_router)
_app.include_router(voices_openapi_router)
_app.include_router(tts_console_router)
_app.include_router(tts_openapi_router)
_app.include_router(clone_console_router)
_app.include_router(clone_openapi_router)
_app.include_router(docs_router)

# 导出 app 实例供 uvicorn 使用
app = _app
