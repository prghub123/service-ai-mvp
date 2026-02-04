"""Technician app endpoints."""

from datetime import date
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_technician, get_current_business
from app.models.technician import Technician
from app.models.business import Business
from app.models.job import JobStatus
from app.schemas.job import TechnicianJobResponse, JobStatusUpdate, JobNoteCreate, JobNoteResponse
from app.schemas.technician import TechnicianLocationUpdate
from app.services.job_service import JobService
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("/me/jobs", response_model=List[TechnicianJobResponse])
async def get_my_jobs(
    date_filter: Optional[date] = Query(None, description="Filter by date (default: today)"),
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    technician: Technician = Depends(get_current_technician),
):
    """Get technician's assigned jobs."""
    job_service = JobService(db, business.id)
    
    # Default to today
    filter_date = date_filter or date.today()
    
    jobs, _ = await job_service.list_jobs(
        technician_id=technician.id,
        date_from=filter_date,
        date_to=filter_date,
        page=1,
        page_size=50,
    )
    
    # Convert to technician view (includes customer contact info)
    result = []
    for job in jobs:
        result.append(TechnicianJobResponse(
            id=job.id,
            confirmation_code=job.confirmation_code,
            service_type=job.service_type,
            description=job.description,
            priority=job.priority,
            status=job.status,
            scheduled_date=job.scheduled_date,
            scheduled_time_start=job.scheduled_time_start,
            scheduled_time_end=job.scheduled_time_end,
            customer_name=job.customer.name if job.customer else None,
            customer_phone=job.customer.phone if job.customer else "",
            address_street=job.address.street if job.address else "",
            address_unit=job.address.unit if job.address else None,
            address_city=job.address.city if job.address else "",
            address_state=job.address.state if job.address else "",
            address_zip=job.address.zip_code if job.address else "",
            address_full=job.address.full_address if job.address else "",
            address_latitude=job.address.latitude if job.address else None,
            address_longitude=job.address.longitude if job.address else None,
            gate_code=job.address.gate_code if job.address else None,
            access_notes=job.address.access_notes if job.address else None,
            notes=[JobNoteResponse.model_validate(n) for n in job.notes],
            created_at=job.created_at,
        ))
    
    return result


@router.get("/me/jobs/{job_id}", response_model=TechnicianJobResponse)
async def get_job_detail(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    technician: Technician = Depends(get_current_technician),
):
    """Get a specific job assigned to this technician."""
    job_service = JobService(db, business.id)
    
    job = await job_service.get_by_id(job_id)
    
    if not job or job.technician_id != technician.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return TechnicianJobResponse(
        id=job.id,
        confirmation_code=job.confirmation_code,
        service_type=job.service_type,
        description=job.description,
        priority=job.priority,
        status=job.status,
        scheduled_date=job.scheduled_date,
        scheduled_time_start=job.scheduled_time_start,
        scheduled_time_end=job.scheduled_time_end,
        customer_name=job.customer.name if job.customer else None,
        customer_phone=job.customer.phone if job.customer else "",
        address_street=job.address.street if job.address else "",
        address_unit=job.address.unit if job.address else None,
        address_city=job.address.city if job.address else "",
        address_state=job.address.state if job.address else "",
        address_zip=job.address.zip_code if job.address else "",
        address_full=job.address.full_address if job.address else "",
        address_latitude=job.address.latitude if job.address else None,
        address_longitude=job.address.longitude if job.address else None,
        gate_code=job.address.gate_code if job.address else None,
        access_notes=job.address.access_notes if job.address else None,
        notes=[JobNoteResponse.model_validate(n) for n in job.notes],
        created_at=job.created_at,
    )


@router.patch("/me/jobs/{job_id}/status", response_model=TechnicianJobResponse)
async def update_job_status(
    job_id: UUID,
    data: JobStatusUpdate,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    technician: Technician = Depends(get_current_technician),
):
    """
    Update job status.
    Allowed transitions:
    - SCHEDULED/DISPATCHED -> EN_ROUTE (starting job)
    - EN_ROUTE -> IN_PROGRESS (arrived)
    - IN_PROGRESS -> COMPLETED (finished)
    """
    job_service = JobService(db, business.id)
    notification_service = NotificationService(db, business.id)
    
    job = await job_service.get_by_id(job_id)
    
    if not job or job.technician_id != technician.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Validate status transition
    valid_transitions = {
        JobStatus.SCHEDULED: [JobStatus.EN_ROUTE],
        JobStatus.DISPATCHED: [JobStatus.EN_ROUTE],
        JobStatus.EN_ROUTE: [JobStatus.IN_PROGRESS],
        JobStatus.IN_PROGRESS: [JobStatus.COMPLETED, JobStatus.AWAITING_PARTS],
        JobStatus.AWAITING_PARTS: [JobStatus.IN_PROGRESS, JobStatus.COMPLETED],
    }
    
    allowed = valid_transitions.get(job.status, [])
    if data.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition from {job.status.value} to {data.status.value}"
        )
    
    # Update status
    updated_job = await job_service.update_status(
        job_id=job_id,
        data=data,
        changed_by_type="technician",
        changed_by_id=technician.id,
    )
    
    # Send notifications based on status
    if data.status == JobStatus.EN_ROUTE and job.customer:
        await notification_service.notify_tech_en_route(
            job=updated_job,
            customer=job.customer,
            technician=technician,
            eta_minutes=15,  # TODO: Calculate actual ETA
        )
    
    # Reload and return
    job = await job_service.get_by_id(job_id)
    return TechnicianJobResponse(
        id=job.id,
        confirmation_code=job.confirmation_code,
        service_type=job.service_type,
        description=job.description,
        priority=job.priority,
        status=job.status,
        scheduled_date=job.scheduled_date,
        scheduled_time_start=job.scheduled_time_start,
        scheduled_time_end=job.scheduled_time_end,
        customer_name=job.customer.name if job.customer else None,
        customer_phone=job.customer.phone if job.customer else "",
        address_street=job.address.street if job.address else "",
        address_unit=job.address.unit if job.address else None,
        address_city=job.address.city if job.address else "",
        address_state=job.address.state if job.address else "",
        address_zip=job.address.zip_code if job.address else "",
        address_full=job.address.full_address if job.address else "",
        address_latitude=job.address.latitude if job.address else None,
        address_longitude=job.address.longitude if job.address else None,
        gate_code=job.address.gate_code if job.address else None,
        access_notes=job.address.access_notes if job.address else None,
        notes=[JobNoteResponse.model_validate(n) for n in job.notes],
        created_at=job.created_at,
    )


@router.post("/me/jobs/{job_id}/notes", response_model=JobNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_job_note(
    job_id: UUID,
    data: JobNoteCreate,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    technician: Technician = Depends(get_current_technician),
):
    """Add a note to a job."""
    job_service = JobService(db, business.id)
    
    job = await job_service.get_by_id(job_id)
    
    if not job or job.technician_id != technician.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    note = await job_service.add_note(
        job_id=job_id,
        data=data,
        author_type="technician",
        author_id=technician.id,
        author_name=technician.name,
    )
    
    return note


@router.post("/me/location")
async def update_location(
    data: TechnicianLocationUpdate,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    technician: Technician = Depends(get_current_technician),
):
    """Update technician's current location."""
    from datetime import datetime
    
    technician.current_latitude = data.latitude
    technician.current_longitude = data.longitude
    technician.location_updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"status": "location updated"}
