"""Schedule service - handles availability and slot reservation."""

import secrets
from datetime import datetime, date, time, timedelta
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import ScheduleBlock, SlotReservation, TimeOff
from app.models.job import Job, JobStatus
from app.models.technician import Technician
from app.schemas.schedule import TimeSlot, DayAvailability
from app.database import get_redis
from app.config import get_settings

settings = get_settings()


class ScheduleService:
    """Service for schedule and availability operations."""
    
    def __init__(self, db: AsyncSession, business_id: UUID):
        self.db = db
        self.business_id = business_id
    
    async def get_availability(
        self,
        date_from: date,
        date_to: date,
        service_type: Optional[str] = None,
        technician_id: Optional[UUID] = None,
    ) -> List[DayAvailability]:
        """
        Get available time slots for a date range.
        Returns list of days with available windows.
        """
        availability = []
        current_date = date_from
        
        while current_date <= date_to:
            windows = await self._get_day_availability(
                current_date, service_type, technician_id
            )
            availability.append(DayAvailability(
                date=current_date,
                windows=windows
            ))
            current_date += timedelta(days=1)
        
        return availability
    
    async def _get_day_availability(
        self,
        check_date: date,
        service_type: Optional[str] = None,
        technician_id: Optional[UUID] = None,
    ) -> List[TimeSlot]:
        """Get available windows for a specific day."""
        
        day_of_week = check_date.weekday()  # 0=Monday in Python
        # Convert to our format (0=Sunday)
        day_of_week = (day_of_week + 1) % 7
        
        # Get schedule blocks for this day
        query = select(ScheduleBlock).where(
            ScheduleBlock.business_id == self.business_id,
            ScheduleBlock.day_of_week == day_of_week,
            ScheduleBlock.is_available == True
        )
        if technician_id:
            query = query.where(
                or_(
                    ScheduleBlock.technician_id == technician_id,
                    ScheduleBlock.technician_id.is_(None)
                )
            )
        
        result = await self.db.execute(query)
        schedule_blocks = list(result.scalars())
        
        if not schedule_blocks:
            # No schedule defined, return empty
            return []
        
        # Get existing jobs for this day
        jobs_query = select(Job).where(
            Job.business_id == self.business_id,
            Job.scheduled_date == check_date,
            Job.status.not_in([JobStatus.CANCELLED])
        )
        if technician_id:
            jobs_query = jobs_query.where(Job.technician_id == technician_id)
        
        jobs_result = await self.db.execute(jobs_query)
        existing_jobs = list(jobs_result.scalars())
        
        # Get active reservations
        redis = await get_redis()
        reserved_slots = await self._get_reserved_slots(check_date)
        
        # Get time off
        time_off_query = select(TimeOff).where(
            TimeOff.business_id == self.business_id,
            TimeOff.start_date <= check_date,
            TimeOff.end_date >= check_date
        )
        if technician_id:
            time_off_query = time_off_query.where(
                or_(
                    TimeOff.technician_id == technician_id,
                    TimeOff.technician_id.is_(None)
                )
            )
        time_off_result = await self.db.execute(time_off_query)
        time_offs = list(time_off_result.scalars())
        
        # Generate time slots (2-hour windows by default)
        windows = []
        slot_duration = timedelta(hours=2)
        
        for block in schedule_blocks:
            current_time = datetime.combine(check_date, block.start_time)
            end_time = datetime.combine(check_date, block.end_time)
            
            while current_time + slot_duration <= end_time:
                slot_start = current_time.time()
                slot_end = (current_time + slot_duration).time()
                
                # Check if slot is available
                is_available = self._is_slot_available(
                    slot_start, slot_end,
                    existing_jobs, reserved_slots, time_offs
                )
                
                windows.append(TimeSlot(
                    start=slot_start,
                    end=slot_end,
                    available=is_available
                ))
                
                current_time += slot_duration
        
        return windows
    
    def _is_slot_available(
        self,
        slot_start: time,
        slot_end: time,
        existing_jobs: List[Job],
        reserved_slots: List[dict],
        time_offs: List[TimeOff],
    ) -> bool:
        """Check if a specific slot is available."""
        
        # Check against existing jobs
        for job in existing_jobs:
            if job.scheduled_time_start and job.scheduled_time_end:
                if self._times_overlap(
                    slot_start, slot_end,
                    job.scheduled_time_start, job.scheduled_time_end
                ):
                    return False
        
        # Check against reservations
        for reservation in reserved_slots:
            if self._times_overlap(
                slot_start, slot_end,
                reservation["start"], reservation["end"]
            ):
                return False
        
        # Check against time off
        for time_off in time_offs:
            if time_off.all_day:
                return False
            if time_off.start_time and time_off.end_time:
                if self._times_overlap(
                    slot_start, slot_end,
                    time_off.start_time, time_off.end_time
                ):
                    return False
        
        return True
    
    def _times_overlap(
        self,
        start1: time, end1: time,
        start2: time, end2: time
    ) -> bool:
        """Check if two time ranges overlap."""
        return start1 < end2 and end1 > start2
    
    async def _get_reserved_slots(self, check_date: date) -> List[dict]:
        """Get active slot reservations from Redis."""
        redis = await get_redis()
        pattern = f"slot_reservation:{self.business_id}:{check_date}:*"
        
        reserved = []
        async for key in redis.scan_iter(match=pattern):
            data = await redis.hgetall(key)
            if data:
                reserved.append({
                    "start": time.fromisoformat(data["start_time"]),
                    "end": time.fromisoformat(data["end_time"]),
                })
        
        return reserved
    
    async def reserve_slot(
        self,
        customer_id: UUID,
        slot_date: date,
        start_time: time,
        end_time: time,
    ) -> SlotReservation:
        """
        Create a temporary slot reservation.
        Stores in both Redis (for fast lookup) and DB (for persistence).
        """
        
        # Generate unique token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.SLOT_RESERVATION_MINUTES)
        
        # Store in Redis for fast checking
        redis = await get_redis()
        redis_key = f"slot_reservation:{self.business_id}:{slot_date}:{token}"
        await redis.hset(redis_key, mapping={
            "customer_id": str(customer_id),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        })
        await redis.expireat(redis_key, expires_at)
        
        # Store in DB
        reservation = SlotReservation(
            business_id=self.business_id,
            reservation_token=token,
            customer_id=customer_id,
            slot_date=slot_date,
            slot_start_time=start_time,
            slot_end_time=end_time,
            expires_at=expires_at,
        )
        self.db.add(reservation)
        await self.db.commit()
        await self.db.refresh(reservation)
        
        return reservation
    
    async def confirm_reservation(self, token: str, job_id: UUID) -> bool:
        """Mark a reservation as confirmed (converted to job)."""
        
        # Find reservation
        result = await self.db.execute(
            select(SlotReservation).where(
                SlotReservation.reservation_token == token,
                SlotReservation.business_id == self.business_id,
                SlotReservation.is_confirmed == False,
                SlotReservation.expires_at > datetime.utcnow()
            )
        )
        reservation = result.scalar_one_or_none()
        
        if not reservation:
            return False
        
        # Update reservation
        reservation.is_confirmed = True
        reservation.job_id = job_id
        reservation.confirmed_at = datetime.utcnow()
        
        # Remove from Redis
        redis = await get_redis()
        redis_key = f"slot_reservation:{self.business_id}:{reservation.slot_date}:{token}"
        await redis.delete(redis_key)
        
        await self.db.commit()
        return True
    
    async def validate_reservation(self, token: str) -> Optional[SlotReservation]:
        """Validate a reservation token is still valid."""
        result = await self.db.execute(
            select(SlotReservation).where(
                SlotReservation.reservation_token == token,
                SlotReservation.business_id == self.business_id,
                SlotReservation.is_confirmed == False,
                SlotReservation.expires_at > datetime.utcnow()
            )
        )
        return result.scalar_one_or_none()
    
    async def find_available_technician(
        self,
        service_type: str,
        location_lat: float,
        location_lng: float,
        urgency: str = "normal",
    ) -> Optional[dict]:
        """
        Find the best available technician for a job.
        For emergencies, prioritizes proximity.
        """
        
        # Get active technicians
        query = select(Technician).where(
            Technician.business_id == self.business_id,
            Technician.is_active == True
        )
        
        # For emergencies after hours, only get on-call techs
        # (This logic would be enhanced based on time of day)
        if urgency == "emergency":
            # Include all active techs for emergencies
            pass
        
        result = await self.db.execute(query)
        technicians = list(result.scalars())
        
        if not technicians:
            return None
        
        # For MVP, return first available tech
        # TODO: Implement distance calculation with Google Maps
        # TODO: Check current job assignments
        
        best_tech = technicians[0]
        
        return {
            "tech_id": best_tech.id,
            "tech_name": best_tech.name,
            "tech_phone": best_tech.phone,
            "eta_minutes": 30,  # Placeholder - would calculate actual ETA
            "distance_miles": 5.0,  # Placeholder
        }
