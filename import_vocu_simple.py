#!/usr/bin/env python3
"""
直接导入Vocu.ai语音数据到数据库
"""

import os
import json
import asyncio
from pathlib import Path
from sqlalchemy import select

# ⚠️ 必须在导入 app 模块之前设置环境变量
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/fast_voice"

from app.db import AsyncSessionLocal
from app.models import User, Voice, CloneJob

# 配置
ADMIN_EMAIL = "admin@autogame.ai"
VOCU_DATA_DIR = Path("vocu_data")
VOCU_DATA_JSON = VOCU_DATA_DIR / "voices_data.json"


async def import_voices():
    """导入语音到数据库"""
    # 读取数据
    with open(VOCU_DATA_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    voices_data = data['data']
    
    print("\n" + "=" * 70)
    print("开始导入语音数据到数据库")
    print("=" * 70)
    
    async with AsyncSessionLocal() as session:
        # 获取admin用户
        result = await session.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        )
        admin_user = result.scalar_one_or_none()
        
        if not admin_user:
            print(f"❌ 找不到用户: {ADMIN_EMAIL}")
            return
        
        print(f"✅ 找到管理员用户: {admin_user.email} (ID: {admin_user.id})")
        
        imported = 0
        failed = 0
        skipped = 0
        
        for i, voice_data in enumerate(voices_data, 1):
            clone_job_uuid = voice_data['id']
            name = voice_data['name']
            
            print(f"\n[{i}/{len(voices_data)}] 📥 导入: {name}")
            print(f"  🔑 CloneJob UUID: {clone_job_uuid}")
            
            try:
                # 检查CloneJob是否存在
                result = await session.execute(
                    select(CloneJob).where(CloneJob.uuid == clone_job_uuid)
                )
                clone_job = result.scalar_one_or_none()
                
                if not clone_job:
                    # CloneJob不存在，创建一个
                    print(f"  📝 CloneJob不存在，创建中...")
                    clone_job = CloneJob(
                        uuid=clone_job_uuid,
                        user_id=admin_user.id,  # 修正字段名
                        voice_name=name,
                        avatar_url=voice_data.get('avatar_url', ''),
                        description=voice_data.get('description', ''),
                        tags=voice_data.get('tags', []),
                        is_public=voice_data.get('is_public', True),
                        status='succeeded',  # 标记为已完成
                        dataset_dir=voice_data.get('preview_audio_url', '').replace('/files/', ''),
                    )
                    session.add(clone_job)
                    await session.flush()
                    print(f"  ✅ 创建CloneJob: {clone_job.uuid}")
                
                # 检查是否已经有关联的Voice
                if clone_job.result_voice_uuid:  # 修正字段名
                    print(f"  ⚠️  CloneJob已关联Voice，跳过")
                    skipped += 1
                    continue
                
                # 创建Voice记录
                voice = Voice(
                    owner_user_id=admin_user.id,
                    name=name,
                    avatar_url=voice_data.get('avatar_url', ''),
                    description=voice_data.get('description', ''),
                    tags=voice_data.get('tags', []),
                    is_public=voice_data.get('is_public', True),
                    preview_audio_path=voice_data.get('preview_audio_url', '').replace('/files/', ''),
                    clone_job_uuid=clone_job_uuid,
                    likes_count=voice_data.get('likes_count', 0),
                    generated_chars_count=voice_data.get('generated_chars_count', 0),
                    usage_count=voice_data.get('usage_count', 0),
                )
                
                session.add(voice)
                await session.flush()
                
                # 更新CloneJob的result_voice_uuid
                clone_job.result_voice_uuid = voice.uuid  # 修正字段名
                
                await session.commit()
                
                print(f"  ✅ 成功创建Voice: {voice.uuid}")
                print(f"  🏷️  标签: {voice.tags[:5]}{'...' if len(voice.tags) > 5 else ''}")
                imported += 1
                
            except Exception as e:
                await session.rollback()
                print(f"  ❌ 异常: {e}")
                failed += 1
    
    print("\n" + "=" * 70)
    print("导入完成！")
    print(f"  ✅ 成功: {imported} 个")
    print(f"  ⚠️  跳过: {skipped} 个")
    print(f"  ❌ 失败: {failed} 个")
    print("=" * 70)


def main():
    asyncio.run(import_voices())


if __name__ == '__main__':
    main()

