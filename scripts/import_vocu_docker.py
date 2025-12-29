#!/usr/bin/env python3
"""
Docker环境下导入Vocu.ai语音数据到数据库
用法: 在 Docker 容器内执行此脚本
"""

import os
import sys
import json
import asyncio
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, '/app')

from sqlalchemy import select

# Docker环境下的数据库配置（从环境变量获取）
# 数据库连接会自动从 docker-compose.yml 中的环境变量读取

from app.core.db import AsyncSessionLocal
from app.core.models import User, Voice, CloneJob

# 配置
ADMIN_EMAIL = "admin@autogame.ai"
VOCU_DATA_DIR = Path("/app/vocu_data")  # Docker容器内的路径
VOCU_DATA_JSON = VOCU_DATA_DIR / "voices_data.json"


async def import_voices():
    """导入语音到数据库"""
    
    # 检查数据文件是否存在
    if not VOCU_DATA_JSON.exists():
        print(f"❌ 找不到数据文件: {VOCU_DATA_JSON}")
        print("请确保 vocu_data 文件夹已挂载到容器中")
        return
    
    # 读取数据
    print(f"📖 读取数据文件: {VOCU_DATA_JSON}")
    with open(VOCU_DATA_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    voices_data = data["data"]

    print("\n" + "=" * 70)
    print("🚀 开始导入语音数据到数据库")
    print("=" * 70)
    print(f"📊 总计: {len(voices_data)} 个语音角色")

    async with AsyncSessionLocal() as session:
        # 获取admin用户
        result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
        admin_user = result.scalar_one_or_none()

        if not admin_user:
            print(f"❌ 找不到用户: {ADMIN_EMAIL}")
            print("请确保管理员账号已创建")
            return

        print(f"✅ 找到管理员用户: {admin_user.email} (ID: {admin_user.id})\n")

        imported = 0
        failed = 0
        skipped = 0

        for i, voice_data in enumerate(voices_data, 1):
            clone_job_uuid = voice_data["id"]
            name = voice_data["name"]

            print(f"[{i}/{len(voices_data)}] 📥 处理: {name}")

            try:
                # 检查CloneJob是否存在
                result = await session.execute(
                    select(CloneJob).where(CloneJob.uuid == clone_job_uuid)
                )
                clone_job = result.scalar_one_or_none()

                if not clone_job:
                    # CloneJob不存在，创建一个
                    print("  📝 创建 CloneJob...")
                    clone_job = CloneJob(
                        uuid=clone_job_uuid,
                        user_id=admin_user.id,
                        voice_name=name,
                        avatar_url=voice_data.get("avatar_url", ""),
                        description=voice_data.get("description", ""),
                        tags=voice_data.get("tags", []),
                        is_public=voice_data.get("is_public", True),
                        status="succeeded",  # 标记为已完成
                        dataset_dir=voice_data.get("preview_audio_url", "").replace(
                            "/files/", ""
                        ),
                    )
                    session.add(clone_job)
                    await session.flush()

                # 检查是否已经有关联的Voice
                if clone_job.result_voice_uuid:
                    print("  ⏭️  已存在，跳过")
                    skipped += 1
                    continue

                # 创建Voice记录
                voice = Voice(
                    owner_user_id=admin_user.id,
                    name=name,
                    avatar_url=voice_data.get("avatar_url", ""),
                    description=voice_data.get("description", ""),
                    tags=voice_data.get("tags", []),
                    is_public=voice_data.get("is_public", True),
                    preview_audio_path=voice_data.get("preview_audio_url", "").replace(
                        "/files/", ""
                    ),
                    clone_job_uuid=clone_job_uuid,
                    likes_count=voice_data.get("likes_count", 0),
                    generated_chars_count=voice_data.get("generated_chars_count", 0),
                    usage_count=voice_data.get("usage_count", 0),
                )

                session.add(voice)
                await session.flush()

                # 更新CloneJob的result_voice_uuid
                clone_job.result_voice_uuid = voice.uuid

                await session.commit()

                print(f"  ✅ 成功 - Voice UUID: {voice.uuid}")
                imported += 1

            except Exception as e:
                await session.rollback()
                print(f"  ❌ 失败: {e}")
                failed += 1

    print("\n" + "=" * 70)
    print("✨ 导入完成！")
    print(f"  ✅ 成功: {imported} 个")
    print(f"  ⏭️  跳过: {skipped} 个")
    print(f"  ❌ 失败: {failed} 个")
    print("=" * 70)


def main():
    asyncio.run(import_voices())


if __name__ == "__main__":
    main()

