"""Job endpoints for customer app."""

from datetime import date
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_customer, get_current_business
from app.models.customer import Customer
from app.models.business import Business
from app.models.job import JobStatus, JobSource
from app.schemas.job import (
    JobCreate,
    JobResponse,
    JobListResponse,
    JobStatusUpdate,
)
from app.services.job_service import JobService
from app.services.schedule_service import ScheduleService
from app.services.notification_service import NotificationService

router = APIRouter()


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: JobCreate,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_current_customer),
):
    """
    Create a new job (self-service booking).
    Optionally use a reservation token to guarantee the slot.
    """
    job_service = JobService(db, business.id)
    schedule_service = ScheduleService(db, business.id)
    notification_service = NotificationService(db, business.id)
    
    # If reservation token provided, validate it
    if data.reservation_token:
        reservation = await schedule_service.validate_reservation(data.reservation_token)
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reservation token"
            )
        
        # Use reservation's slot
        data.preferred_date = reservation.slot_date
        data.preferred_time_start = reservation.slot_start_time
        data.preferred_time_end = reservation.slot_end_time
    
    # Validate address
    if not data.address_id and not data.address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either address_id or address is required"
        )
    
    # If using saved address, verify it belongs to customer
    if data.address_id:
        from app.services.customer_service import CustomerService
        customer_service = CustomerService(db, business.id)
        address = await customer_service.get_address(data.address_id, customer.id)
        if not address:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Address not found"
            )
    
    try:
        # Create the job
        job = await job_service.create(
            customer_id=customer.id,
            data=data,
            source=JobSource.CUSTOMER_APP,
        )
        
        # If we used a reservation, mark it as confirmed
        if data.reservation_token:
            await schedule_service.confirm_reservation(data.reservation_token, job.id)
        
        # Send notifications
        await notification_service.notify_job_created(job, customer)
        
        # Reload with relationships
        job = await job_service.get_by_id(job.id)
        
        return job
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: Optional[JobStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_current_customer),
):
    """List customer's jobs."""
    job_service = JobService(db, business.id)
    
    jobs, total = await job_service.list_jobs(
        customer_id=customer.id,
        status=status,
        page=page,
        page_size=page_size,
    )
    
    return JobListResponse(
        jobs=jobs,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_current_customer),
):
    """Get a specific job."""
    job_service = JobService(db, business.id)
    
    job = await job_service.get_by_id(job_id)
    
    if not job or job.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return job


@router.patch("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_current_customer),
):
    """Cancel a job (only if pending or scheduled)."""
    job_service = JobService(db, business.id)
    
    job = await job_service.get_by_id(job_id)
    
    if not job or job.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Only allow cancellation of pending/scheduled jobs
    if job.status not in [JobStatus.PENDING, JobStatus.SCHEDULED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job in {job.status} status"
        )
    
    updated = await job_service.update_status(
        job_id=job_id,
        data=JobStatusUpdate(status=JobStatus.CANCELLED, reason="Cancelled by customer"),
        changed_by_type="customer",
        changed_by_id=customer.id,
    )
    
    return updated


@router.get("/{job_id}/tracking")
async def get_job_tracking(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_current_customer),
):
    """Get real-time tracking info for a job (tech location, ETA)."""
    job_service = JobService(db, business.id)
    
    job = await job_service.get_by_id(job_id)
    
    if not job or job.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Only show tracking when tech is en route or in progress
    if job.status not in [JobStatus.EN_ROUTE, JobStatus.DISPATCHED]:
        return {
            "tracking_available": False,
            "status": job.status.value,
            "message": "Tracking is available once technician is on the way"
        }
    
    # Get technician location
    if job.technician:
        return {
            "tracking_available": True,
            "status": job.status.value,
            "technician_name": job.technician.name,
            "technician_phone": job.technician.phone,
            "latitude": job.technician.current_latitude,
            "longitude": job.technician.current_longitude,
            "location_updated_at": job.technician.location_updated_at,
            "eta_minutes": 15,  # TODO: Calculate actual ETA
        }
    
    return {
        "tracking_available": False,
        "status": job.status.value,
        "message": "No technician assigned"
    }
