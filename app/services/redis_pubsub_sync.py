"""Redis Pub/Sub 同步版本（用于 Celery Worker）"""

from __future__ import annotations

import json
from redis import Redis
from celery.utils.log import get_task_logger

from app.core.config import settings

logger = get_task_logger(__name__)


class RedisPubSubSync:
    """Redis 发布订阅管理器（同步版本）"""
    
    _redis_client: Redis | None = None
    
    @classmethod
    def get_client(cls) -> Redis | None:
        """获取 Redis 客户端（单例）"""
        if cls._redis_client is None:
            redis_url = settings.redis_url
            if not redis_url:
                logger.warning("Redis URL not configured, pub/sub disabled")
                return None
            
            try:
                cls._redis_client = Redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                )
                # 测试连接
                cls._redis_client.ping()
                logger.info("Redis pub/sub client (sync) connected successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis (sync): {e}")
                cls._redis_client = None
        
        return cls._redis_client
    
    @classmethod
    def close(cls):
        """关闭 Redis 连接"""
        if cls._redis_client:
            cls._redis_client.close()
            cls._redis_client = None
    
    @classmethod
    def publish_job_status(
        cls,
        job_type: str,  # "tts" or "clone"
        job_uuid: str,
        status: str,
        data: dict | None = None
    ) -> bool:
        """
        发布任务状态更新（同步版本）
        
        Args:
            job_type: 任务类型（tts 或 clone）
            job_uuid: 任务 UUID
            status: 任务状态（queued/running/succeeded/failed）
            data: 附加数据（可选）
        
        Returns:
            是否发布成功
        """
        client = cls.get_client()
        if not client:
            return False
        
        channel = f"{job_type}:job:{job_uuid}"
        payload = {
            "job_uuid": job_uuid,
            "status": status,
            "data": data or {},
        }
        
        try:
            client.publish(channel, json.dumps(payload))
            logger.debug(f"Published to {channel}: {status}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish to {channel}: {e}")
            return False

