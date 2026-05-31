"""
Models Module
Defines the Job table structure for the database
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text

from src.database import Base


class Job(Base):
    """
    Job Model - Represents a containerized task in the database
    
    Each row = one job that was submitted to run
    """
    
    __tablename__ = "jobs"
    
    # Unique ID (auto-generated)
    id = Column(Integer, primary_key=True, index=True)
    
    # Job name (given by user when submitting)
    name = Column(String(255), nullable=False)
    
    # Docker command to run (e.g., "docker run hello-world")
    command = Column(Text, nullable=False)
    
    # Status: pending, running, completed, failed
    status = Column(String(50), default="pending", index=True)
    
    # When job was submitted
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # When job finished (null if still running)
    completed_at = Column(DateTime, nullable=True)
    
    # Exit code from Docker (0 = success, else = error)
    exit_code = Column(Integer, nullable=True)
    
    # Optional: description of what the job does
    description = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Job {self.id}: {self.name} ({self.status})>"