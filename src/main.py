"""
Main Module
FastAPI Application with REST endpoints and WebSocket
"""

from contextlib import asynccontextmanager
import asyncio
from typing import List

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_db, init_db
from src.models import Job
from src.schemas import JobCreate, JobResponse, JobListResponse
from src.queue import redis_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    print("🚀 Starting Container Job Orchestrator...")
    await init_db()
    print("✅ Database initialized")
    await redis_queue.connect()
    print("✅ Redis connected")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    await redis_queue.disconnect()


# Create FastAPI app
app = FastAPI(
    title="Container Job Orchestrator",
    description="Queue Docker containerized tasks and stream execution logs live!",
    version="1.0.0",
    lifespan=lifespan
)


# ─────────────────────────────────────────────
# STATIC FILES (Frontend)
# ─────────────────────────────────────────────

# Serve frontend HTML
@app.get("/", response_class=FileResponse)
async def root():
    """Serve the frontend"""
    return FileResponse("frontend/index.html")


# ─────────────────────────────────────────────
# REST API ENDPOINTS
# ─────────────────────────────────────────────

@app.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(job_data: JobCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new job
    
1. Save job to database (status: pending)
    2. Add job_id to Redis queue
    3. Return job details
    """
    # Create job in database
    job = Job(
        name=job_data.name,
        command=job_data.command,
        description=job_data.description,
        status="pending"
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Add job to Redis queue
    await redis_queue.enqueue_job(job.id)
    print(f"📋 Job {job.id} created and queued")
    
    return job


@app.get("/jobs", response_model=JobListResponse)
async def list_jobs(db: AsyncSession = Depends(get_db)):
    """List all jobs"""
    result = await db.execute(select(Job).order_by(Job.created_at.desc()))
    jobs = result.scalars().all()
    
    return JobListResponse(jobs=list(jobs), total=len(jobs))


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific job by ID"""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a job"""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    await db.delete(job)
    await db.commit()
    print(f"🗑️ Job {job_id} deleted")


# ─────────────────────────────────────────────
# WEBSOCKET FOR LIVE LOGS
# ─────────────────────────────────────────────

@app.websocket("/ws/{job_id}")
async def websocket_logs(websocket: WebSocket, job_id: int):
    """
    WebSocket endpoint for real-time log streaming
    
1. Connect to WebSocket
    2. Subscribe to Redis channel for this job
    3. Stream logs to browser as they come
    """
    await websocket.accept()
    print(f"🔌 WebSocket connected for job {job_id}")
    
    # Subscribe to Redis log channel
    pubsub = await redis_queue.subscribe_to_logs(job_id)
    
    if not pubsub:
        await websocket.close(code=1011, reason="Failed to subscribe to logs")
        return
    
    try:
        # Send initial connection message
        await websocket.send_text("[INFO] Connected to job logs...\n")
        
        # Use listen() async iterator for Redis pubsub
        async for message in pubsub.listen():
            if message["type"] == "message":
                log_data = message["data"]
                print(f"📤 WS sending to client: {log_data[:50]}...")
                await websocket.send_text(log_data)
            elif message["type"] == "subscribe":
                print(f"[Redis] Subscription confirmed for job {job_id}")
                
    except WebSocketDisconnect:
        print(f"🔌 Client disconnected from job {job_id}")
    except Exception as e:
        print(f"❌ WebSocket error: {str(e)}")
    finally:
        # Cleanup
        try:
            await redis_queue.close_pubsub(pubsub)
        except Exception:
            pass
        print(f"🔌 WebSocket disconnected for job {job_id}")


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "container-orchestrator"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)