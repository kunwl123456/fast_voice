from __future__ import annotations

from pathlib import Path

from app.core.config import settings


def ensure_dir(p: str | Path) -> str:
    Path(p).mkdir(parents=True, exist_ok=True)
    return str(p)


def data_dir() -> str:
    return ensure_dir(settings.data_dir)


def job_dir(kind: str, user_id: int, job_uuid: str) -> str:
    """生成任务目录，使用 user_id_uuid 格式"""
    base = Path(data_dir()) / kind / f"{user_id}_{job_uuid}"
    return ensure_dir(base)


def save_bytes(path: str | Path, data: bytes) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return str(p)


def safe_join(*parts: str) -> str:
    return "/".join(s.strip("/").replace("\\", "/") for s in parts if s is not None)


def to_public_file_url(local_path: str) -> str:
    """
    把本地 DATA_DIR 下的文件映射到 /files/{relative_path}
    """
    base = Path(data_dir()).resolve()
    p = Path(local_path).resolve()
    try:
        rel = p.relative_to(base)
    except Exception:
        return ""
    return "/" + safe_join("files", str(rel))


