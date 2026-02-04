"""Job models - the core entity of the system."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Date, Time, Index, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class JobStatus(str, PyEnum):
    """Job status enumeration."""
    PENDING = "pending"              # Created, awaiting tech assignment
    SCHEDULED = "scheduled"          # Tech assigned, waiting for job day
    DISPATCHED = "dispatched"        # Emergency auto-dispatched
    EN_ROUTE = "en_route"            # Tech traveling to location
    IN_PROGRESS = "in_progress"      # Tech on site, working
    COMPLETED = "completed"          # Work finished
    CANCELLED = "cancelled"          # Cancelled by customer or business
    AWAITING_PARTS = "awaiting_parts"  # Paused, waiting for parts


class JobPriority(str, PyEnum):
    """Job priority levels."""
    LOW = "low"
    NORMAL = "normal"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class JobSource(str, PyEnum):
    """How the job was created."""
    CUSTOMER_APP = "customer_app"
    PHONE_AGENT = "phone_agent"
    ADMIN_DASHBOARD = "admin_dashboard"
    WEBSITE = "website"


class Job(Base):
    """Job entity - represents a service request/appointment."""
    
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    address_id = Column(UUID(as_uuid=True), ForeignKey("customer_addresses.id"))
    technician_id = Column(UUID(as_uuid=True), ForeignKey("technicians.id"))
    
    # Job Details
    service_type = Column(String(100), nullable=False)  # 'plumbing', 'hvac', 'water_heater', etc.
    description = Column(Text)
    priority = Column(Enum(JobPriority), default=JobPriority.NORMAL)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    
    # Scheduling
    scheduled_date = Column(Date)
    scheduled_time_start = Column(Time)
    scheduled_time_end = Column(Time)
    
    # Tracking
    source = Column(Enum(JobSource), default=JobSource.CUSTOMER_APP)
    source_call_id = Column(String(100))  # Vapi call ID for reconciliation
    confirmation_code = Column(String(20))
    
    # Emergency Detection
    emergency_keywords_matched = Column(Boolean, default=False)
    emergency_confidence_score = Column(String(10))  # LLM confidence: "0.95"
    review_recommended = Column(Boolean, default=False)
    
    # Escalation Tracking
    escalation_level = Column(String(10), default="0")  # 0, 1, 2, 3, 4
    last_escalation_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    assigned_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    
    # Relationships
    business = relationship("Business", back_populates="jobs")
    customer = relationship("Customer", back_populates="jobs")
    address = relationship("CustomerAddress", back_populates="jobs")
    technician = relationship("Technician", back_populates="jobs")
    notes = relationship("JobNote", back_populates="job", cascade="all, delete-orphan")
    photos = relationship("JobPhoto", back_populates="job", cascade="all, delete-orphan")
    status_history = relationship("JobStatusHistory", back_populates="job", cascade="all, delete-orphan")
    
    # Prevent double-booking: unique constraint on business + date + time
    # Only applies to non-cancelled jobs
    __table_args__ = (
        Index(
            "ix_jobs_unique_slot",
            "business_id",
            "scheduled_date",
            "scheduled_time_start",
            "technician_id",
            unique=True,
            postgresql_where=(status != JobStatus.CANCELLED)
        ),
    )
    
    def __repr__(self):
        return f"<Job {self.confirmation_code or self.id}>"


class JobNote(Base):
    """Notes added to jobs by technicians or admins."""
    
    __tablename__ = "job_notes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    
    # Note content
    content = Column(Text, nullable=False)
    
    # Author (could be tech or admin)
    author_type = Column(String(20))  # 'technician', 'admin', 'system'
    author_id = Column(UUID(as_uuid=True))
    author_name = Column(String(255))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="notes")
    
    def __repr__(self):
        return f"<JobNote {self.job_id}>"


class JobPhoto(Base):
    """Photos uploaded for jobs."""
    
    __tablename__ = "job_photos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    
    # Photo info
    url = Column(String(500), nullable=False)
    caption = Column(String(255))
    photo_type = Column(String(50))  # 'before', 'after', 'diagnostic'
    
    # Uploader
    uploaded_by_type = Column(String(20))  # 'technician', 'customer'
    uploaded_by_id = Column(UUID(as_uuid=True))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="photos")
    
    def __repr__(self):
        return f"<JobPhoto {self.job_id}>"


class JobStatusHistory(Base):
    """Track all status changes for auditing."""
    
    __tablename__ = "job_status_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    
    # Status change
    from_status = Column(String(50))
    to_status = Column(String(50), nullable=False)
    
    # Who made the change
    changed_by_type = Column(String(20))  # 'technician', 'admin', 'system', 'customer'
    changed_by_id = Column(UUID(as_uuid=True))
    
    # Optional reason
    reason = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="status_history")
    
    def __repr__(self):
        return f"<JobStatusHistory {self.from_status} -> {self.to_status}>"
