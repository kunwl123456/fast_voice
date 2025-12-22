import json
import os
from typing import Any, Optional

import redis


def get_client() -> redis.Redis:
    """获取 Redis 客户端，默认连接 redis://localhost:6379/0。"""
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(url, decode_responses=True)


def get_json(client: redis.Redis, key: str, default: Optional[Any] = None) -> Any:
    """从 Redis 读取 JSON。出错返回 default。"""
    try:
        data = client.get(key)
        return json.loads(data) if data else default
    except Exception:
        return default


def set_json(client: redis.Redis, key: str, value: Any, ex: Optional[int] = None) -> bool:
    """写入 JSON。"""
    try:
        client.set(key, json.dumps(value), ex=ex)
        return True
    except Exception:
        return False


def add_set_member(client: redis.Redis, key: str, member: str) -> bool:
    """向集合添加成员。"""
    try:
        client.sadd(key, member)
        return True
    except Exception:
        return False

