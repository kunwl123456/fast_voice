#!/usr/bin/env python
"""
FastAPI 应用启动脚本
用于在本地开发环境中启动应用（非 Docker 环境）
使用方式: python run.py
"""
import os
from pathlib import Path
import uvicorn

if __name__ == "__main__":
    # ====================================================================
    # 设置环境变量（本地开发配置）
    # ====================================================================

    # 获取项目根目录
    PROJECT_ROOT = Path(__file__).parent.absolute()

    # 时区设置
    os.environ.setdefault("TZ", "Asia/Shanghai")

    # 数据库配置 (本地开发使用 localhost)
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/fast_voice",
    )
    os.environ.setdefault(
        "DATABASE_URL_SYNC",
        "postgresql+psycopg://postgres:postgres@localhost:5432/fast_voice",
    )
    os.environ.setdefault("DB_POOL_SIZE", "10")
    os.environ.setdefault("DB_MAX_OVERFLOW", "20")
    os.environ.setdefault("DB_POOL_TIMEOUT_SECONDS", "30")
    os.environ.setdefault("DB_POOL_RECYCLE_SECONDS", "1800")

    # Redis 配置 (本地开发使用 localhost)
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
    os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

    # JWT 密钥
    os.environ.setdefault("JWT_SECRET", "f77a006515c2020c609f248b31c56a09")

    # 数据目录
    os.environ.setdefault("DATA_DIR", str(PROJECT_ROOT / "data"))

    # 外部服务配置
    os.environ.setdefault("VOICE_SVC_BASE_URL", "http://192.168.1.5:4000")
    os.environ.setdefault("VOICE_TTS_BASE_URL", "http://192.168.1.5:7000")

    # 注册赠送积分
    os.environ.setdefault("REGISTER_FREE_POINT", "10000000")

    # 开发环境标识
    os.environ.setdefault("ENV", "development")

    # 自动创建数据库表
    os.environ.setdefault("AUTO_CREATE_DB", "false")

    # ====================================================================
    # 启动应用
    # ====================================================================

    print("=" * 70)
    print("🚀 正在启动 FastAPI 应用...")
    print("=" * 70)
    print(f"📊 数据库: {os.environ.get('DATABASE_URL')}")
    print(f"🔴 Redis: {os.environ.get('REDIS_URL')}")
    print(f"🌍 时区: {os.environ.get('TZ')}")
    print(f"📁 数据目录: {os.environ.get('DATA_DIR')}")
    print(f"🎯 环境: {os.environ.get('ENV')}")
    print(f"🔑 JWT Secret: {os.environ.get('JWT_SECRET')[:20]}...")
    print("=" * 70)

    # 创建数据目录（如果不存在）
    data_dir = Path(os.environ.get("DATA_DIR"))
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ 已创建数据目录: {data_dir}")

    # 启动 uvicorn 服务器
    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=9000, reload=True, log_level="info"
    )
