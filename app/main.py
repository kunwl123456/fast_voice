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
from app.views.console import router as console_router
from app.views.account import router as account_router
from app.views.subscription import router as subscription_router
from app.views.api_keys import router as api_keys_router
from app.views.credits import router as credits_router
from app.views.tts import console_router as tts_console_router
from app.views.tts import openapi_router as tts_openapi_router
from app.views.clone import console_router as clone_console_router
from app.views.clone import openapi_router as clone_openapi_router
from app.views.voices import console_router as voices_console_router
from app.views.voices import openapi_router as voices_openapi_router


app = FastAPI(
    title="FastVoice API Document",
    version="0.1.0",
    description="""
# API 说明

## 认证方式

### JWT Token 认证（控制台）
```
Authorization: Bearer <access_token>
```

### API Key 认证（企业版 OpenAPI）
```
Authorization: Bearer <api_key>
```

## 响应说明

### 响应格式
所有接口均返回统一格式：
```json
{
  "message": "提示信息",
  "data": {} // 响应数据或错误详情
}
```

### HTTP 状态码说明

| 状态码 | 说明 | 示例场景 |
|--------|------|----------|
| 200 | 请求成功 | 数据查询、更新、删除成功 |
| 201 | 创建成功 | 资源创建成功 |
| 400 | 请求参数错误 | 参数错误，例如缺少必需参数、参数格式错误 |
| 401 | 未授权 | 未登录、token 无效或过期 |
| 403 | 无权限 | 没有操作权限 |
| 404 | 资源不存在 | 请求的资源未找到 |
| 409 | 资源冲突 | 邮箱已注册、资源已存在 |
| 422 | 参数验证失败 | 字段验证不通过 |
| 500 | 服务器内部错误 | 系统异常 |

### 错误响应示例

**400 错误请求**
```json
{
  "message": "请求参数错误",
  "data": null
}
```

**403 无权限**
```json
{
  "message": "无权限访问该资源",
  "data": null
}
```

## 数据格式规范

### 时间格式
所有时间字段统一使用以下格式：
```
YYYY-MM-DD HH:MM:SS
示例：2025-12-25 12:00:00
```
""",
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
app.include_router(console_router)
app.include_router(voices_console_router)
app.include_router(voices_openapi_router)
app.include_router(tts_console_router)
app.include_router(tts_openapi_router)
app.include_router(clone_console_router)
app.include_router(clone_openapi_router)
