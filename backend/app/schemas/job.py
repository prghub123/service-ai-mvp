"""Job-related Pydantic schemas."""

from datetime import datetime, date, time
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
from app.models.job import JobStatus, JobPriority, JobSource


class JobAddressInline(BaseModel):
    """Inline address when not using a saved address."""
    
    street: str = Field(..., max_length=255)
    unit: Optional[str] = Field(None, max_length=50)
    city: str = Field(..., max_length=100)
    state: str = Field(..., max_length=50)
    zip_code: str = Field(..., max_length=20)
    gate_code: Optional[str] = None
    access_notes: Optional[str] = None


# Alias for backwards compatibility
AddressInline = JobAddressInline


class JobCreate(BaseModel):
    """Schema for creating a job (self-service booking)."""
    
    service_type: str = Field(..., max_length=100)
    description: Optional[str] = None
    
    # Address - either saved address ID or inline
    address_id: Optional[UUID] = None
    address: Optional[JobAddressInline] = None
    
    # Scheduling (optional for emergency bookings)
    preferred_date: Optional[date] = None
    preferred_time_start: Optional[time] = None
    preferred_time_end: Optional[time] = None
    
    # For slot reservation flow
    reservation_token: Optional[str] = None


class JobUpdate(BaseModel):
    """Schema for updating a job (admin)."""
    
    technician_id: Optional[UUID] = None
    scheduled_date: Optional[date] = None
    scheduled_time_start: Optional[time] = None
    scheduled_time_end: Optional[time] = None
    priority: Optional[JobPriority] = None
    description: Optional[str] = None


class JobStatusUpdate(BaseModel):
    """Schema for updating job status (technician app)."""
    
    status: JobStatus
    reason: Optional[str] = None  # Required for cancellation


class JobNoteCreate(BaseModel):
    """Schema for adding a note to a job."""
    
    content: str = Field(..., min_length=1)


class JobNoteResponse(BaseModel):
    """Schema for job note response."""
    
    id: UUID
    content: str
    author_type: Optional[str]
    author_name: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class JobTechnicianResponse(BaseModel):
    """Minimal technician info for job response."""
    
    id: UUID
    name: str
    phone: str
    
    class Config:
        from_attributes = True


class JobCustomerResponse(BaseModel):
    """Minimal customer info for job response."""
    
    id: UUID
    name: Optional[str]
    phone: str
    
    class Config:
        from_attributes = True


class JobAddressResponse(BaseModel):
    """Address info for job response."""
    
    id: UUID
    street: str
    unit: Optional[str]
    city: str
    state: str
    zip_code: str
    full_address: str
    latitude: Optional[str]
    longitude: Optional[str]
    gate_code: Optional[str]
    access_notes: Optional[str]
    
    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    """Full job response schema."""
    
    id: UUID
    confirmation_code: Optional[str]
    
    # Details
    service_type: str
    description: Optional[str]
    priority: JobPriority
    status: JobStatus
    source: JobSource
    
    # Scheduling
    scheduled_date: Optional[date]
    scheduled_time_start: Optional[time]
    scheduled_time_end: Optional[time]
    
    # Related entities
    customer: Optional[JobCustomerResponse]
    technician: Optional[JobTechnicianResponse]
    address: Optional[JobAddressResponse]
    
    # Notes
    notes: List[JobNoteResponse] = []
    
    # Emergency flags
    emergency_keywords_matched: bool
    review_recommended: bool
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    assigned_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Paginated job list response."""
    
    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# Technician app schemas

class TechnicianJobResponse(BaseModel):
    """Job response for technician app (includes customer contact info)."""
    
    id: UUID
    confirmation_code: Optional[str]
    
    # Details
    service_type: str
    description: Optional[str]
    priority: JobPriority
    status: JobStatus
    
    # Scheduling
    scheduled_date: Optional[date]
    scheduled_time_start: Optional[time]
    scheduled_time_end: Optional[time]
    
    # Customer (full contact for tech)
    customer_name: Optional[str]
    customer_phone: str
    
    # Address (full details for navigation)
    address_street: str
    address_unit: Optional[str]
    address_city: str
    address_state: str
    address_zip: str
    address_full: str
    address_latitude: Optional[str]
    address_longitude: Optional[str]
    gate_code: Optional[str]
    access_notes: Optional[str]
    
    # Notes
    notes: List[JobNoteResponse] = []
    
    # Timestamps
    created_at: datetime
    
    class Config:
        from_attributes = True
