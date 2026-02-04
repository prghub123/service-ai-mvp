"""Owner/Admin API routes for the web dashboard."""

from datetime import date, datetime, timedelta
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.api.deps import (
    get_current_user,
    get_business_from_token,
    hash_password,
)
from app.models.user import User, UserRole
from app.models.business import Business
from app.models.technician import Technician
from app.models.customer import Customer
from app.models.job import Job, JobStatus, JobPriority
from app.services.job_service import JobService
from app.services.schedule_service import ScheduleService

router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================

class DashboardStats(BaseModel):
    """Dashboard statistics."""
    total_jobs_today: int
    pending_jobs: int
    in_progress_jobs: int
    completed_today: int
    total_technicians: int
    active_technicians: int
    total_customers: int
    emergency_jobs: int


class JobResponse(BaseModel):
    """Job response for listings."""
    id: str
    confirmation_code: str
    status: str
    priority: str
    service_type: str
    description: Optional[str]
    customer_name: Optional[str]
    customer_phone: Optional[str]
    address: Optional[str]
    technician_name: Optional[str]
    technician_id: Optional[str]
    scheduled_date: Optional[date]
    scheduled_time_start: Optional[str]
    scheduled_time_end: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TechnicianResponse(BaseModel):
    """Technician response for listings."""
    id: str
    name: str
    phone: str
    email: Optional[str]
    is_active: bool
    is_on_call: bool
    current_job_count: int = 0

    class Config:
        from_attributes = True


class TechnicianCreate(BaseModel):
    """Create a new technician."""
    name: str
    email: EmailStr
    phone: str
    password: str


class CustomerResponse(BaseModel):
    """Customer response for listings."""
    id: str
    name: Optional[str]
    phone: str
    email: Optional[str]
    job_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class AssignTechnicianRequest(BaseModel):
    """Request to assign a technician to a job."""
    technician_id: str


# =============================================================================
# Dashboard
# =============================================================================

@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    business: Business = Depends(get_business_from_token),
):
    """Get dashboard statistics for the owner."""
    today = date.today()
    
    # Total jobs today
    result = await db.execute(
        select(func.count(Job.id)).where(
            Job.business_id == business.id,
            Job.scheduled_date == today
        )
    )
    total_jobs_today = result.scalar() or 0
    
    # Pending jobs (all time, not assigned)
    result = await db.execute(
        select(func.count(Job.id)).where(
            Job.business_id == business.id,
            Job.status == JobStatus.PENDING
        )
    )
    pending_jobs = result.scalar() or 0
    
    # In progress jobs
    result = await db.execute(
        select(func.count(Job.id)).where(
            Job.business_id == business.id,
            Job.status.in_([JobStatus.EN_ROUTE, JobStatus.IN_PROGRESS])
        )
    )
    in_progress_jobs = result.scalar() or 0
    
    # Completed today
    result = await db.execute(
        select(func.count(Job.id)).where(
            Job.business_id == business.id,
            Job.status == JobStatus.COMPLETED,
            func.date(Job.completed_at) == today
        )
    )
    completed_today = result.scalar() or 0
    
    # Total technicians
    result = await db.execute(
        select(func.count(Technician.id)).where(
            Technician.business_id == business.id
        )
    )
    total_technicians = result.scalar() or 0
    
    # Active technicians
    result = await db.execute(
        select(func.count(Technician.id)).where(
            Technician.business_id == business.id,
            Technician.is_active == True
        )
    )
    active_technicians = result.scalar() or 0
    
    # Total customers
    result = await db.execute(
        select(func.count(Customer.id)).where(
            Customer.business_id == business.id
        )
    )
    total_customers = result.scalar() or 0
    
    # Emergency jobs (pending or in progress)
    result = await db.execute(
        select(func.count(Job.id)).where(
            Job.business_id == business.id,
            Job.priority == JobPriority.EMERGENCY,
            Job.status.in_([JobStatus.PENDING, JobStatus.DISPATCHED, JobStatus.EN_ROUTE, JobStatus.IN_PROGRESS])
        )
    )
    emergency_jobs = result.scalar() or 0
    
    return DashboardStats(
        total_jobs_today=total_jobs_today,
        pending_jobs=pending_jobs,
        in_progress_jobs=in_progress_jobs,
        completed_today=completed_today,
        total_technicians=total_technicians,
        active_technicians=active_technicians,
        total_customers=total_customers,
        emergency_jobs=emergency_jobs,
    )


# =============================================================================
# Jobs Management
# =============================================================================

@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    business: Business = Depends(get_business_from_token),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    technician_id: Optional[str] = Query(None, description="Filter by technician"),
    date_from: Optional[date] = Query(None, description="Filter from date"),
    date_to: Optional[date] = Query(None, description="Filter to date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all jobs with filters."""
    from sqlalchemy.orm import selectinload
    
    query = (
        select(Job)
        .options(
            selectinload(Job.customer),
            selectinload(Job.technician),
            selectinload(Job.address),
        )
        .where(Job.business_id == business.id)
    )
    
    # Apply filters
    if status:
        try:
            status_enum = JobStatus(status)
            query = query.where(Job.status == status_enum)
        except ValueError:
            pass
    
    if priority:
        try:
            priority_enum = JobPriority(priority)
            query = query.where(Job.priority == priority_enum)
        except ValueError:
            pass
    
    if technician_id:
        query = query.where(Job.technician_id == UUID(technician_id))
    
    if date_from:
        query = query.where(Job.scheduled_date >= date_from)
    
    if date_to:
        query = query.where(Job.scheduled_date <= date_to)
    
    # Order and paginate
    query = query.order_by(Job.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return [
        JobResponse(
            id=str(job.id),
            confirmation_code=job.confirmation_code or "",
            status=job.status.value,
            priority=job.priority.value,
            service_type=job.service_type,
            description=job.description,
            customer_name=job.customer.name if job.customer else None,
            customer_phone=job.customer.phone if job.customer else None,
            address=job.address.full_address if job.address else None,
            technician_name=job.technician.name if job.technician else None,
            technician_id=str(job.technician_id) if job.technician_id else None,
            scheduled_date=job.scheduled_date,
            scheduled_time_start=str(job.scheduled_time_start) if job.scheduled_time_start else None,
            scheduled_time_end=str(job.scheduled_time_end) if job.scheduled_time_end else None,
            created_at=job.created_at,
        )
        for job in jobs
    ]


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    business: Business = Depends(get_business_from_token),
):
    """Get a specific job by ID."""
    job_service = JobService(db, business.id)
    job = await job_service.get_by_id(UUID(job_id))
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return JobResponse(
        id=str(job.id),
        confirmation_code=job.confirmation_code or "",
        status=job.status.value,
        priority=job.priority.value,
        service_type=job.service_type,
        description=job.description,
        customer_name=job.customer.name if job.customer else None,
        customer_phone=job.customer.phone if job.customer else None,
        address=job.address.full_address if job.address else None,
        technician_name=job.technician.name if job.technician else None,
        technician_id=str(job.technician_id) if job.technician_id else None,
        scheduled_date=job.scheduled_date,
        scheduled_time_start=str(job.scheduled_time_start) if job.scheduled_time_start else None,
        scheduled_time_end=str(job.scheduled_time_end) if job.scheduled_time_end else None,
        created_at=job.created_at,
    )


@router.post("/jobs/{job_id}/assign")
async def assign_technician_to_job(
    job_id: str,
    data: AssignTechnicianRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    business: Business = Depends(get_business_from_token),
):
    """Assign a technician to a job."""
    job_service = JobService(db, business.id)
    
    job = await job_service.assign_technician(
        job_id=UUID(job_id),
        technician_id=UUID(data.technician_id),
        changed_by_type="admin",
        changed_by_id=user.id,
    )
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # TODO: Send notification to technician
    
    return {"message": "Technician assigned successfully", "job_id": str(job.id)}


# =============================================================================
# Technicians Management
# =============================================================================

@router.get("/technicians", response_model=List[TechnicianResponse])
async def list_technicians(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    business: Business = Depends(get_business_from_token),
    active_only: bool = Query(False),
):
    """List all technicians."""
    query = select(Technician).where(Technician.business_id == business.id)
    
    if active_only:
        query = query.where(Technician.is_active == True)
    
    query = query.order_by(Technician.name)
    
    result = await db.execute(query)
    technicians = result.scalars().all()
    
    # Get job counts for each technician
    tech_responses = []
    for tech in technicians:
        # Count active jobs
        job_count_result = await db.execute(
            select(func.count(Job.id)).where(
                Job.technician_id == tech.id,
                Job.status.in_([JobStatus.SCHEDULED, JobStatus.EN_ROUTE, JobStatus.IN_PROGRESS])
            )
        )
        job_count = job_count_result.scalar() or 0
        
        tech_responses.append(TechnicianResponse(
            id=str(tech.id),
            name=tech.name,
            phone=tech.phone,
            email=tech.email,
            is_active=tech.is_active,
            is_on_call=tech.is_on_call,
            current_job_count=job_count,
        ))
    
    return tech_responses


@router.post("/technicians", response_model=TechnicianResponse)
async def create_technician(
    data: TechnicianCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    business: Business = Depends(get_business_from_token),
):
    """Create a new technician."""
    # Check if email already exists for this business
    result = await db.execute(
        select(Technician).where(
            Technician.email == data.email.lower(),
            Technician.business_id == business.id
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Technician with this email already exists"
        )
    
    technician = Technician(
        business_id=business.id,
        name=data.name,
        email=data.email.lower(),
        phone=data.phone,
        password_hash=hash_password(data.password),
        is_active=True,
    )
    
    db.add(technician)
    await db.commit()
    await db.refresh(technician)
    
    return TechnicianResponse(
        id=str(technician.id),
        name=technician.name,
        phone=technician.phone,
        email=technician.email,
        is_active=technician.is_active,
        is_on_call=technician.is_on_call,
        current_job_count=0,
    )


@router.patch("/technicians/{tech_id}")
async def update_technician(
    tech_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    business: Business = Depends(get_business_from_token),
    name: Optional[str] = None,
    phone: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_on_call: Optional[bool] = None,
):
    """Update a technician's details."""
    result = await db.execute(
        select(Technician).where(
            Technician.id == UUID(tech_id),
            Technician.business_id == business.id
        )
    )
    technician = result.scalar_one_or_none()
    
    if not technician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Technician not found"
        )
    
    if name is not None:
        technician.name = name
    if phone is not None:
        technician.phone = phone
    if is_active is not None:
        technician.is_active = is_active
    if is_on_call is not None:
        technician.is_on_call = is_on_call
    
    technician.updated_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "Technician updated successfully"}


# =============================================================================
# Customers Management
# =============================================================================

@router.get("/customers", response_model=List[CustomerResponse])
async def list_customers(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    business: Business = Depends(get_business_from_token),
    search: Optional[str] = Query(None, description="Search by name or phone"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all customers."""
    query = select(Customer).where(Customer.business_id == business.id)
    
    if search:
        query = query.where(
            (Customer.name.ilike(f"%{search}%")) |
            (Customer.phone.ilike(f"%{search}%"))
        )
    
    query = query.order_by(Customer.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    customers = result.scalars().all()
    
    # Get job counts
    customer_responses = []
    for customer in customers:
        job_count_result = await db.execute(
            select(func.count(Job.id)).where(Job.customer_id == customer.id)
        )
        job_count = job_count_result.scalar() or 0
        
        customer_responses.append(CustomerResponse(
            id=str(customer.id),
            name=customer.name,
            phone=customer.phone,
            email=customer.email,
            job_count=job_count,
            created_at=customer.created_at,
        ))
    
    return customer_responses


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    business: Business = Depends(get_business_from_token),
):
    """Get a specific customer."""
    result = await db.execute(
        select(Customer).where(
            Customer.id == UUID(customer_id),
            Customer.business_id == business.id
        )
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    job_count_result = await db.execute(
        select(func.count(Job.id)).where(Job.customer_id == customer.id)
    )
    job_count = job_count_result.scalar() or 0
    
    return CustomerResponse(
        id=str(customer.id),
        name=customer.name,
        phone=customer.phone,
        email=customer.email,
        job_count=job_count,
        created_at=customer.created_at,
    )
