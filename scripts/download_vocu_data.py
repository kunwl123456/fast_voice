#!/usr/bin/env python3
"""
脚本用于从Vocu.ai下载语音数据和资源
包括：语音名字、头像图片、语音标签、音频文件
"""

import requests
import json
from pathlib import Path
from typing import List, Dict, Any
import time

# 配置
API_BASE = "https://v1.vocu.ai/api/market/voice"
OUTPUT_DIR = Path("vocu_data")
AVATARS_DIR = OUTPUT_DIR / "avatars"
AUDIO_DIR = OUTPUT_DIR / "audio"

# 创建目录
OUTPUT_DIR.mkdir(exist_ok=True)
AVATARS_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)


def fetch_voices() -> List[Dict[str, Any]]:
    """获取所有语音数据"""
    all_voices = []
    offset = 0
    limit = 20

    print("正在获取语音数据...")

    while True:
        params = {
            "limit": limit,
            "offset": offset,
            "status": "published",
            "type": "official",
            "orderBy": "likes",
            "excludeTags": "filter:special.nsfw",
            "excludeTagMode": "any",
        }

        try:
            response = requests.get(API_BASE, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data.get("data") or len(data["data"]) == 0:
                break

            voices = data["data"]
            all_voices.extend(voices)
            print(f"已获取 {len(all_voices)} 个语音...")

            if len(voices) < limit:
                break

            offset += limit

            # 安全限制
            if offset >= 200:
                break

            time.sleep(0.5)  # 避免请求过快

        except Exception as e:
            print(f"获取数据时出错: {e}")
            break

    print(f"总共获取到 {len(all_voices)} 个语音")
    return all_voices


def extract_chinese_name(description: str) -> str:
    """从描述中提取中文名字"""
    if not description:
        return ""

    # 描述格式通常是: "Name | English description | French... | Japanese... | 中文名 | 中文描述 | 繁体中文..."
    parts = description.split("|")
    for i, part in enumerate(parts):
        part = part.strip()
        # 查找包含中文的部分，且不是描述（通常中文名比较短）
        if any("\u4e00" <= c <= "\u9fff" for c in part) and len(part) < 20:
            return part

    return ""


def extract_tags_info(tags: List[Dict]) -> Dict[str, List[str]]:
    """提取并分类标签信息"""
    tag_categories = {
        "language": [],
        "gender": [],
        "age_group": [],
        "emotion": [],
        "style": [],
        "voice_feature": [],
        "scenario": [],
        "professional_field": [],
        "speed": [],
        "rhythm": [],
        "tone": [],
        "effect": [],
    }

    for tag in tags:
        tag_name = tag.get("name", "")
        # 标签格式: filter:category.value
        if ":" in tag_name and "." in tag_name:
            # 先去掉 filter: 前缀
            tag_name = tag_name.replace("filter:", "")
            # 再按 . 分割成 category 和 value
            parts = tag_name.split(".", 1)
            if len(parts) == 2:
                category, value = parts
                if category in tag_categories:
                    tag_categories[category].append(value)

    return {k: v for k, v in tag_categories.items() if v}


def download_file(url: str, save_path: Path) -> bool:
    """下载文件"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        with open(save_path, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"下载失败 {url}: {e}")
        return False


def process_voices(voices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """处理语音数据并下载资源"""
    processed_voices = []

    for i, voice in enumerate(voices, 1):
        print(f"\n处理 {i}/{len(voices)}: {voice.get('name', 'Unknown')}")

        # 提取基本信息
        voice_id = voice.get("id", "")
        name = voice.get("name", "")
        description = voice.get("description", "")
        chinese_name = extract_chinese_name(description)

        # 提取metadata
        metadata = voice.get("metadata", {})

        # 提取标签
        tags = voice.get("tags", [])
        categorized_tags = extract_tags_info(tags)

        # 头像处理 - 从metadata中获取
        avatar_url = metadata.get("avatar", "")
        avatar_filename = ""
        if avatar_url:
            avatar_ext = avatar_url.split(".")[-1].split("?")[0]
            avatar_filename = f"{voice_id}.{avatar_ext}"
            avatar_path = AVATARS_DIR / avatar_filename

            if not avatar_path.exists():
                print("  下载头像...")
                if download_file(avatar_url, avatar_path):
                    print(f"  ✓ 头像已保存: {avatar_filename}")
            else:
                print(f"  ✓ 头像已存在: {avatar_filename}")

        # 音频处理 - 从metadata.voice.metadata.prompts中获取
        audio_files = []
        audio_urls = []

        voice_metadata = metadata.get("voice", {}).get("metadata", {})
        prompts = voice_metadata.get("prompts", [])

        if prompts:
            print(f"  找到 {len(prompts)} 个音频样本")
            for j, prompt in enumerate(prompts):
                # 尝试获取previewAudio或promptOriginAudioStorageUrl
                sample_url = prompt.get("previewAudio") or prompt.get(
                    "promptOriginAudioStorageUrl", ""
                )
                if sample_url:
                    audio_urls.append(sample_url)
                    audio_ext = sample_url.split(".")[-1].split("?")[0]
                    prompt_id = prompt.get("id", f"sample_{j}")
                    audio_filename = f"{voice_id}_{prompt_id}.{audio_ext}"
                    audio_path = AUDIO_DIR / audio_filename

                    if not audio_path.exists():
                        print(f"    下载音频: {prompt_id}...")
                        if download_file(sample_url, audio_path):
                            audio_files.append(audio_filename)
                            print(f"    ✓ 音频已保存: {audio_filename}")
                    else:
                        audio_files.append(audio_filename)
                        print(f"    ✓ 音频已存在: {audio_filename}")
        else:
            print("  ⚠ 没有可用的音频样本")

        # 统计信息
        stats = {
            "api": voice.get("api", 0),
            "clicks": voice.get("clicks", 0),
            "likes": voice.get("likes", 0),
            "used": voice.get("used", 0),
            "generated": voice.get("generated", 0),
        }

        # 构建处理后的数据
        processed_voice = {
            "id": voice_id,
            "name": name,
            "chinese_name": chinese_name or name,
            "description": description,
            "avatar_url": avatar_url,
            "avatar_file": avatar_filename,
            "tags": categorized_tags,
            "audio_samples": audio_files,
            "audio_urls": audio_urls,
            "stats": stats,
            "status": voice.get("status", ""),
            "type": voice.get("type", ""),
            "created_at": voice.get("createdAt", ""),
            "updated_at": voice.get("updatedAt", ""),
        }

        processed_voices.append(processed_voice)
        time.sleep(0.3)  # 避免请求过快

    return processed_voices


def main():
    print("=" * 60)
    print("Vocu.ai 语音数据爬取工具")
    print("=" * 60)

    # 获取语音列表
    voices = fetch_voices()

    if not voices:
        print("没有获取到任何语音数据")
        return

    # 处理语音数据并下载资源
    processed_voices = process_voices(voices)

    # 保存JSON数据
    output_data = {
        "total": len(processed_voices),
        "source": "https://www.vocu.ai/market",
        "api_endpoint": API_BASE,
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "voices": processed_voices,
    }

    json_file = OUTPUT_DIR / "voices_data.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("爬取完成！")
    print(f"总共处理: {len(processed_voices)} 个语音")
    print(f"数据已保存到: {OUTPUT_DIR}")
    print(f"  - JSON数据: {json_file}")
    print(f"  - 头像图片: {AVATARS_DIR}")
    print(f"  - 音频文件: {AUDIO_DIR}")
    print("=" * 60)

    # 打印统计信息
    print("\n统计信息:")
    avatar_count = len(list(AVATARS_DIR.glob("*")))
    audio_count = len(list(AUDIO_DIR.glob("*")))
    print(f"  - 头像数量: {avatar_count}")
    print(f"  - 音频数量: {audio_count}")

    if audio_count == 0:
        print("\n⚠ 注意: 没有下载到音频文件")
        print("   可能原因: 音频需要登录或特殊权限才能获取")
        print("   建议: 查看API文档或使用浏览器登录后获取音频URL")


if __name__ == "__main__":
    main()
