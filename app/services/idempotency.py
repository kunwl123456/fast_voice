from __future__ import annotations

from app.services.kv import KV


def idem_key(user_id: int, endpoint: str, key: str) -> str:
    return f"idem:{user_id}:{endpoint}:{key}"


def get_idempotency(kv: KV, user_id: int, endpoint: str, key: str) -> str | None:
    return kv.get(idem_key(user_id, endpoint, key))


def set_idempotency(kv: KV, user_id: int, endpoint: str, key: str, value: str, ttl_seconds: int = 3600) -> None:
    kv.set_ttl(idem_key(user_id, endpoint, key), value, ttl_seconds)



