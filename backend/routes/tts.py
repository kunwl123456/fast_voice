from flask import Blueprint, jsonify, request

tts_bp = Blueprint("tts", __name__)


@tts_bp.post("/generate")
def generate():
    """
    文本转语音接口占位。

    注意：按照用户要求，该接口仅预留，不做真实调用。可在此处接入模型推理或任务队列。
    """
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    voice_model_id = data.get("voice_model_id")
    settings = data.get(
        "settings",
        {
            "speed": 1.0,
            "volume": 0.0,
            "temperature": 0.9,
            "top_p": 0.9,
            "high_quality": True,
        },
    )
    return (
        jsonify(
            {
                "message": "TTS 接口占位，待实现",
                "echo": {
                    "text": text,
                    "voice_model_id": voice_model_id,
                    "settings": settings,
                },
            }
        ),
        501,
    )

