"""
Worker Module
Background process that picks jobs from queue and runs Docker commands
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import AsyncSessionLocal, init_db
from src.queue import redis_queue
from src.models import Job
from src.config import settings


async def update_job_status(job_id: int, status: str, exit_code: int = None):
    """Update job status in database"""
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        if job:
            job.status = status
            if exit_code is not None:
                job.exit_code = exit_code
            if status in ["completed", "failed"]:
                from datetime import datetime
                job.completed_at = datetime.utcnow()
            await session.commit()


async def run_docker_command(job_id: int, command: str):
    """
    Run a Docker command and stream logs via Redis
    
    Args:
        job_id: The job ID in database
        command: Docker command to run (e.g., "docker run hello-world")
    """
    print(f"[Worker] Job {job_id}: Starting command: {command}")
    
    # Ensure Redis connection
    if not redis_queue.redis:
        await redis_queue.connect()
        print("[Worker] Redis connection established in worker")
    
    # Update status to running
    await update_job_status(job_id, "running")
    
    # Publish log message
    await redis_queue.publish_log(job_id, f"🚀 Starting: {command}\n")
    
    try:
        # Use system environment (no hardcoded DOCKER_HOST)
        # The Docker socket will be mounted at /var/run/docker.sock
        env = os.environ.copy()
        # Run the Docker command using async subprocess
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env
        )
        
        print(f"[Worker] Job {job_id}: Process started with PID {process.pid}")
        
        # Stream output line by line
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            line_str = line.decode('utf-8', errors='replace')
            if line_str.strip():
                await redis_queue.publish_log(job_id, line_str)
        
        # Wait for process to complete
        exit_code = await process.wait()
        print(f"[Worker] Job {job_id}: Process finished with exit code {exit_code}")
        
        # Publish completion message
        if exit_code == 0:
            await redis_queue.publish_log(job_id, f"\n✅ Completed with exit code: {exit_code}\n")
            await update_job_status(job_id, "completed", exit_code)
        else:
            await redis_queue.publish_log(job_id, f"\n❌ Failed with exit code: {exit_code}\n")
            await update_job_status(job_id, "failed", exit_code)
        
        print(f"[Worker] Job {job_id}: Finished with exit code {exit_code}")
        
    except Exception as e:
        error_msg = f"\n Error: {str(e)}\n"
        await redis_queue.publish_log(job_id, error_msg)
        await update_job_status(job_id, "failed", -1)
        print(f"[Worker] Job {job_id}: Error - {str(e)}")


async def worker_loop():
    """
    Main worker loop
    Continuously polls Redis queue for new jobs
    """
    print("[Worker] Starting worker loop...")
    print(f"[Worker] Polling interval: {settings.WORKER_POLL_INTERVAL}s")
    
    while True:
        try:
            # Try to get a job from the queue
            job_id = await redis_queue.dequeue_job()
            
            if job_id:
                print(f"[Worker] Found job {job_id} in queue")
                
                # Get job details from database
                async with AsyncSessionLocal() as session:
                    job = await session.get(Job, job_id)
                    
                    if job and job.status == "pending":
                        # Run the Docker command
                        await run_docker_command(job_id, job.command)
                    else:
                        print(f"[Worker] Job {job_id} not found or not pending, skipping")
            
            # Wait before checking queue again
            await asyncio.sleep(settings.WORKER_POLL_INTERVAL)
            
        except Exception as e:
            print(f"[Worker] Error in worker loop: {str(e)}")
            await asyncio.sleep(5)  # Wait longer on error


async def main():
    """Entry point"""
    print("=" * 50)
    print("Container Job Orchestrator - Worker")
    print("=" * 50)
    
    # Connect to Redis
    await redis_queue.connect()
    print("[Worker] Connected to Redis")
    
    # Initialize database tables
    await init_db()
    print("[Worker] Database initialized")
    
    # Start worker loop
    await worker_loop()


if __name__ == "__main__":
    asyncio.run(main())