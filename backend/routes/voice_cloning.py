from flask import Blueprint, jsonify, request

voice_cloning_bp = Blueprint("voice_cloning", __name__)


@voice_cloning_bp.post("/upload")
def upload():
    """上传源音频（演示，未做存储）。"""
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400
    file = request.files["file"]
    # 此处应保存文件并返回真实上传ID
    return jsonify({"upload_id": "demo-upload-id", "filename": file.filename, "duration": 30})


@voice_cloning_bp.post("/create")
def create_voice():
    """
    创建声音模型接口占位。

    按照用户要求预留实现，可在此接入训练流水线。
    """
    data = request.get_json(silent=True) or {}
    upload_id = data.get("upload_id")
    name = data.get("name")
    if not upload_id or not name:
        return jsonify({"error": "upload_id and name are required"}), 400
    return (
        jsonify(
            {
                "message": "创建声音接口占位，待实现",
                "voice_model_id": "demo-voice-model",
                "status": "training",
                "echo": data,
            }
        ),
        501,
    )


@voice_cloning_bp.get("/status/<voice_model_id>")
def status(voice_model_id: str):
    """返回示例训练状态。"""
    return jsonify(
        {
            "voice_model_id": voice_model_id,
            "status": "training",
            "progress": 0.4,
            "estimated_time": "2m",
        }
    )

