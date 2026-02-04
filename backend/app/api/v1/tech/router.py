"""Technician API routes for the mobile app."""

from datetime import date, datetime, time
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.database import get_db
from app.api.deps import get_current_technician, get_business_from_token
from app.models.technician import Technician
from app.models.business import Business
from app.models.job import Job, JobStatus, JobNote, JobPhoto
from app.services.job_service import JobService
from app.schemas.job import JobStatusUpdate

router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================

class TechJobResponse(BaseModel):
    """Job response for technician app."""
    id: str
    confirmation_code: str
    status: str
    priority: str
    service_type: str
    description: Optional[str]
    
    # Customer info
    customer_name: Optional[str]
    customer_phone: Optional[str]
    
    # Address
    address_street: Optional[str]
    address_city: Optional[str]
    address_state: Optional[str]
    address_zip: Optional[str]
    address_full: Optional[str]
    gate_code: Optional[str]
    access_notes: Optional[str]
    latitude: Optional[str]
    longitude: Optional[str]
    
    # Schedule
    scheduled_date: Optional[date]
    scheduled_time_start: Optional[str]
    scheduled_time_end: Optional[str]
    
    # Notes
    notes: List[dict] = []
    
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateStatusRequest(BaseModel):
    """Request to update job status."""
    status: str
    reason: Optional[str] = None


class AddNoteRequest(BaseModel):
    """Request to add a note to a job."""
    content: str


class UpdateLocationRequest(BaseModel):
    """Request to update technician's current location."""
    latitude: float
    longitude: float


# =============================================================================
# My Jobs
# =============================================================================

@router.get("/my-jobs", response_model=List[TechJobResponse])
async def get_my_jobs(
    db: AsyncSession = Depends(get_db),
    technician: Technician = Depends(get_current_technician),
    status_filter: Optional[str] = Query(None, alias="status"),
    date_filter: Optional[date] = Query(None, alias="date"),
):
    """Get jobs assigned to the current technician."""
    query = (
        select(Job)
        .options(
            selectinload(Job.customer),
            selectinload(Job.address),
            selectinload(Job.notes),
        )
        .where(
            Job.technician_id == technician.id,
            Job.status.notin_([JobStatus.CANCELLED, JobStatus.COMPLETED])
        )
    )
    
    # Apply filters
    if status_filter:
        try:
            status_enum = JobStatus(status_filter)
            query = query.where(Job.status == status_enum)
        except ValueError:
            pass
    
    if date_filter:
        query = query.where(Job.scheduled_date == date_filter)
    else:
        # Default: today and future jobs
        query = query.where(Job.scheduled_date >= date.today())
    
    # Order by date and time
    query = query.order_by(Job.scheduled_date, Job.scheduled_time_start)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return [_job_to_response(job) for job in jobs]


@router.get("/my-jobs/today", response_model=List[TechJobResponse])
async def get_todays_jobs(
    db: AsyncSession = Depends(get_db),
    technician: Technician = Depends(get_current_technician),
):
    """Get today's jobs for the current technician."""
    query = (
        select(Job)
        .options(
            selectinload(Job.customer),
            selectinload(Job.address),
            selectinload(Job.notes),
        )
        .where(
            Job.technician_id == technician.id,
            Job.scheduled_date == date.today(),
            Job.status.notin_([JobStatus.CANCELLED])
        )
        .order_by(Job.scheduled_time_start)
    )
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return [_job_to_response(job) for job in jobs]


@router.get("/my-jobs/history", response_model=List[TechJobResponse])
async def get_job_history(
    db: AsyncSession = Depends(get_db),
    technician: Technician = Depends(get_current_technician),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    """Get completed jobs history for the current technician."""
    query = (
        select(Job)
        .options(
            selectinload(Job.customer),
            selectinload(Job.address),
        )
        .where(
            Job.technician_id == technician.id,
            Job.status == JobStatus.COMPLETED
        )
        .order_by(Job.completed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return [_job_to_response(job) for job in jobs]


# =============================================================================
# Job Actions
# =============================================================================

@router.get("/jobs/{job_id}", response_model=TechJobResponse)
async def get_job_details(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    technician: Technician = Depends(get_current_technician),
):
    """Get detailed job information."""
    query = (
        select(Job)
        .options(
            selectinload(Job.customer),
            selectinload(Job.address),
            selectinload(Job.notes),
        )
        .where(
            Job.id == UUID(job_id),
            Job.technician_id == technician.id
        )
    )
    
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or not assigned to you"
        )
    
    return _job_to_response(job)


@router.post("/jobs/{job_id}/status")
async def update_job_status(
    job_id: str,
    data: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
    technician: Technician = Depends(get_current_technician),
    business: Business = Depends(get_business_from_token),
):
    """Update job status (en_route, in_progress, completed, etc.)."""
    # Verify job is assigned to this technician
    result = await db.execute(
        select(Job).where(
            Job.id == UUID(job_id),
            Job.technician_id == technician.id
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or not assigned to you"
        )
    
    # Validate status transition
    try:
        new_status = JobStatus(data.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Valid values: {[s.value for s in JobStatus]}"
        )
    
    # Update status
    job_service = JobService(db, business.id)
    updated_job = await job_service.update_status(
        job_id=UUID(job_id),
        data=JobStatusUpdate(status=new_status, reason=data.reason),
        changed_by_type="technician",
        changed_by_id=technician.id,
    )
    
    # TODO: Send notification to customer about status change
    
    return {
        "message": f"Job status updated to {new_status.value}",
        "job_id": str(updated_job.id),
        "status": updated_job.status.value,
    }


@router.post("/jobs/{job_id}/notes")
async def add_job_note(
    job_id: str,
    data: AddNoteRequest,
    db: AsyncSession = Depends(get_db),
    technician: Technician = Depends(get_current_technician),
    business: Business = Depends(get_business_from_token),
):
    """Add a note to a job."""
    # Verify job is assigned to this technician
    result = await db.execute(
        select(Job).where(
            Job.id == UUID(job_id),
            Job.technician_id == technician.id
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or not assigned to you"
        )
    
    job_service = JobService(db, business.id)
    from app.schemas.job import JobNoteCreate
    
    note = await job_service.add_note(
        job_id=UUID(job_id),
        data=JobNoteCreate(content=data.content),
        author_type="technician",
        author_id=technician.id,
        author_name=technician.name,
    )
    
    return {
        "message": "Note added successfully",
        "note_id": str(note.id),
    }


@router.post("/jobs/{job_id}/photos")
async def upload_job_photo(
    job_id: str,
    photo_type: str = Query(..., description="Photo type: before, after, diagnostic"),
    caption: Optional[str] = Query(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    technician: Technician = Depends(get_current_technician),
):
    """Upload a photo for a job."""
    # Verify job is assigned to this technician
    result = await db.execute(
        select(Job).where(
            Job.id == UUID(job_id),
            Job.technician_id == technician.id
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or not assigned to you"
        )
    
    # Validate photo type
    if photo_type not in ["before", "after", "diagnostic"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid photo_type. Must be: before, after, or diagnostic"
        )
    
    # TODO: Upload to S3/cloud storage and get URL
    # For now, we'll just save metadata with a placeholder URL
    photo_url = f"https://storage.example.com/jobs/{job_id}/{file.filename}"
    
    photo = JobPhoto(
        job_id=UUID(job_id),
        url=photo_url,
        caption=caption,
        photo_type=photo_type,
        uploaded_by_type="technician",
        uploaded_by_id=technician.id,
    )
    
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    
    return {
        "message": "Photo uploaded successfully",
        "photo_id": str(photo.id),
        "url": photo_url,
    }


# =============================================================================
# Location Updates
# =============================================================================

@router.post("/location")
async def update_location(
    data: UpdateLocationRequest,
    db: AsyncSession = Depends(get_db),
    technician: Technician = Depends(get_current_technician),
):
    """Update technician's current location (for tracking)."""
    technician.current_latitude = data.latitude
    technician.current_longitude = data.longitude
    technician.location_updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Location updated"}


@router.get("/profile")
async def get_profile(
    technician: Technician = Depends(get_current_technician),
    business: Business = Depends(get_business_from_token),
):
    """Get technician's profile information."""
    return {
        "id": str(technician.id),
        "name": technician.name,
        "email": technician.email,
        "phone": technician.phone,
        "is_on_call": technician.is_on_call,
        "business_name": business.name,
    }


@router.patch("/profile")
async def update_profile(
    db: AsyncSession = Depends(get_db),
    technician: Technician = Depends(get_current_technician),
    push_token: Optional[str] = None,
    app_platform: Optional[str] = None,
):
    """Update technician's profile (push token, etc.)."""
    if push_token is not None:
        technician.push_token = push_token
    if app_platform is not None:
        technician.app_platform = app_platform
    
    technician.updated_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "Profile updated"}


# =============================================================================
# Helper Functions
# =============================================================================

def _job_to_response(job: Job) -> TechJobResponse:
    """Convert Job model to TechJobResponse."""
    notes = []
    if hasattr(job, 'notes') and job.notes:
        notes = [
            {
                "id": str(note.id),
                "content": note.content,
                "author_name": note.author_name,
                "created_at": note.created_at.isoformat(),
            }
            for note in job.notes
        ]
    
    return TechJobResponse(
        id=str(job.id),
        confirmation_code=job.confirmation_code or "",
        status=job.status.value,
        priority=job.priority.value,
        service_type=job.service_type,
        description=job.description,
        customer_name=job.customer.name if job.customer else None,
        customer_phone=job.customer.phone if job.customer else None,
        address_street=job.address.street if job.address else None,
        address_city=job.address.city if job.address else None,
        address_state=job.address.state if job.address else None,
        address_zip=job.address.zip_code if job.address else None,
        address_full=job.address.full_address if job.address else None,
        gate_code=job.address.gate_code if job.address else None,
        access_notes=job.address.access_notes if job.address else None,
        latitude=job.address.latitude if job.address else None,
        longitude=job.address.longitude if job.address else None,
        scheduled_date=job.scheduled_date,
        scheduled_time_start=str(job.scheduled_time_start) if job.scheduled_time_start else None,
        scheduled_time_end=str(job.scheduled_time_end) if job.scheduled_time_end else None,
        notes=notes,
        created_at=job.created_at,
    )
