#!/usr/bin/env python3
"""
为音频文件创建克隆任务
该脚本会：
1. 读取 vocu_data/voices_data.json 的数据
2. 通过 HTTP API 上传音频文件创建音频特征
3. 等待克隆任务完成（顺序执行，一个完成后再执行下一个）
4. 生成新的 UUID 并保存到 voices_data.json

用法: python scripts/create_real_audio_clones.py
"""

import json
import uuid
import asyncio
import aiohttp
from pathlib import Path

# 配置
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
VOCU_DATA_DIR = PROJECT_ROOT / "vocu_data"
VOCU_DATA_JSON = VOCU_DATA_DIR / "voices_data.json"
API_BASE_URL = "http://192.168.1.5:4000"  # 音频创建 API


async def create_voice_via_api(session: aiohttp.ClientSession, voice_data: dict) -> str:
    """通过 API 创建音频特征"""
    name = voice_data.get("name")
    
    # 获取音频文件路径
    preview_audio_url = voice_data.get("preview_audio_url", "")
    if preview_audio_url.startswith("audio/"):
        audio_file = preview_audio_url.replace("audio/", "")
    else:
        audio_file = f"{name}.mp3"
    
    audio_path = VOCU_DATA_DIR / "audio" / audio_file
    if not audio_path.exists():
        raise Exception(f"音频文件不存在: {audio_path}")
    
    # 生成新的 UUID
    new_voice_id = str(uuid.uuid4())
    
    print(f"    📤 上传音频文件: {audio_file}")
    print(f"    🆔 新 ID: {new_voice_id}")
    
    # 准备表单数据
    data = aiohttp.FormData()
    data.add_field('id', new_voice_id)
    
    # 上传音频文件
    with open(audio_path, 'rb') as f:
        data.add_field('file', f, 
                      filename=audio_file,
                      content_type='audio/mpeg')
        
        response = await session.post(
            f"{API_BASE_URL}/create_voice",
            data=data
        )
    
    if response.status != 200:
        error_text = await response.text()
        raise Exception(f"API 请求失败 ({response.status}): {error_text}")
    
    result = await response.json()
    message = result.get("message", "")
    returned_id = result.get("id", "")
    
    print(f"    ✅ {message}")
    
    return new_voice_id


async def create_real_audio_clones():
    """通过 API 创建音频特征（顺序执行）"""

    if not VOCU_DATA_JSON.exists():
        print(f"❌ 找不到数据文件: {VOCU_DATA_JSON}")
        return

    print(f"📖 读取数据文件: {VOCU_DATA_JSON}")
    with open(VOCU_DATA_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 兼容两种格式：直接数组或 {"data": [...]}
    voices_data = data.get("data", data) if isinstance(data, dict) else data

    print("\n" + "=" * 70)
    print("🚀 开始通过 API 创建音频特征")
    print("=" * 70)
    print(f"📊 总计: {len(voices_data)} 个语音角色")
    print(f"🌐 API 地址: {API_BASE_URL}/create_voice")
    print("⚠️  注意: 将顺序执行，每个任务完成后再执行下一个\n")

    created = 0
    failed = 0
    updated_voices = []

    # 创建 HTTP 会话
    async with aiohttp.ClientSession() as session:
        for i, voice_data in enumerate(voices_data, 1):
            name = voice_data.get("name")
            old_id = voice_data.get("id")

            if not name:
                print(f"[{i}/{len(voices_data)}] ⚠️  跳过: 缺少名称")
                updated_voices.append(voice_data)
                continue

            print(f"\n[{i}/{len(voices_data)}] 正在处理: {name}")
            print("=" * 50)
            print(f"  旧 ID: {old_id}")

            try:
                # 通过 API 创建音频特征
                print(f"  🎤 开始创建音频特征...")
                new_voice_id = await create_voice_via_api(session, voice_data)

                # 更新数据
                voice_data["id"] = new_voice_id
                updated_voices.append(voice_data)

                print(f"  ✅ 成功创建！")
                created += 1

            except Exception as e:
                print(f"  ❌ 失败: {str(e)}")
                import traceback
                traceback.print_exc()
                failed += 1
                # 失败时保留原数据
                updated_voices.append(voice_data)

    # 保存更新后的JSON
    print("\n" + "=" * 70)
    print("📝 更新 voices_data.json 文件...")
    
    # 保持原有的结构
    if isinstance(data, dict) and "message" in data:
        output_data = {
            "message": data["message"],
            "data": updated_voices
        }
    else:
        output_data = updated_voices
    
    with open(VOCU_DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("✨ 完成！")
    print(f"  ✅ 成功创建: {created} 个")
    print(f"  ❌ 失败: {failed} 个")
    print(f"  📄 已更新: {VOCU_DATA_JSON}")
    print("=" * 70)


def main():
    asyncio.run(create_real_audio_clones())


if __name__ == "__main__":
    main()
