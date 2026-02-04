"""Tools for job-related operations."""

from typing import Optional
from uuid import UUID
from datetime import date, time
from langchain.tools import tool


def create_job_tools(db_session, business_id: UUID):
    """Create job tools bound to a specific session and business."""
    
    @tool
    async def create_job(
        customer_id: str,
        service_type: str,
        description: str,
        address_id: str,
        preferred_date: str,
        preferred_time_start: str,
        preferred_time_end: str,
        priority: str = "normal",
    ) -> dict:
        """
        Create a new service job.
        Returns the job ID and confirmation code.
        """
        from app.services.job_service import JobService
        from app.schemas.job import JobCreate
        from app.models.job import JobPriority, JobSource
        
        service = JobService(db_session, business_id)
        
        # Parse priority
        priority_map = {
            "low": JobPriority.LOW,
            "normal": JobPriority.NORMAL,
            "urgent": JobPriority.URGENT,
            "emergency": JobPriority.EMERGENCY,
        }
        
        job = await service.create(
            customer_id=UUID(customer_id),
            data=JobCreate(
                service_type=service_type,
                description=description,
                address_id=UUID(address_id),
                preferred_date=date.fromisoformat(preferred_date),
                preferred_time_start=time.fromisoformat(preferred_time_start),
                preferred_time_end=time.fromisoformat(preferred_time_end),
            ),
            source=JobSource.PHONE_AGENT,
            priority=priority_map.get(priority, JobPriority.NORMAL),
        )
        
        return {
            "job_id": str(job.id),
            "confirmation_code": job.confirmation_code,
            "status": job.status.value,
            "scheduled_date": str(job.scheduled_date),
            "scheduled_time": f"{job.scheduled_time_start}-{job.scheduled_time_end}",
        }
    
    @tool
    async def create_emergency_job(
        customer_id: str,
        address_id: str,
        service_type: str,
        description: str,
        technician_id: str,
    ) -> dict:
        """
        Create an emergency job with auto-assignment.
        Used when urgency is detected as emergency.
        """
        from app.services.job_service import JobService
        
        service = JobService(db_session, business_id)
        
        job = await service.create_emergency(
            customer_id=UUID(customer_id),
            address_id=UUID(address_id),
            service_type=service_type,
            description=description,
            technician_id=UUID(technician_id),
        )
        
        return {
            "job_id": str(job.id),
            "confirmation_code": job.confirmation_code,
            "status": job.status.value,
            "technician_assigned": True,
        }
    
    @tool
    async def get_job_by_confirmation_code(confirmation_code: str) -> dict:
        """
        Look up a job by its confirmation code.
        Used when customer calls about an existing job.
        """
        from app.services.job_service import JobService
        
        service = JobService(db_session, business_id)
        job = await service.get_by_confirmation_code(confirmation_code)
        
        if not job:
            return {"found": False}
        
        return {
            "found": True,
            "job_id": str(job.id),
            "service_type": job.service_type,
            "status": job.status.value,
            "scheduled_date": str(job.scheduled_date) if job.scheduled_date else None,
            "technician_name": job.technician.name if job.technician else None,
        }
    
    return [
        create_job,
        create_emergency_job,
        get_job_by_confirmation_code,
    ]
