"""
Schemas Module
Defines how Job data looks in API requests and responses
Uses Pydantic for validation
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class JobBase(BaseModel):
    """Base schema - fields shared between input and output"""
    name: str = Field(..., min_length=1, max_length=255, description="Job name")
    command: str = Field(..., min_length=1, description="Docker command to run")
    description: Optional[str] = Field(None, description="Optional description")


class JobCreate(JobBase):
    """Schema for creating a new job (API input)"""
    pass  # Same as JobBase - no extra fields needed


class JobResponse(JobBase):
    """Schema for job response (API output)"""
    id: int
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    exit_code: Optional[int] = None

    class Config:
        from_attributes = True  # Allows converting SQLAlchemy model to Pydantic


class JobListResponse(BaseModel):
    """Schema for listing multiple jobs"""
    jobs: list[JobResponse]
    total: int