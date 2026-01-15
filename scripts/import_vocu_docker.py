#!/usr/bin/env python3
"""
Docker环境下导入Vocu.ai语音数据到数据库
用法: 在 Docker 容器内执行此脚本
"""

import os
import sys
import json
import asyncio
import shutil
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, "/app")

# Docker环境下的数据库配置（从环境变量获取）
# 数据库连接会自动从 docker-compose.yml 中的环境变量读取

from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.core.models import User, Voice, CloneJob, JobStatus

# 配置
ADMIN_EMAIL = "admin@autogame.ai"
VOCU_DATA_DIR = Path("/app/vocu_data")  # Docker容器内的路径
VOCU_DATA_JSON = VOCU_DATA_DIR / "voices_data.json"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))  # 实际数据目录


def copy_avatar_files():
    """复制头像文件从 vocu_data 到 data 目录"""
    src_avatars_dir = VOCU_DATA_DIR / "avatars"  # 头像直接在 avatars 下
    dest_avatars_dir = DATA_DIR / "avatars" / "vocu"  # 目标在 avatars/vocu 下

    if not src_avatars_dir.exists():
        print(f"⚠️  源头像目录不存在: {src_avatars_dir}")
        return 0

    # 确保目标目录存在
    dest_avatars_dir.mkdir(parents=True, exist_ok=True)

    # 复制所有头像文件
    copied = 0
    for avatar_file in src_avatars_dir.glob("*.webp"):
        dest_file = dest_avatars_dir / avatar_file.name
        shutil.copy2(avatar_file, dest_file)
        copied += 1

    return copied


def copy_preview_audio_files(voices_data):
    """复制预览音频文件"""
    src_audio_dir = VOCU_DATA_DIR / "audio"

    if not src_audio_dir.exists():
        print(f"⚠️  源音频目录不存在: {src_audio_dir}")
        return 0

    copied = 0
    for voice_data in voices_data:
        original_id = voice_data.get("id")
        avatar_url = voice_data.get("avatar_url", "")

        if not original_id or not avatar_url:
            continue

        # 从 avatar_url 中提取 UUID
        # 格式: /files/avatars/vocu/d876307a-7769-4345-be6a-05b5976ac758.webp
        try:
            audio_uuid = avatar_url.split("/")[-1].replace(".webp", "")
        except:
            continue

        # 查找匹配的音频文件 (格式: {audio_uuid}_default.mp3)
        src_audio_file = src_audio_dir / f"{audio_uuid}_default.mp3"
        if not src_audio_file.exists():
            continue

        # 目标路径: /data/clone/1_{original_id}/preview.wav
        dest_dir = DATA_DIR / "clone" / f"1_{original_id}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / "preview.wav"

        shutil.copy2(src_audio_file, dest_file)
        copied += 1

    return copied


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

    # 兼容两种格式：直接数组或 {"data": [...]}
    voices_data = data if isinstance(data, list) else data["data"]

    print("\n" + "=" * 70)
    print("🚀 开始导入语音数据到数据库")
    print("=" * 70)
    print(f"📊 总计: {len(voices_data)} 个语音角色")

    # 复制头像文件
    print("\n📸 复制头像文件...")
    copied_count = copy_avatar_files()
    print(f"✅ 已复制 {copied_count} 个头像文件")

    # 复制预览音频文件
    print("\n🎵 复制预览音频文件...")
    audio_copied_count = copy_preview_audio_files(voices_data)
    print(f"✅ 已复制 {audio_copied_count} 个预览音频文件\n")

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
            original_id = voice_data.get("id")
            name = voice_data.get("name")

            # 跳过没有必要字段的记录
            if not original_id or not name:
                skipped += 1
                continue

            if imported % 20 == 0 and imported > 0:
                print(f"[进度] 已导入 {imported} 个...")

            try:
                # 检查是否已存在（避免重复导入和外键冲突）
                result = await session.execute(
                    select(CloneJob).where(CloneJob.uuid == original_id)
                )
                existing_clone_job = result.scalar_one_or_none()
                if existing_clone_job:
                    skipped += 1
                    continue
                # 处理 preview_audio_url: 从 /files/... 转换为本地路径
                preview_audio_url = voice_data.get("preview_audio_url", "")
                preview_audio_path = ""
                if preview_audio_url and preview_audio_url.startswith("/files/"):
                    # 转换 /files/xxx 为 DATA_DIR/xxx
                    preview_audio_path = str(
                        DATA_DIR / preview_audio_url.replace("/files/", "")
                    )

                avatar_url = voice_data.get("avatar_url", "")
                description = voice_data.get("description", "")
                tags = voice_data.get("tags", [])
                
                # description 现在支持多语言格式（简体|繁体|日语|韩语|英语）
                # 数据库字段已扩展到 VARCHAR(2000) 以支持完整的多语言内容

                # 先创建 CloneJob 记录（TTS 接口需要查找这个）
                clone_job = CloneJob(
                    uuid=original_id,
                    user_id=admin_user.id,
                    voice_name=name,
                    avatar_url=avatar_url,
                    description=description,
                    tags=tags,
                    is_public=True,
                    remove_background_noise=False,
                    status=JobStatus.succeeded,  # 已成功克隆
                    error="",
                    dataset_dir="",
                    result_voice_uuid=original_id,  # 指向生成的 Voice
                    external_request_id="",
                )
                session.add(clone_job)
                await session.flush()

                # 创建Voice记录
                # uuid 和 clone_job_uuid 都使用原数据的 id
                voice = Voice(
                    uuid=original_id,
                    owner_user_id=admin_user.id,
                    name=name,
                    avatar_url=avatar_url,
                    description=description,
                    tags=tags,
                    is_public=True,
                    preview_audio_path=preview_audio_path,
                    clone_job_uuid=original_id,
                    likes_count=voice_data.get("likes_count", 0),
                    generated_chars_count=voice_data.get("generated_chars_count", 0),
                    usage_count=voice_data.get("usage_count", 0),
                )
                session.add(voice)
                await session.flush()
                
                # 提交事务
                await session.commit()

                imported += 1

            except Exception as e:
                await session.rollback()
                print(f"  ❌ [{i}] {name}: {e}")
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
