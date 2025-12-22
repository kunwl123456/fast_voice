import json
from typing import Any, List, Tuple

from flask import Blueprint, jsonify, request

from backend.services.redis_client import get_client, get_json, set_json, add_set_member

discovery_bp = Blueprint("discovery", __name__)

VOICES_KEY = "discovery:voices"
BOOKMARK_KEY = "discovery:bookmarks"

SAMPLE_VOICES: List[dict[str, Any]] = [
    {
        "id": "voice-1",
        "name": "示例女声",
        "language": "zh",
        "tags": ["女性", "平静"],
        "creator": "demo-user",
    },
    {
        "id": "voice-2",
        "name": "示例男声",
        "language": "en",
        "tags": ["男性", "叙述"],
        "creator": "demo-user",
    },
]


def _load_voices() -> Tuple[List[dict[str, Any]], bool]:
    """
    从 Redis 加载发现列表；若 Redis 不可用或无数据则回退到本地示例。
    返回 (voices, used_redis)。
    """
    try:
        client = get_client()
        voices = get_json(client, VOICES_KEY)
        if voices is None:
            voices = SAMPLE_VOICES
            set_json(client, VOICES_KEY, voices)
        return voices, True
    except Exception:
        return SAMPLE_VOICES, False


@discovery_bp.get("/voices")
def list_voices():
    """使用 Redis 存储的发现列表；无 Redis 时回退示例。"""
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 10))
    voices, _ = _load_voices()

    start = (page - 1) * page_size
    end = start + page_size
    sliced = voices[start:end]
    return jsonify({"voices": sliced, "page": page, "page_size": page_size, "total": len(voices)})


@discovery_bp.get("/voices/<voice_id>")
def voice_detail(voice_id: str):
    """返回指定 ID 的声音详情。"""
    voices, _ = _load_voices()
    voice = next((v for v in voices if v["id"] == voice_id), None)
    if not voice:
        return jsonify({"error": "voice not found"}), 404
    # 简化返回，附加示例统计字段
    return jsonify(
        {
            **voice,
            "description": "演示用占位声音。",
            "use_count": 120,
            "like_count": 42,
        }
    )


@discovery_bp.post("/bookmark")
def bookmark():
    """
    收藏接口：把 voice_model_id 存入 Redis Set；Redis 不可用时直接返回成功。
    """
    data = request.get_json(silent=True) or {}
    voice_model_id = data.get("voice_model_id")
    if not voice_model_id:
        return jsonify({"error": "voice_model_id is required"}), 400

    stored = False
    try:
        client = get_client()
        stored = add_set_member(client, BOOKMARK_KEY, voice_model_id)
    except Exception:
        stored = False

    return jsonify({"success": True, "voice_model_id": voice_model_id, "stored_in_redis": stored})

