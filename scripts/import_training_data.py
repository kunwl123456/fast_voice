#!/usr/bin/env python3
"""
导入 FGO training_data 转换后的语音数据到数据库
用法: 在 Docker 容器内执行此脚本
数据将导入到社区市场（/console/voices/public）
所有语音将归属于 "FGO Dataset" 作者
"""

import os
import sys
import json
import asyncio
import shutil
from pathlib import Path
from typing import Dict

# 添加项目根目录到 Python 路径
sys.path.insert(0, "/app")

from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.core.models import User, Voice, CloneJob, JobStatus

# 配置
TRAINING_DATA_CONVERTED_DIR = Path("/app/training_data_converted")  # Docker容器内的路径
TRAINING_DATA_JSON = TRAINING_DATA_CONVERTED_DIR / "voices_data.json"
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))  # 实际数据目录

# 用户缓存，避免重复查询
user_cache: Dict[str, User] = {}


def copy_voice_avatar_files():
    """复制语音角色头像文件从 training_data_converted 到 data 目录"""
    src_avatars_dir = TRAINING_DATA_CONVERTED_DIR / "voice_avatars"
    dest_avatars_dir = DATA_DIR / "avatars" / "fgo_dataset"

    if not src_avatars_dir.exists():
        print(f"⚠️  源语音头像目录不存在: {src_avatars_dir}")
        return 0

    # 确保目标目录存在
    dest_avatars_dir.mkdir(parents=True, exist_ok=True)

    # 复制所有头像文件
    copied = 0
    for avatar_file in src_avatars_dir.glob("*_voice.webp"):
        dest_file = dest_avatars_dir / avatar_file.name
        if not dest_file.exists():  # 避免重复复制
            shutil.copy2(avatar_file, dest_file)
        copied += 1

    return copied


def copy_preview_audio_files(voices_data):
    """复制预览音频文件"""
    src_audio_dir = TRAINING_DATA_CONVERTED_DIR / "audios"

    if not src_audio_dir.exists():
        print(f"⚠️  源音频目录不存在: {src_audio_dir}")
        return 0

    copied = 0
    for voice_data in voices_data:
        clone_job_uuid = voice_data.get("clone_job_uuid")
        audio_file = voice_data.get("audio_file")

        if not clone_job_uuid or not audio_file:
            continue

        src_audio_file = src_audio_dir / audio_file
        if not src_audio_file.exists():
            print(f"  ⚠️  音频文件不存在: {audio_file}")
            continue

        # 目标路径: /data/clone/1_{clone_job_uuid}/preview.wav
        dest_dir = DATA_DIR / "clone" / f"1_{clone_job_uuid}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / "preview.wav"

        if not dest_file.exists():  # 避免重复复制
            shutil.copy2(src_audio_file, dest_file)
        copied += 1

    return copied


async def get_or_create_user(session, author_id: str, author_name: str) -> User:
    """获取或创建用户"""
    # 先从缓存获取
    if author_id in user_cache:
        return user_cache[author_id]

    # 查询数据库
    result = await session.execute(select(User).where(User.uuid == author_id))
    user = result.scalar_one_or_none()

    if not user:
        # 创建新用户
        email = f"fgo_dataset_{author_id}@tts.local"
        user = User(
            uuid=author_id,
            display_name=author_name,
            email=email,
            password_hash="",  # 这些用户不能登录，只是作为语音的所有者
            is_admin=False,
        )
        session.add(user)
        await session.flush()

    # 缓存用户
    user_cache[author_id] = user
    return user


async def import_training_voices():
    """导入 FGO training_data 转换后的语音到数据库"""

    # 检查数据文件是否存在
    if not TRAINING_DATA_JSON.exists():
        print(f"❌ 找不到数据文件: {TRAINING_DATA_JSON}")
        print("请确保 training_data_converted 文件夹已挂载到容器中")
        return

    # 读取数据
    print(f"📖 读取数据文件: {TRAINING_DATA_JSON}")
    with open(TRAINING_DATA_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 兼容两种格式：直接数组或 {"data": [...]}
    voices_data = data if isinstance(data, list) else data.get("data", [])

    print("\n" + "=" * 70)
    print("🚀 开始导入 FGO 训练数据集语音到数据库")
    print("=" * 70)
    print(f"📊 总计: {len(voices_data)} 个语音角色")

    # 复制语音头像文件
    print("\n📸 复制语音头像文件...")
    copied_count = copy_voice_avatar_files()
    print(f"✅ 已复制 {copied_count} 个语音头像文件")

    # 复制预览音频文件
    print("\n🎵 复制预览音频文件...")
    audio_copied_count = copy_preview_audio_files(voices_data)
    print(f"✅ 已复制 {audio_copied_count} 个预览音频文件\n")

    async with AsyncSessionLocal() as session:
        print("开始导入 FGO 训练数据集语音...\n")

        imported = 0
        failed = 0
        skipped = 0
        created_users = 0

        for i, voice_data in enumerate(voices_data, 1):
            clone_job_uuid = voice_data.get("clone_job_uuid")
            vocu_original_id = voice_data.get("vocu_original_id")
            name = voice_data.get("name")
            author_id = voice_data.get("author_id")
            author_name = voice_data.get("author_name", "FGO Dataset")

            # 跳过没有必要字段的记录
            if not clone_job_uuid or not name or not author_id:
                skipped += 1
                continue

            if imported % 5 == 0 and imported > 0:
                print(f"[进度] 已导入 {imported} 个...")

            try:
                # 检查是否已存在（避免重复导入）
                result = await session.execute(
                    select(CloneJob).where(CloneJob.uuid == clone_job_uuid)
                )
                existing_clone_job = result.scalar_one_or_none()
                if existing_clone_job:
                    skipped += 1
                    continue

                # 获取或创建作者用户
                is_new_user = author_id not in user_cache
                author_user = await get_or_create_user(session, author_id, author_name)
                if is_new_user:
                    created_users += 1

                # 检查该用户是否已有同名语音（避免唯一约束冲突）
                result = await session.execute(
                    select(Voice).where(
                        Voice.owner_user_id == author_user.id, Voice.name == name
                    )
                )
                existing_voice = result.scalar_one_or_none()
                if existing_voice:
                    # 同一作者已有同名语音，添加后缀区分
                    name = f"{name}_{vocu_original_id[:8]}"

                # 处理头像URL - 使用 voice_avatar_file，路径改为 fgo_dataset
                avatar_url = ""
                voice_avatar_file = voice_data.get("voice_avatar_file")
                if voice_avatar_file:
                    # 转换为本地路径格式
                    avatar_url = f"/files/avatars/fgo_dataset/{voice_avatar_file}"

                # 处理预览音频路径
                preview_audio_path = ""
                if clone_job_uuid:
                    preview_audio_path = f"clone/1_{clone_job_uuid}/preview.wav"

                description = voice_data.get("description", "")
                tags = voice_data.get("tags", [])

                # 获取统计数据
                likes_count = voice_data.get("likes", 0)
                usage_count = voice_data.get("usage_count", 0)
                generated_chars_count = voice_data.get("characters_used", 0)

                # 先创建 CloneJob 记录
                clone_job = CloneJob(
                    uuid=clone_job_uuid,
                    user_id=author_user.id,
                    voice_name=name,
                    avatar_url=avatar_url,
                    description=description,
                    tags=tags,
                    is_public=True,  # FGO 数据集的语音都是公开的
                    remove_background_noise=False,
                    status=JobStatus.succeeded,
                    error="",
                    dataset_dir="",
                    result_voice_uuid=vocu_original_id,
                    external_request_id="",
                )
                session.add(clone_job)

                # 创建 Voice 记录
                voice = Voice(
                    uuid=vocu_original_id,
                    owner_user_id=author_user.id,
                    name=name,
                    avatar_url=avatar_url,
                    description=description,
                    tags=tags,
                    is_public=True,
                    preview_audio_path=preview_audio_path,
                    clone_job_uuid=clone_job_uuid,
                    likes_count=likes_count,
                    generated_chars_count=generated_chars_count,
                    usage_count=usage_count,
                )
                session.add(voice)

                await session.flush()
                await session.commit()

                print(f"  ✅ [{i}/{len(voices_data)}] {name}")
                imported += 1

            except Exception as e:
                await session.rollback()
                print(f"  ❌ [{i}/{len(voices_data)}] {name}: {e}")
                failed += 1

    print("\n" + "=" * 70)
    print("✨ 导入完成！")
    print(f"  ✅ 成功导入语音: {imported} 个")
    print(f"  👥 创建用户: {created_users} 个")
    print(f"  ⏭️  跳过: {skipped} 个")
    print(f"  ❌ 失败: {failed} 个")
    print("=" * 70)
    print("\n💡 提示: 这些语音现在可以在社区市场 (/console/voices/public) 中查询到")


def main():
    asyncio.run(import_training_voices())


if __name__ == "__main__":
    main()
