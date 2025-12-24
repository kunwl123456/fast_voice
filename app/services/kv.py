from __future__ import annotations

import time
from dataclasses import dataclass

try:
    import redis as redis_lib
except Exception:  # pragma: no cover
    redis_lib = None

from app.core.config import settings

_GLOBAL_MEM: dict[str, tuple[str, float]] = {}


@dataclass
class KV:
    """
    KV：用于 nonce 防重放、Idempotency-Key 等。
    - 生产：Redis（推荐）
    - 本地/测试：未配置 REDIS_URL 时退化为进程内内存
    """

    _mem: dict[str, tuple[str, float]]
    _redis: object | None

    @classmethod
    def from_settings(cls) -> "KV":
        if settings.redis_url and redis_lib is not None:
            r = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)
            return cls(_mem=_GLOBAL_MEM, _redis=r)
        return cls(_mem=_GLOBAL_MEM, _redis=None)

    def setnx_ttl(self, key: str, value: str, ttl_seconds: int) -> bool:
        if self._redis is not None:
            return bool(self._redis.set(key, value, nx=True, ex=ttl_seconds))
        now = time.time()
        expired = [k for k, (_, exp) in self._mem.items() if exp <= now]
        for k in expired:
            self._mem.pop(k, None)
        if key in self._mem:
            return False
        self._mem[key] = (value, now + ttl_seconds)
        return True

    def get(self, key: str) -> str | None:
        if self._redis is not None:
            return self._redis.get(key)
        now = time.time()
        entry = self._mem.get(key)
        if entry is None:
            return None
        value, exp = entry
        if exp <= now:
            self._mem.pop(key, None)
            return None
        return value

    def set_ttl(self, key: str, value: str, ttl_seconds: int) -> None:
        if self._redis is not None:
            self._redis.set(key, value, ex=ttl_seconds)
            return
        self._mem[key] = (value, time.time() + ttl_seconds)
