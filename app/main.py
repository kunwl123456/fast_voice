from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db import Base, engine, AsyncSessionLocal
from app.models import *  # noqa: F401,F403 (ensure models imported for metadata)
from app.routes.clone import console_router as clone_console_router
from app.routes.clone import openapi_router as clone_openapi_router
from app.routes.console import router as console_router
from app.routes.openapi_docs import router as openapi_docs_router
from app.routes.tts import console_router as tts_console_router
from app.routes.tts import openapi_router as tts_openapi_router
from app.routes.voices import console_router as voices_console_router
from app.routes.voices import openapi_router as voices_openapi_router
from app.services.bootstrap import bootstrap_admin
from app.services.storage import ensure_dir


app = FastAPI(title="fast_voice", version="0.1.0")


@app.middleware("http")
async def capture_raw_body(request: Request, call_next):
    """
    OpenAPI 签名需要“原始 body bytes”的 sha256，因此这里缓存 raw body 到 request.state。
    """
    body = await request.body()
    request.state.raw_body = body

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # type: ignore[attr-defined]
    return await call_next(request)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def init_db() -> None:
    if not settings.auto_create_db:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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


