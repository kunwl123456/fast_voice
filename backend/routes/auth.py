import hashlib
import uuid
from typing import Dict, Optional, Tuple

from flask import Blueprint, jsonify, request

from backend.services.redis_client import get_client, get_json, set_json

auth_bp = Blueprint("auth", __name__)

# 内存回退（Redis 不可用时使用，重启会丢失）
_memory_users: Dict[str, Dict] = {}
_memory_tokens: Dict[str, str] = {}


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _load_user(email: str) -> Optional[Dict]:
    client = get_client()
    user = get_json(client, f"user:{email}")
    if user:
        return user
    # fallback
    return _memory_users.get(email)


def _save_user(user: Dict) -> bool:
    client = get_client()
    ok = set_json(client, f"user:{user['email']}", user)
    if ok:
        return True
    _memory_users[user["email"]] = user
    return True


def _store_token(token: str, user_id: str) -> None:
    client = get_client()
    if not set_json(client, f"token:{token}", {"user_id": user_id}, ex=24 * 3600):
        _memory_tokens[token] = user_id


def _get_user_by_token(token: str) -> Optional[Dict]:
    if not token:
        return None
    client = get_client()
    token_data = get_json(client, f"token:{token}")
    if token_data and "user_id" in token_data:
        # 反查 email
        for key in client.scan_iter(match="user:*"):
            user = get_json(client, key)
            if user and user.get("user_id") == token_data["user_id"]:
                return user
    # fallback
    user_id = _memory_tokens.get(token)
    if user_id:
        for user in _memory_users.values():
            if user.get("user_id") == user_id:
                return user
    return None


def _issue_token(user_id: str) -> str:
    token = uuid.uuid4().hex
    _store_token(token, user_id)
    return token


def _require_fields(data: dict, fields: Tuple[str, ...]) -> Optional[str]:
    missing = [f for f in fields if not data.get(f)]
    if missing:
        return f"缺少字段: {', '.join(missing)}"
    return None


@auth_bp.post("/register")
def register():
    """注册账号，保存到 Redis（失败则内存回退）。"""
    data = request.get_json(silent=True) or {}
    error = _require_fields(data, ("email", "password", "username"))
    if error:
        return jsonify({"error": error}), 400

    email = data["email"].strip().lower()
    if _load_user(email):
        return jsonify({"error": "用户已存在"}), 409

    user = {
        "user_id": uuid.uuid4().hex,
        "email": email,
        "username": data["username"],
        "password_hash": _hash_password(data["password"]),
        "role": "user",
    }
    _save_user(user)
    token = _issue_token(user["user_id"])
    return jsonify({"user": {k: v for k, v in user.items() if k != "password_hash"}, "token": token}), 201


@auth_bp.post("/login")
def login():
    """邮箱+密码登录，返回 token。"""
    data = request.get_json(silent=True) or {}
    error = _require_fields(data, ("email", "password"))
    if error:
        return jsonify({"error": error}), 400

    email = data["email"].strip().lower()
    user = _load_user(email)
    if not user:
        return jsonify({"error": "用户不存在"}), 401
    if user.get("password_hash") != _hash_password(data["password"]):
        return jsonify({"error": "密码错误"}), 401

    token = _issue_token(user["user_id"])
    return jsonify({"user": {k: v for k, v in user.items() if k != "password_hash"}, "token": token})


@auth_bp.get("/me")
def me():
    """依据 Authorization: Bearer <token> 返回当前用户。"""
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "", 1).strip()
    token = token or request.args.get("token")

    user = _get_user_by_token(token)
    if not user:
        return jsonify({"error": "未登录或 token 无效"}), 401

    return jsonify({k: v for k, v in user.items() if k != "password_hash"})

