from __future__ import annotations

import os
from loguru import logger
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.models import *  # noqa: F401,F403 (ensure models imported for metadata)
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
from app.routes.console import router as console_router
from app.routes.tts import console_router as tts_console_router
from app.routes.tts import openapi_router as tts_openapi_router
from app.routes.openapi_docs import router as openapi_docs_router
from app.routes.clone import console_router as clone_console_router
from app.routes.clone import openapi_router as clone_openapi_router
from app.routes.voices import console_router as voices_console_router
from app.routes.voices import openapi_router as voices_openapi_router


# 定义 OpenAPI tags 元数据
tags_metadata = [
    {
        "name": "tts",
        "description": "文本转语音服务，支持异步任务和实时流式输出",
    },
    {
        "name": "clone",
        "description": "音色克隆服务，通过上传音频文件创建自定义音色",
    },
    {
        "name": "voices",
        "description": "音色管理服务，包括我的音色、公开音色列表等",
    },
]

app = FastAPI(
    title="fast_voice",
    version="0.1.0",
    openapi_tags=tags_metadata,
)


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
    """初始化数据库：清空旧表 -> 创建新表 -> 创建管理员"""
    if not settings.auto_create_db:
        return

    # 🗑️ 每次启动都清空所有表（开发环境）
    print("⚠️  清空所有表...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("✅ 所有表已清空")

    # 🏗️ 重新创建所有表
    print("📦 重新创建表结构...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 表结构创建完成")

    # 👤 创建管理员账号
    async with AsyncSessionLocal() as db:
        await bootstrap_admin(db)


def init_files() -> None:
    ensure_dir(settings.data_dir)
    app.mount("/files", StaticFiles(directory=settings.data_dir), name="files")


@app.on_event("startup")
async def _startup():
    await init_db()
    init_files()


app.include_router(console_router)
app.include_router(voices_console_router)
app.include_router(voices_openapi_router)
app.include_router(tts_console_router)
app.include_router(tts_openapi_router)
app.include_router(clone_console_router)
app.include_router(clone_openapi_router)
app.include_router(openapi_docs_router)
