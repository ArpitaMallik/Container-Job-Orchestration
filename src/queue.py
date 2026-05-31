"""
Queue Module
Handles Redis operations for job queue and log streaming
"""

import json
from typing import Optional
import redis.asyncio as redis

from src.config import settings


class RedisQueue:
    """
    Redis Queue Manager
    
    Handles two things:
    1. Job Queue - where we put job IDs for workers to pick up
    2. Log Streaming - where workers publish logs for real-time viewing
    """
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        self.redis = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
    
    # ─────────────────────────────────────────────
    # JOB QUEUE OPERATIONS
    # ─────────────────────────────────────────────
    
    async def enqueue_job(self, job_id: int):
        """
        Add a job ID to the queue
        Worker will pick this up
        """
        if self.redis:
            await self.redis.lpush(settings.JOBS_QUEUE, job_id)
    
    async def dequeue_job(self) -> Optional[int]:
        """
        Get next job ID from queue (blocking for 2 seconds)
        Returns None if queue is empty
        """
        if self.redis:
            result = await self.redis.brpop(settings.JOBS_QUEUE, timeout=2)
            if result:
                return int(result[1])  # result = (queue_name, job_id)
        return None
    
    # ─────────────────────────────────────────────
    # LOG STREAMING OPERATIONS (Pub/Sub)
    # ─────────────────────────────────────────────
    
    async def publish_log(self, job_id: int, log_line: str):
        """
        Publish a log line for a job
        WebSocket will subscribe to receive this
        """
        if self.redis:
            channel = f"{settings.LOGS_CHANNEL_PREFIX}{job_id}"
            try:
                subscribers = await self.redis.publish(channel, log_line)
                print(f"[Redis] Published to {channel}, {subscribers} subscribers received")
            except Exception as e:
                print(f"[Redis] Failed to publish to {channel}: {e}")
    
    async def subscribe_to_logs(self, job_id: int):
        """
        Subscribe to log channel for a job
        Returns a PubSub object to listen for logs
        """
        if self.redis:
            channel = f"{settings.LOGS_CHANNEL_PREFIX}{job_id}"
            pubsub = self.redis.pubsub()
            try:
                await pubsub.subscribe(channel)
                # Wait for subscription confirmation
                await pubsub.get_message(ignore_subscribe_messages=False, timeout=2.0)
                print(f"[Redis] Subscribed to log channel: {channel}")
                return pubsub
            except Exception as e:
                print(f"[Redis] Failed to subscribe to {channel}: {e}")
                await pubsub.close()
                return None
        return None
    
    async def close_pubsub(self, pubsub):
        """Close a pubsub connection"""
        if pubsub:
            await pubsub.close()


# Global instance
redis_queue = RedisQueue()