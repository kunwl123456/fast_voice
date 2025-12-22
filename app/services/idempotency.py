from __future__ import annotations

from app.services.kv import KV


def idem_key(project_id: int, endpoint: str, key: str) -> str:
    return f"idem:{project_id}:{endpoint}:{key}"


def get_idempotency(kv: KV, project_id: int, endpoint: str, key: str) -> str | None:
    return kv.get(idem_key(project_id, endpoint, key))


def set_idempotency(kv: KV, project_id: int, endpoint: str, key: str, value: str, ttl_seconds: int = 3600) -> None:
    kv.set_ttl(idem_key(project_id, endpoint, key), value, ttl_seconds)


