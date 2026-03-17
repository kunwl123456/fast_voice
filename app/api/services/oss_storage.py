"""
阿里云 OSS 存储管理（Python SDK V2）

参考文档:
https://help.aliyun.com/zh/oss/developer-reference/upload-files-using-oss-sdk-for-python-v2
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import alibabacloud_oss_v2 as oss
from alibabacloud_oss_v2 import GetObjectRequest, PutObjectRequest
from alibabacloud_oss_v2.client import Client

from app.api.services.storage import safe_join


class OSSStorageError(Exception):
    """OSS 存储操作异常"""


@dataclass(frozen=True)
class OSSPresignOptions:
    """预签名 URL 选项"""

    expires_seconds: int = 3600
    response_content_disposition: str | None = None


class OSSStorageManager:
    """
    阿里云 OSS 管理类

    支持:
    - 上传文件/字节
    - 下载文件/字节
    - 生成文件访问链接（公开 URL 或预签名 URL）
    """

    def __init__(
        self,
        region: str,
        bucket: str,
        access_key_id: str | None = None,
        access_key_secret: str | None = None,
        endpoint: str | None = None,
        use_cname: bool = False,
        public_base_url: str | None = None,
        default_presign_expires_seconds: int = 3600,
    ):
        if not region:
            raise ValueError("OSS region 未配置")
        if not bucket:
            raise ValueError("OSS bucket 未配置")

        self.bucket = bucket
        self.endpoint = endpoint
        self.use_cname = use_cname
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self.default_presign_expires_seconds = default_presign_expires_seconds

        cfg = oss.config.load_default()
        if access_key_id and access_key_secret:
            cfg.credentials_provider = oss.credentials.StaticCredentialsProvider(
                access_key_id, access_key_secret
            )
        else:
            cfg.credentials_provider = (
                oss.credentials.EnvironmentVariableCredentialsProvider()
            )
        cfg.region = region
        if endpoint:
            cfg.endpoint = endpoint
        cfg.use_cname = use_cname

        self.client: Client = Client(cfg)

    @staticmethod
    def _normalize_key(object_key: str) -> str:
        if not object_key:
            raise ValueError("object_key 不能为空")
        return object_key.strip("/").replace("\\", "/")

    def upload_file(
        self,
        object_key: str,
        file_path: str | Path,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Any:
        key = self._normalize_key(object_key)
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        with path.open("rb") as f:
            req = PutObjectRequest(bucket=self.bucket, key=key, body=f)
            if content_type:
                req.content_type = content_type
            if metadata:
                req.metadata = metadata
            return self.client.put_object(req)

    def upload_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Any:
        key = self._normalize_key(object_key)
        req = PutObjectRequest(bucket=self.bucket, key=key, body=data)
        if content_type:
            req.content_type = content_type
        if metadata:
            req.metadata = metadata
        return self.client.put_object(req)

    def download_file(self, object_key: str, file_path: str | Path) -> Any:
        key = self._normalize_key(object_key)
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        req = GetObjectRequest(bucket=self.bucket, key=key)
        result = self.client.get_object(req)
        with result.body as stream, path.open("wb") as f:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                f.write(chunk)
        return result

    def download_bytes(self, object_key: str) -> bytes:
        key = self._normalize_key(object_key)
        req = GetObjectRequest(bucket=self.bucket, key=key)
        result = self.client.get_object(req)
        with result.body as stream:
            return stream.read()

    def get_presigned_url(
        self,
        object_key: str,
        options: OSSPresignOptions | None = None,
    ) -> str:
        key = self._normalize_key(object_key)
        req = GetObjectRequest(bucket=self.bucket, key=key)

        options = options or OSSPresignOptions(
            expires_seconds=self.default_presign_expires_seconds
        )
        if options.response_content_disposition:
            req.response_content_disposition = options.response_content_disposition

        presign_result = self.client.presign(
            req, expires=timedelta(seconds=options.expires_seconds)
        )
        return presign_result.url

    def get_public_url(self, object_key: str) -> str:
        key = self._normalize_key(object_key)
        if self.public_base_url:
            return f"{self.public_base_url}/{safe_join(key)}"

        endpoint = (self.endpoint or "").strip().rstrip("/")
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            base = endpoint
        elif endpoint:
            base = f"https://{endpoint}"
        else:
            base = ""

        if not base:
            raise OSSStorageError(
                "无法生成公开 URL: 未配置 public_base_url 或 endpoint"
            )

        if self.use_cname:
            return f"{base}/{safe_join(key)}"
        return f"{base}/{self.bucket}/{safe_join(key)}"


_oss_manager: OSSStorageManager | None = None


def get_oss_storage_manager() -> OSSStorageManager:
    """
    获取 OSS 管理实例（懒加载）
    """
    global _oss_manager
    if _oss_manager is None:
        from app.core.config import settings

        if not settings.oss_region:
            raise ValueError("OSS region 未配置 (oss_region)")
        if not settings.oss_bucket:
            raise ValueError("OSS bucket 未配置 (oss_bucket)")

        _oss_manager = OSSStorageManager(
            region=settings.oss_region,
            bucket=settings.oss_bucket,
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
            endpoint=settings.oss_endpoint,
            use_cname=settings.oss_use_cname,
            public_base_url=settings.oss_public_base_url,
            default_presign_expires_seconds=settings.oss_presign_expires_seconds,
        )

    return _oss_manager
