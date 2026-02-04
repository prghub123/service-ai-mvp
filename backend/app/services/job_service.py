"""Job service - handles job-related business logic."""

import secrets
import string
from datetime import datetime, date, time
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from app.models.job import Job, JobStatus, JobPriority, JobSource, JobNote, JobStatusHistory
from app.models.customer import CustomerAddress
from app.schemas.job import JobCreate, JobUpdate, JobStatusUpdate, JobNoteCreate
from app.services.notification_service import NotificationService
from app.config import get_settings

settings = get_settings()


def generate_confirmation_code() -> str:
    """Generate a unique confirmation code like 'SVC-A1B2C3'."""
    chars = string.ascii_uppercase + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(6))
    return f"SVC-{random_part}"


class JobService:
    """Service for job operations."""
    
    def __init__(self, db: AsyncSession, business_id: UUID):
        self.db = db
        self.business_id = business_id
    
    async def get_by_id(self, job_id: UUID) -> Optional[Job]:
        """Get job by ID with all relations."""
        result = await self.db.execute(
            select(Job)
            .options(
                selectinload(Job.customer),
                selectinload(Job.technician),
                selectinload(Job.address),
                selectinload(Job.notes),
            )
            .where(
                Job.id == job_id,
                Job.business_id == self.business_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_by_confirmation_code(self, code: str) -> Optional[Job]:
        """Get job by confirmation code."""
        result = await self.db.execute(
            select(Job)
            .options(
                selectinload(Job.customer),
                selectinload(Job.technician),
                selectinload(Job.address),
            )
            .where(
                Job.confirmation_code == code,
                Job.business_id == self.business_id
            )
        )
        return result.scalar_one_or_none()
    
    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        technician_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Job], int]:
        """List jobs with filters and pagination."""
        query = (
            select(Job)
            .options(
                selectinload(Job.customer),
                selectinload(Job.technician),
                selectinload(Job.address),
            )
            .where(Job.business_id == self.business_id)
        )
        
        # Apply filters
        if status:
            query = query.where(Job.status == status)
        if date_from:
            query = query.where(Job.scheduled_date >= date_from)
        if date_to:
            query = query.where(Job.scheduled_date <= date_to)
        if technician_id:
            query = query.where(Job.technician_id == technician_id)
        if customer_id:
            query = query.where(Job.customer_id == customer_id)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()
        
        # Apply pagination
        query = query.order_by(Job.scheduled_date, Job.scheduled_time_start)
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        jobs = list(result.scalars())
        
        return jobs, total
    
    async def create(
        self,
        customer_id: UUID,
        data: JobCreate,
        source: JobSource = JobSource.CUSTOMER_APP,
        priority: JobPriority = JobPriority.NORMAL,
        source_call_id: Optional[str] = None,
        emergency_keywords_matched: bool = False,
        emergency_confidence_score: Optional[str] = None,
    ) -> Job:
        """Create a new job."""
        
        # Handle address - either use existing or create from inline
        address_id = data.address_id
        if not address_id and data.address:
            # Create address from inline data
            address = CustomerAddress(
                customer_id=customer_id,
                label="Service Address",
                street=data.address.street,
                unit=data.address.unit,
                city=data.address.city,
                state=data.address.state,
                zip_code=data.address.zip_code,
                gate_code=data.address.gate_code,
                access_notes=data.address.access_notes,
            )
            self.db.add(address)
            await self.db.flush()
            address_id = address.id
        
        # Create job
        job = Job(
            business_id=self.business_id,
            customer_id=customer_id,
            address_id=address_id,
            service_type=data.service_type,
            description=data.description,
            priority=priority,
            status=JobStatus.PENDING,
            source=source,
            source_call_id=source_call_id,
            scheduled_date=data.preferred_date,
            scheduled_time_start=data.preferred_time_start,
            scheduled_time_end=data.preferred_time_end,
            confirmation_code=generate_confirmation_code(),
            emergency_keywords_matched=emergency_keywords_matched,
            emergency_confidence_score=emergency_confidence_score,
        )
        
        self.db.add(job)
        
        # Record initial status
        history = JobStatusHistory(
            job_id=job.id,
            from_status=None,
            to_status=JobStatus.PENDING.value,
            changed_by_type="system",
            reason="Job created",
        )
        self.db.add(history)
        
        try:
            await self.db.commit()
            await self.db.refresh(job)
        except IntegrityError:
            await self.db.rollback()
            raise ValueError("Time slot is no longer available")
        
        return job
    
    async def create_emergency(
        self,
        customer_id: UUID,
        address_id: UUID,
        service_type: str,
        description: str,
        technician_id: UUID,
        source_call_id: Optional[str] = None,
    ) -> Job:
        """Create an emergency job with auto-assignment."""
        
        job = Job(
            business_id=self.business_id,
            customer_id=customer_id,
            address_id=address_id,
            technician_id=technician_id,
            service_type=service_type,
            description=description,
            priority=JobPriority.EMERGENCY,
            status=JobStatus.DISPATCHED,
            source=JobSource.PHONE_AGENT,
            source_call_id=source_call_id,
            scheduled_date=date.today(),
            confirmation_code=generate_confirmation_code(),
            emergency_keywords_matched=True,
            assigned_at=datetime.utcnow(),
        )
        
        self.db.add(job)
        
        # Record status
        history = JobStatusHistory(
            job_id=job.id,
            from_status=None,
            to_status=JobStatus.DISPATCHED.value,
            changed_by_type="system",
            reason="Emergency auto-dispatch",
        )
        self.db.add(history)
        
        await self.db.commit()
        await self.db.refresh(job)
        
        return job
    
    async def assign_technician(
        self,
        job_id: UUID,
        technician_id: UUID,
        changed_by_type: str = "admin",
        changed_by_id: Optional[UUID] = None,
    ) -> Optional[Job]:
        """Assign a technician to a job."""
        job = await self.get_by_id(job_id)
        if not job:
            return None
        
        old_status = job.status
        job.technician_id = technician_id
        job.assigned_at = datetime.utcnow()
        
        # Update status if pending
        if job.status == JobStatus.PENDING:
            job.status = JobStatus.SCHEDULED
            
            # Record status change
            history = JobStatusHistory(
                job_id=job.id,
                from_status=old_status.value,
                to_status=JobStatus.SCHEDULED.value,
                changed_by_type=changed_by_type,
                changed_by_id=changed_by_id,
                reason="Technician assigned",
            )
            self.db.add(history)
        
        job.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(job)
        
        return job
    
    async def update_status(
        self,
        job_id: UUID,
        data: JobStatusUpdate,
        changed_by_type: str,
        changed_by_id: Optional[UUID] = None,
    ) -> Optional[Job]:
        """Update job status."""
        job = await self.get_by_id(job_id)
        if not job:
            return None
        
        old_status = job.status
        job.status = data.status
        job.updated_at = datetime.utcnow()
        
        # Set timestamps based on status
        if data.status == JobStatus.EN_ROUTE:
            job.started_at = datetime.utcnow()
        elif data.status == JobStatus.COMPLETED:
            job.completed_at = datetime.utcnow()
        elif data.status == JobStatus.CANCELLED:
            job.cancelled_at = datetime.utcnow()
        
        # Record status change
        history = JobStatusHistory(
            job_id=job.id,
            from_status=old_status.value,
            to_status=data.status.value,
            changed_by_type=changed_by_type,
            changed_by_id=changed_by_id,
            reason=data.reason,
        )
        self.db.add(history)
        
        await self.db.commit()
        await self.db.refresh(job)
        
        return job
    
    async def add_note(
        self,
        job_id: UUID,
        data: JobNoteCreate,
        author_type: str,
        author_id: Optional[UUID] = None,
        author_name: Optional[str] = None,
    ) -> Optional[JobNote]:
        """Add a note to a job."""
        job = await self.get_by_id(job_id)
        if not job:
            return None
        
        note = JobNote(
            job_id=job_id,
            content=data.content,
            author_type=author_type,
            author_id=author_id,
            author_name=author_name,
        )
        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)
        
        return note
    
    async def get_pending_jobs_for_escalation(self) -> List[Job]:
        """Get jobs that need escalation."""
        result = await self.db.execute(
            select(Job)
            .where(
                Job.business_id == self.business_id,
                Job.status == JobStatus.PENDING,
                Job.technician_id.is_(None),
            )
            .order_by(Job.created_at)
        )
        return list(result.scalars())
    
    async def update_escalation_level(self, job_id: UUID, level: int) -> None:
        """Update job escalation level."""
        job = await self.get_by_id(job_id)
        if job:
            job.escalation_level = str(level)
            job.last_escalation_at = datetime.utcnow()
            await self.db.commit()
    
    async def get_jobs_by_call_id(self, call_id: str) -> Optional[Job]:
        """Get job by source call ID (for reconciliation)."""
        result = await self.db.execute(
            select(Job).where(
                Job.source_call_id == call_id,
                Job.business_id == self.business_id
            )
        )
        return result.scalar_one_or_none()
