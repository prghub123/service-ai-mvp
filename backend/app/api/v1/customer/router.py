"""Customer API routes for the mobile app."""

from datetime import date, datetime, time
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.database import get_db
from app.api.deps import get_current_customer, get_business_from_token
from app.models.customer import Customer, CustomerAddress
from app.models.business import Business
from app.models.job import Job, JobStatus, JobPriority, JobSource
from app.models.technician import Technician
from app.services.job_service import JobService
from app.services.schedule_service import ScheduleService
from app.schemas.job import JobCreate, AddressInline

router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================

class CustomerJobResponse(BaseModel):
    """Job response for customer app."""
    id: str
    confirmation_code: str
    status: str
    priority: str
    service_type: str
    description: Optional[str]
    
    # Address
    address: Optional[str]
    
    # Schedule
    scheduled_date: Optional[date]
    scheduled_time_start: Optional[str]
    scheduled_time_end: Optional[str]
    
    # Technician (when assigned)
    technician_name: Optional[str]
    technician_phone: Optional[str]
    technician_eta: Optional[str] = None  # Estimated time of arrival
    
    # Tracking
    technician_latitude: Optional[float] = None
    technician_longitude: Optional[float] = None
    
    created_at: datetime

    class Config:
        from_attributes = True


class CreateJobRequest(BaseModel):
    """Request to create a new job/service request."""
    service_type: str
    description: str
    address_id: Optional[str] = None  # Use existing address
    # Or provide new address
    address_street: Optional[str] = None
    address_unit: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    gate_code: Optional[str] = None
    access_notes: Optional[str] = None
    # Scheduling preferences
    preferred_date: Optional[date] = None
    preferred_time_start: Optional[str] = None  # "09:00"
    preferred_time_end: Optional[str] = None    # "11:00"
    is_emergency: bool = False


class AddressResponse(BaseModel):
    """Customer address response."""
    id: str
    label: str
    street: str
    unit: Optional[str]
    city: str
    state: str
    zip_code: str
    gate_code: Optional[str]
    access_notes: Optional[str]
    is_default: bool
    full_address: str

    class Config:
        from_attributes = True


class AddAddressRequest(BaseModel):
    """Request to add a new address."""
    label: str = "Home"
    street: str
    unit: Optional[str] = None
    city: str
    state: str
    zip_code: str
    gate_code: Optional[str] = None
    access_notes: Optional[str] = None
    is_default: bool = False


class UpdateProfileRequest(BaseModel):
    """Request to update customer profile."""
    name: Optional[str] = None
    email: Optional[str] = None
    push_token: Optional[str] = None
    app_platform: Optional[str] = None


class AvailableSlot(BaseModel):
    """Available time slot for scheduling."""
    date: date
    time_start: str
    time_end: str
    available: bool = True


# =============================================================================
# Profile
# =============================================================================

@router.get("/profile")
async def get_profile(
    customer: Customer = Depends(get_current_customer),
    business: Business = Depends(get_business_from_token),
):
    """Get customer's profile information."""
    return {
        "id": str(customer.id),
        "name": customer.name,
        "phone": customer.phone,
        "email": customer.email,
        "business_name": business.name,
        "business_phone": business.phone,
    }


@router.patch("/profile")
async def update_profile(
    data: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
):
    """Update customer's profile."""
    if data.name is not None:
        customer.name = data.name
    if data.email is not None:
        customer.email = data.email
    if data.push_token is not None:
        customer.push_token = data.push_token
    if data.app_platform is not None:
        customer.app_platform = data.app_platform
    
    customer.updated_at = datetime.utcnow()
    customer.last_active_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "Profile updated"}


# =============================================================================
# Addresses
# =============================================================================

@router.get("/addresses", response_model=List[AddressResponse])
async def get_addresses(
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
):
    """Get all customer addresses."""
    result = await db.execute(
        select(CustomerAddress)
        .where(CustomerAddress.customer_id == customer.id)
        .order_by(CustomerAddress.is_default.desc(), CustomerAddress.created_at)
    )
    addresses = result.scalars().all()
    
    return [
        AddressResponse(
            id=str(addr.id),
            label=addr.label,
            street=addr.street,
            unit=addr.unit,
            city=addr.city,
            state=addr.state,
            zip_code=addr.zip_code,
            gate_code=addr.gate_code,
            access_notes=addr.access_notes,
            is_default=addr.is_default,
            full_address=addr.full_address,
        )
        for addr in addresses
    ]


@router.post("/addresses", response_model=AddressResponse)
async def add_address(
    data: AddAddressRequest,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
):
    """Add a new address."""
    # If this is set as default, unset other defaults
    if data.is_default:
        result = await db.execute(
            select(CustomerAddress).where(
                CustomerAddress.customer_id == customer.id,
                CustomerAddress.is_default == True
            )
        )
        for addr in result.scalars():
            addr.is_default = False
    
    address = CustomerAddress(
        customer_id=customer.id,
        label=data.label,
        street=data.street,
        unit=data.unit,
        city=data.city,
        state=data.state,
        zip_code=data.zip_code,
        gate_code=data.gate_code,
        access_notes=data.access_notes,
        is_default=data.is_default,
    )
    
    db.add(address)
    await db.commit()
    await db.refresh(address)
    
    return AddressResponse(
        id=str(address.id),
        label=address.label,
        street=address.street,
        unit=address.unit,
        city=address.city,
        state=address.state,
        zip_code=address.zip_code,
        gate_code=address.gate_code,
        access_notes=address.access_notes,
        is_default=address.is_default,
        full_address=address.full_address,
    )


@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: str,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
):
    """Delete an address."""
    result = await db.execute(
        select(CustomerAddress).where(
            CustomerAddress.id == UUID(address_id),
            CustomerAddress.customer_id == customer.id
        )
    )
    address = result.scalar_one_or_none()
    
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    await db.delete(address)
    await db.commit()
    
    return {"message": "Address deleted"}


# =============================================================================
# Jobs
# =============================================================================

@router.get("/jobs", response_model=List[CustomerJobResponse])
async def get_my_jobs(
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
    status_filter: Optional[str] = Query(None, alias="status"),
    include_completed: bool = Query(False),
):
    """Get customer's jobs."""
    query = (
        select(Job)
        .options(
            selectinload(Job.address),
            selectinload(Job.technician),
        )
        .where(Job.customer_id == customer.id)
    )
    
    if status_filter:
        try:
            status_enum = JobStatus(status_filter)
            query = query.where(Job.status == status_enum)
        except ValueError:
            pass
    elif not include_completed:
        # By default, exclude completed and cancelled
        query = query.where(
            Job.status.notin_([JobStatus.COMPLETED, JobStatus.CANCELLED])
        )
    
    query = query.order_by(Job.created_at.desc())
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return [_job_to_customer_response(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=CustomerJobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
):
    """Get a specific job."""
    query = (
        select(Job)
        .options(
            selectinload(Job.address),
            selectinload(Job.technician),
        )
        .where(
            Job.id == UUID(job_id),
            Job.customer_id == customer.id
        )
    )
    
    result = await db.execute(query)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return _job_to_customer_response(job)


@router.post("/jobs", response_model=CustomerJobResponse)
async def create_job(
    data: CreateJobRequest,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
    business: Business = Depends(get_business_from_token),
):
    """Create a new service request."""
    job_service = JobService(db, business.id)
    
    # Determine address
    address_id = None
    address_inline = None
    
    if data.address_id:
        # Verify address belongs to customer
        result = await db.execute(
            select(CustomerAddress).where(
                CustomerAddress.id == UUID(data.address_id),
                CustomerAddress.customer_id == customer.id
            )
        )
        address = result.scalar_one_or_none()
        if not address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found"
            )
        address_id = address.id
    elif data.address_street:
        # Create new address inline
        address_inline = AddressInline(
            street=data.address_street,
            unit=data.address_unit,
            city=data.address_city or "",
            state=data.address_state or "",
            zip_code=data.address_zip or "",
            gate_code=data.gate_code,
            access_notes=data.access_notes,
        )
    else:
        # Try to use default address
        result = await db.execute(
            select(CustomerAddress).where(
                CustomerAddress.customer_id == customer.id,
                CustomerAddress.is_default == True
            )
        )
        default_address = result.scalar_one_or_none()
        if default_address:
            address_id = default_address.id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide an address"
            )
    
    # Parse time if provided
    time_start = None
    time_end = None
    if data.preferred_time_start:
        try:
            time_start = time.fromisoformat(data.preferred_time_start)
        except ValueError:
            pass
    if data.preferred_time_end:
        try:
            time_end = time.fromisoformat(data.preferred_time_end)
        except ValueError:
            pass
    
    # Determine priority
    priority = JobPriority.EMERGENCY if data.is_emergency else JobPriority.NORMAL
    
    # Create job
    job_data = JobCreate(
        service_type=data.service_type,
        description=data.description,
        address_id=address_id,
        address=address_inline,
        preferred_date=data.preferred_date,
        preferred_time_start=time_start,
        preferred_time_end=time_end,
    )
    
    job = await job_service.create(
        customer_id=customer.id,
        data=job_data,
        source=JobSource.CUSTOMER_APP,
        priority=priority,
    )
    
    # Reload with relationships
    result = await db.execute(
        select(Job)
        .options(
            selectinload(Job.address),
            selectinload(Job.technician),
        )
        .where(Job.id == job.id)
    )
    job = result.scalar_one()
    
    # TODO: Notify business owner of new job
    
    return _job_to_customer_response(job)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
    business: Business = Depends(get_business_from_token),
):
    """Cancel a job."""
    result = await db.execute(
        select(Job).where(
            Job.id == UUID(job_id),
            Job.customer_id == customer.id
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Can only cancel pending or scheduled jobs
    if job.status not in [JobStatus.PENDING, JobStatus.SCHEDULED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status {job.status.value}"
        )
    
    job_service = JobService(db, business.id)
    from app.schemas.job import JobStatusUpdate
    
    await job_service.update_status(
        job_id=UUID(job_id),
        data=JobStatusUpdate(status=JobStatus.CANCELLED, reason=reason or "Cancelled by customer"),
        changed_by_type="customer",
        changed_by_id=customer.id,
    )
    
    return {"message": "Job cancelled"}


# =============================================================================
# Availability
# =============================================================================

@router.get("/availability", response_model=List[AvailableSlot])
async def get_available_slots(
    service_type: str,
    days_ahead: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
    business: Business = Depends(get_business_from_token),
):
    """Get available time slots for booking."""
    schedule_service = ScheduleService(db, business.id)
    
    slots = []
    today = date.today()
    
    # Generate slots for the next N days
    # This is simplified - real implementation would check technician availability
    for i in range(days_ahead):
        check_date = today + timedelta(days=i + 1)  # Start from tomorrow
        
        # Skip weekends (simplified)
        if check_date.weekday() >= 5:
            continue
        
        # Generate time slots (9-11, 11-1, 1-3, 3-5)
        time_slots = [
            ("09:00", "11:00"),
            ("11:00", "13:00"),
            ("13:00", "15:00"),
            ("15:00", "17:00"),
        ]
        
        for start, end in time_slots:
            # Check availability (simplified - always available for now)
            slots.append(AvailableSlot(
                date=check_date,
                time_start=start,
                time_end=end,
                available=True,
            ))
    
    return slots


# =============================================================================
# Tracking
# =============================================================================

@router.get("/jobs/{job_id}/track")
async def track_technician(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
):
    """Get technician location for an active job."""
    result = await db.execute(
        select(Job)
        .options(selectinload(Job.technician))
        .where(
            Job.id == UUID(job_id),
            Job.customer_id == customer.id
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Only track for en_route or in_progress jobs
    if job.status not in [JobStatus.EN_ROUTE, JobStatus.IN_PROGRESS]:
        return {
            "tracking_available": False,
            "message": "Tracking only available when technician is en route",
        }
    
    if not job.technician:
        return {
            "tracking_available": False,
            "message": "No technician assigned yet",
        }
    
    tech = job.technician
    
    return {
        "tracking_available": True,
        "technician_name": tech.name,
        "technician_phone": tech.phone,
        "latitude": tech.current_latitude,
        "longitude": tech.current_longitude,
        "location_updated_at": tech.location_updated_at.isoformat() if tech.location_updated_at else None,
    }


# =============================================================================
# Helper Functions
# =============================================================================

def _job_to_customer_response(job: Job) -> CustomerJobResponse:
    """Convert Job model to CustomerJobResponse."""
    tech_lat = None
    tech_lng = None
    
    # Only include technician location for active jobs
    if job.technician and job.status in [JobStatus.EN_ROUTE, JobStatus.IN_PROGRESS]:
        tech_lat = job.technician.current_latitude
        tech_lng = job.technician.current_longitude
    
    return CustomerJobResponse(
        id=str(job.id),
        confirmation_code=job.confirmation_code or "",
        status=job.status.value,
        priority=job.priority.value,
        service_type=job.service_type,
        description=job.description,
        address=job.address.full_address if job.address else None,
        scheduled_date=job.scheduled_date,
        scheduled_time_start=str(job.scheduled_time_start) if job.scheduled_time_start else None,
        scheduled_time_end=str(job.scheduled_time_end) if job.scheduled_time_end else None,
        technician_name=job.technician.name if job.technician else None,
        technician_phone=job.technician.phone if job.technician else None,
        technician_latitude=tech_lat,
        technician_longitude=tech_lng,
        created_at=job.created_at,
    )


# Import timedelta for availability
from datetime import timedelta
