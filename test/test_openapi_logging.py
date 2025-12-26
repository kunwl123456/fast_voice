"""
OpenAPI 请求日志中间件测试
测试以 /openapi 开头的请求是否会被正确记录
"""

import asyncio
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.models import ApiRequestLog, ApiKey, User


async def test_openapi_logging():
    """测试 OpenAPI 日志记录功能"""
    db = AsyncSessionLocal()

    try:
        # 1. 查询是否有测试用户
        user = (await db.execute(select(User).limit(1))).scalar_one_or_none()

        if not user:
            print("❌ 没有找到用户，请先运行应用创建用户")
            return

        # 2. 查询该用户的 API Key
        api_key = (
            await db.execute(select(ApiKey).where(ApiKey.user_id == user.id).limit(1))
        ).scalar_one_or_none()

        if not api_key:
            print("❌ 没有找到 API Key，请先为用户创建 API Key")
            return

        print(f"✅ 找到用户: {user.email}")
        print(f"✅ 找到 API Key: {api_key.api_key[:20]}...")

        # 3. 查询最近的 OpenAPI 请求日志
        logs = (
            (
                await db.execute(
                    select(ApiRequestLog)
                    .where(ApiRequestLog.user_id == user.id)
                    .order_by(ApiRequestLog.created_at.desc())
                    .limit(5)
                )
            )
            .scalars()
            .all()
        )

        if not logs:
            print("\n📝 暂无 OpenAPI 请求日志")
            print("💡 请使用以下命令测试：")
            print(
                f'   curl -H "Authorization: Bearer {api_key.api_key}" http://localhost:8000/openapi/v1/voices'
            )
            return

        print(f"\n📊 最近 {len(logs)} 条 OpenAPI 请求日志：")
        print("-" * 80)
        for log in logs:
            print(f"时间: {log.created_at}")
            print(f"路径: {log.endpoint}")
            print(f"方法: {log.method}")
            print(f"状态: {log.status_code}")
            print(f"延迟: {log.latency_ms}ms")
            print(f"响应大小: {log.response_size} bytes")
            if log.error_message:
                print(f"错误: {log.error_message}")
            print("-" * 80)

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(test_openapi_logging())
