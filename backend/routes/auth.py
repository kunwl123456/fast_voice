from flask import Blueprint, jsonify, request

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    """示例登录接口（演示用，未接入真实鉴权）。"""
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    if not email:
        return jsonify({"error": "email is required"}), 400
    return jsonify(
        {
            "user_id": "demo-user",
            "token": "demo-token",
            "email": email,
            "username": "demo",
        }
    )


@auth_bp.get("/me")
def me():
    """获取当前用户信息（演示数据）。"""
    return jsonify(
        {
            "user_id": "demo-user",
            "email": "demo@example.com",
            "username": "demo",
            "role": "user",
        }
    )

