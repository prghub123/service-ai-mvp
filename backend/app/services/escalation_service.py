"""Escalation service - handles job escalation for unassigned jobs."""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.models.business import Business
from app.services.notification_service import NotificationService
from app.services.job_service import JobService
from app.config import get_settings

settings = get_settings()


class EscalationService:
    """Service for handling job escalation ladder."""
    
    # Escalation levels and their delays (in minutes)
    ESCALATION_LEVELS = {
        0: {"delay_minutes": 0, "action": "initial_notification"},
        1: {"delay_minutes": 30, "action": "first_reminder"},
        2: {"delay_minutes": 120, "action": "second_reminder_call"},
        3: {"delay_minutes": 240, "action": "auto_assign_or_alert"},
        4: {"delay_minutes": 1440, "action": "customer_outreach"},
    }
    
    def __init__(self, db: AsyncSession, business_id: UUID):
        self.db = db
        self.business_id = business_id
        self.notification_service = NotificationService(db, business_id)
        self.job_service = JobService(db, business_id)
    
    async def check_and_escalate_jobs(self) -> List[dict]:
        """
        Check all pending jobs and escalate as needed.
        Returns list of actions taken.
        """
        actions = []
        
        # Get all pending unassigned jobs
        pending_jobs = await self.job_service.get_pending_jobs_for_escalation()
        
        for job in pending_jobs:
            action = await self._check_job_escalation(job)
            if action:
                actions.append(action)
        
        return actions
    
    async def _check_job_escalation(self, job: Job) -> Optional[dict]:
        """Check if a job needs escalation and perform it."""
        
        current_level = int(job.escalation_level or "0")
        job_age_minutes = (datetime.utcnow() - job.created_at).total_seconds() / 60
        
        # Find the appropriate escalation level
        next_level = None
        for level, config in self.ESCALATION_LEVELS.items():
            if level > current_level and job_age_minutes >= config["delay_minutes"]:
                next_level = level
        
        if next_level is None:
            return None
        
        # Perform escalation
        config = self.ESCALATION_LEVELS[next_level]
        action_taken = await self._perform_escalation(job, next_level, config["action"])
        
        # Update job escalation level
        await self.job_service.update_escalation_level(job.id, next_level)
        
        return {
            "job_id": str(job.id),
            "confirmation_code": job.confirmation_code,
            "previous_level": current_level,
            "new_level": next_level,
            "action": action_taken,
        }
    
    async def _perform_escalation(
        self, 
        job: Job, 
        level: int, 
        action: str
    ) -> str:
        """Perform the escalation action."""
        
        # Load customer for notifications
        await self.db.refresh(job, ["customer"])
        
        if action == "initial_notification":
            # Already sent when job created
            return "initial_notification_skipped"
        
        elif action == "first_reminder":
            message = (
                f"⚠️ Job {job.confirmation_code} needs assignment. "
                f"Service: {job.service_type}. "
                f"Created {self._format_age(job.created_at)} ago."
            )
            await self.notification_service.notify_owner(
                message=message,
                job_id=job.id,
                trigger_event="escalation_reminder_1",
            )
            return "first_reminder_sent"
        
        elif action == "second_reminder_call":
            message = (
                f"🚨 URGENT: Job {job.confirmation_code} still unassigned! "
                f"Customer waiting for {self._format_age(job.created_at)}. "
                f"Please assign immediately."
            )
            await self.notification_service.notify_owner(
                message=message,
                job_id=job.id,
                trigger_event="escalation_reminder_2",
                urgent=True,  # This triggers a phone call
            )
            return "second_reminder_with_call"
        
        elif action == "auto_assign_or_alert":
            # Check if business has auto-assign enabled
            business = await self._get_business()
            auto_assign = business.settings.get("auto_assign_enabled", False)
            
            if auto_assign:
                # Try to auto-assign
                assigned = await self._try_auto_assign(job)
                if assigned:
                    return "auto_assigned"
            
            # If not auto-assigned, send critical alert
            message = (
                f"🔴 CRITICAL: Job {job.confirmation_code} unassigned for "
                f"{self._format_age(job.created_at)}! "
                f"Customer may call competitor. Action required NOW."
            )
            await self.notification_service.notify_owner(
                message=message,
                job_id=job.id,
                trigger_event="escalation_critical",
                urgent=True,
            )
            return "critical_alert_sent"
        
        elif action == "customer_outreach":
            # Contact customer to apologize and offer to reschedule
            if job.customer:
                customer_message = (
                    f"We apologize for the delay in confirming your service request. "
                    f"We're working to assign a technician. "
                    f"Please call us if you need immediate assistance."
                )
                await self.notification_service.notify_customer(
                    customer=job.customer,
                    message=customer_message,
                    job_id=job.id,
                    trigger_event="escalation_customer_apology",
                )
            
            # Final owner alert
            message = (
                f"⛔ SLA BREACH: Job {job.confirmation_code} unassigned for 24+ hours. "
                f"Customer has been notified of delay. "
                f"This will affect service metrics."
            )
            await self.notification_service.notify_owner(
                message=message,
                job_id=job.id,
                trigger_event="escalation_sla_breach",
                urgent=True,
            )
            return "customer_outreach_completed"
        
        return "unknown_action"
    
    async def _try_auto_assign(self, job: Job) -> bool:
        """Attempt to auto-assign a technician to the job."""
        from app.services.schedule_service import ScheduleService
        
        if not job.address:
            return False
        
        schedule_service = ScheduleService(self.db, self.business_id)
        
        # Find available tech
        tech_info = await schedule_service.find_available_technician(
            service_type=job.service_type,
            location_lat=float(job.address.latitude or 0),
            location_lng=float(job.address.longitude or 0),
            urgency="normal",
        )
        
        if not tech_info:
            return False
        
        # Assign the technician
        await self.job_service.assign_technician(
            job_id=job.id,
            technician_id=tech_info["tech_id"],
            changed_by_type="system",
        )
        
        return True
    
    async def _get_business(self) -> Business:
        """Get the business entity."""
        result = await self.db.execute(
            select(Business).where(Business.id == self.business_id)
        )
        return result.scalar_one()
    
    def _format_age(self, created_at: datetime) -> str:
        """Format job age in human-readable form."""
        age = datetime.utcnow() - created_at
        minutes = int(age.total_seconds() / 60)
        
        if minutes < 60:
            return f"{minutes} minutes"
        elif minutes < 1440:
            hours = minutes // 60
            return f"{hours} hour{'s' if hours > 1 else ''}"
        else:
            days = minutes // 1440
            return f"{days} day{'s' if days > 1 else ''}"
