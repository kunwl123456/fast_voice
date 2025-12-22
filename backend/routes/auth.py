import hashlib
import time
import uuid
from typing import Dict, Optional, Tuple

from flask import Blueprint, jsonify, request

from backend.services.redis_client import get_client, get_json, set_json

auth_bp = Blueprint("auth", __name__)

# 内存回退（Redis 不可用时使用，重启会丢失）
_memory_users: Dict[str, Dict] = {}
_memory_tokens: Dict[str, Dict] = {}


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _safe_user(user: Dict) -> Dict:
    return {k: v for k, v in user.items() if k != "password_hash"}


def _load_user(email: str) -> Optional[Dict]:
    client = get_client()
    user = get_json(client, f"user:{email}")
    if user:
        return user
    return _memory_users.get(email)


def _save_user(user: Dict) -> bool:
    client = get_client()
    ok = set_json(client, f"user:{user['email']}", user)
    if ok:
        return True
    _memory_users[user["email"]] = user
    return True


def _store_token(token: str, user: Dict) -> None:
    payload = {"user_id": user["user_id"], "email": user["email"]}
    client = get_client()
    if not set_json(client, f"token:{token}", payload, ex=24 * 3600):
        _memory_tokens[token] = payload


def _invalidate_token(token: str) -> None:
    client = get_client()
    try:
        client.delete(f"token:{token}")
    except Exception:
        pass
    _memory_tokens.pop(token, None)


def _get_user_by_token(token: str) -> Optional[Dict]:
    if not token:
        return None
    client = get_client()
    token_data = get_json(client, f"token:{token}") or _memory_tokens.get(token)
    if not token_data:
        return None
    email = token_data.get("email")
    if not email:
        return None
    user = _load_user(email)
    return user


def _issue_token(user: Dict) -> str:
    token = uuid.uuid4().hex
    _store_token(token, user)
    return token


def _require_fields(data: dict, fields: Tuple[str, ...]) -> Optional[str]:
    missing = [f for f in fields if not data.get(f)]
    if missing:
        return f"缺少字段: {', '.join(missing)}"
    return None


def _auth_token_from_request() -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1).strip()
    return request.args.get("token")


def _ensure_user_from_token() -> Optional[Dict]:
    return _get_user_by_token(_auth_token_from_request())


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
        "bio": "",
        "avatar_url": "",
        "website": "",
        "socials": {"twitter": "", "discord": "", "twitch": "", "github": ""},
        "notify_marketing": False,
        "notify_api_balance": False,
        "notify_api_expiry": False,
        "joined_at": int(time.time()),
    }
    _save_user(user)
    token = _issue_token(user)
    return jsonify({"user": _safe_user(user), "token": token}), 201


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

    token = _issue_token(user)
    return jsonify({"user": _safe_user(user), "token": token})


@auth_bp.get("/me")
def me():
    """依据 Authorization: Bearer <token> 返回当前用户。"""
    user = _ensure_user_from_token()
    if not user:
        return jsonify({"error": "未登录或 token 无效"}), 401

    return jsonify(_safe_user(user))


@auth_bp.get("/profile")
def profile():
    """获取个人资料详情。"""
    user = _ensure_user_from_token()
    if not user:
        return jsonify({"error": "未登录或 token 无效"}), 401
    return jsonify(_safe_user(user))

 
@auth_bp.patch("/profile")
def update_profile():
    """更新个人资料（昵称、简介、社交、网站、通知开关）。"""
    user = _ensure_user_from_token()
    if not user:
        return jsonify({"error": "未登录或 token 无效"}), 401

    data = request.get_json(silent=True) or {}
    allowed_fields = ["username", "bio", "website", "notify_marketing", "notify_api_balance", "notify_api_expiry"]
    for f in allowed_fields:
        if f in data:
            user[f] = data[f]

    socials = data.get("socials")
    if isinstance(socials, dict):
        user.setdefault("socials", {})
        for key in ["twitter", "discord", "twitch", "github"]:
            if key in socials:
                user["socials"][key] = socials[key]

    _save_user(user)
    return jsonify(_safe_user(user))


@auth_bp.post("/password/change")
def change_password():
    user = _ensure_user_from_token()
    if not user:
        return jsonify({"error": "未登录或 token 无效"}), 401
    data = request.get_json(silent=True) or {}
    error = _require_fields(data, ("old_password", "new_password"))
    if error:
        return jsonify({"error": error}), 400
    if user["password_hash"] != _hash_password(data["old_password"]):
        return jsonify({"error": "旧密码错误"}), 400
    user["password_hash"] = _hash_password(data["new_password"])
    _save_user(user)
    return jsonify({"message": "密码已更新"})


@auth_bp.post("/email/change")
def change_email():
    user = _ensure_user_from_token()
    if not user:
        return jsonify({"error": "未登录或 token 无效"}), 401
    data = request.get_json(silent=True) or {}
    error = _require_fields(data, ("password", "new_email"))
    if error:
        return jsonify({"error": error}), 400
    if user["password_hash"] != _hash_password(data["password"]):
        return jsonify({"error": "密码错误"}), 400

    new_email = data["new_email"].strip().lower()
    if new_email != user["email"] and _load_user(new_email):
        return jsonify({"error": "邮箱已被使用"}), 409

    # remove old record
    try:
        client = get_client()
        client.delete(f"user:{user['email']}")
    except Exception:
        _memory_users.pop(user["email"], None)

    user["email"] = new_email
    _save_user(user)
    return jsonify(_safe_user(user))


@auth_bp.post("/avatar")
def update_avatar():
    """更新头像，允许 base64 或 URL 字符串存储。"""
    user = _ensure_user_from_token()
    if not user:
        return jsonify({"error": "未登录或 token 无效"}), 401
    data = request.get_json(silent=True) or {}
    avatar = data.get("avatar")
    if not avatar:
        return jsonify({"error": "缺少 avatar"}), 400
    user["avatar_url"] = avatar
    _save_user(user)
    return jsonify({"avatar_url": avatar})


@auth_bp.post("/logout")
def logout():
    token = _auth_token_from_request()
    if token:
        _invalidate_token(token)
    return jsonify({"message": "已注销"})

