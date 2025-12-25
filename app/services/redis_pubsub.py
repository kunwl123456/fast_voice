"""Redis Pub/Sub 工具类，用于任务状态实时推送"""

from __future__ import annotations

import json
import asyncio
from typing import AsyncGenerator, Any
from redis import asyncio as aioredis

from app.core.config import settings
from loguru import logger


class RedisPubSub:
    """Redis 发布订阅管理器"""
    
    _redis_client: aioredis.Redis | None = None
    
    @classmethod
    async def get_client(cls) -> aioredis.Redis | None:
        """获取 Redis 客户端（单例）"""
        if cls._redis_client is None:
            redis_url = settings.redis_url
            if not redis_url:
                logger.warning("Redis URL not configured, pub/sub disabled")
                return None
            
            try:
                cls._redis_client = await aioredis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                )
                # 测试连接
                await cls._redis_client.ping()
                logger.info("Redis pub/sub client connected successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                cls._redis_client = None
        
        return cls._redis_client
    
    @classmethod
    async def close(cls):
        """关闭 Redis 连接"""
        if cls._redis_client:
            await cls._redis_client.close()
            cls._redis_client = None
    
    @classmethod
    async def publish_job_status(
        cls,
        job_type: str,  # "tts" or "clone"
        job_uuid: str,
        status: str,
        data: dict | None = None
    ) -> bool:
        """
        发布任务状态更新
        
        Args:
            job_type: 任务类型（tts 或 clone）
            job_uuid: 任务 UUID
            status: 任务状态（queued/running/succeeded/failed）
            data: 附加数据（可选）
        
        Returns:
            是否发布成功
        """
        client = await cls.get_client()
        if not client:
            return False
        
        channel = f"{job_type}:job:{job_uuid}"
        payload = {
            "job_uuid": job_uuid,
            "status": status,
            "data": data or {},
        }
        
        try:
            await client.publish(channel, json.dumps(payload))
            logger.debug(f"Published to {channel}: {status}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish to {channel}: {e}")
            return False
    
    @classmethod
    async def subscribe_job_status(
        cls,
        job_type: str,
        job_uuid: str,
        timeout: float = 300.0
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        订阅任务状态更新（异步生成器）
        
        Args:
            job_type: 任务类型（tts 或 clone）
            job_uuid: 任务 UUID
            timeout: 超时时间（秒）
        
        Yields:
            状态更新消息字典
        """
        client = await cls.get_client()
        if not client:
            logger.warning("Redis client not available for subscription")
            return
        
        channel = f"{job_type}:job:{job_uuid}"
        pubsub = client.pubsub()
        
        try:
            await pubsub.subscribe(channel)
            logger.debug(f"Subscribed to {channel}")
            
            # 设置超时
            start_time = asyncio.get_event_loop().time()
            
            while True:
                # 检查超时
                if asyncio.get_event_loop().time() - start_time > timeout:
                    logger.debug(f"Subscription to {channel} timed out")
                    break
                
                try:
                    # 非阻塞获取消息（1秒超时）
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=1.0
                    )
                    
                    if message and message['type'] == 'message':
                        try:
                            payload = json.loads(message['data'])
                            yield payload
                            
                            # 如果是终态，停止订阅
                            if payload.get('status') in ['succeeded', 'failed']:
                                logger.debug(f"Job {job_uuid} reached final state")
                                break
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in message: {message['data']}")
                
                except asyncio.TimeoutError:
                    # 1秒内没有消息，继续等待
                    continue
                
        except Exception as e:
            logger.error(f"Error in subscription to {channel}: {e}")
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            logger.debug(f"Unsubscribed from {channel}")

