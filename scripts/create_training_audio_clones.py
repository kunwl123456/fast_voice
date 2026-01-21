#!/usr/bin/env python3
"""
为 training_data_converted/voices_data.json 创建真实音频克隆任务
该脚本会：
1. 读取 training_data_converted/voices_data.json
2. 通过 HTTP API 上传音频文件创建音频特征
3. 顺序执行，成功后仅更新 clone_job_uuid（保留原有 id）

用法: python scripts/create_training_audio_clones.py
"""

import asyncio
import json
import uuid
from pathlib import Path

import aiohttp

# 配置
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
TRAINING_DATA_DIR = PROJECT_ROOT / "training_data_converted"
TRAINING_DATA_JSON = TRAINING_DATA_DIR / "voices_data.json"
AUDIO_DIR = TRAINING_DATA_DIR / "audios"
API_BASE_URL = "http://192.168.1.5:4000"  # 音频创建 API


async def create_voice_via_api(session: aiohttp.ClientSession, audio_path: Path) -> str:
    """通过 API 创建音频特征，返回真实音频 ID"""
    # 生成用于音频服务的真实 ID
    real_audio_id = str(uuid.uuid4())

    print(f"    📤 上传音频文件: {audio_path.name}")
    print(f"    🆔 真实音频 ID: {real_audio_id}")

    data = aiohttp.FormData()
    data.add_field("id", real_audio_id)

    with open(audio_path, "rb") as f:
        data.add_field(
            "file",
            f,
            filename=audio_path.name,
            content_type="audio/mpeg",
        )
        response = await session.post(f"{API_BASE_URL}/create_voice", data=data)

    if response.status != 200:
        error_text = await response.text()
        raise Exception(f"API 请求失败 ({response.status}): {error_text}")

    result = await response.json()
    message = result.get("message", "")
    returned_id = result.get("id")

    print(f"    ✅ {message}")

    # 优先使用返回值（如果有）
    return returned_id or real_audio_id


async def create_training_audio_clones():
    """通过 API 创建音频特征（顺序执行）"""
    if not TRAINING_DATA_JSON.exists():
        print(f"❌ 找不到数据文件: {TRAINING_DATA_JSON}")
        return

    print(f"📖 读取数据文件: {TRAINING_DATA_JSON}")
    with open(TRAINING_DATA_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

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

    async with aiohttp.ClientSession() as session:
        for i, voice_data in enumerate(voices_data, 1):
            name = voice_data.get("name")
            voice_id = voice_data.get("id")
            audio_file = voice_data.get("audio_file")

            if not name:
                print(f"[{i}/{len(voices_data)}] ⚠️  跳过: 缺少名称")
                updated_voices.append(voice_data)
                continue

            if not audio_file:
                print(f"[{i}/{len(voices_data)}] ⚠️  跳过: 缺少 audio_file")
                updated_voices.append(voice_data)
                continue

            audio_path = AUDIO_DIR / audio_file
            if not audio_path.exists():
                print(
                    f"[{i}/{len(voices_data)}] ❌ 找不到音频文件: {audio_path}"
                )
                updated_voices.append(voice_data)
                continue

            print(f"\n[{i}/{len(voices_data)}] 正在处理: {name}")
            print("=" * 50)
            print(f"  保留 ID: {voice_id}")

            try:
                print("  🎤 开始创建音频特征...")
                real_audio_id = await create_voice_via_api(session, audio_path)

                voice_data["clone_job_uuid"] = real_audio_id
                updated_voices.append(voice_data)

                print("  ✅ 成功创建！")
                created += 1

            except Exception as e:
                print(f"  ❌ 失败: {str(e)}")
                import traceback

                traceback.print_exc()
                failed += 1
                updated_voices.append(voice_data)

    print("\n" + "=" * 70)
    print("📝 更新 voices_data.json 文件...")

    if isinstance(data, dict) and "message" in data:
        output_data = {"message": data["message"], "data": updated_voices}
    else:
        output_data = updated_voices

    with open(TRAINING_DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("✨ 完成！")
    print(f"  ✅ 成功创建: {created} 个")
    print(f"  ❌ 失败: {failed} 个")
    print(f"  📄 已更新: {TRAINING_DATA_JSON}")
    print("=" * 70)


def main():
    asyncio.run(create_training_audio_clones())


if __name__ == "__main__":
    main()
