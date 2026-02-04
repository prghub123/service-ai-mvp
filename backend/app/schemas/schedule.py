"""Schedule and availability schemas."""

from datetime import datetime, date, time
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class TimeSlot(BaseModel):
    """A single time slot."""
    
    start: time
    end: time
    available: bool


class DayAvailability(BaseModel):
    """Availability for a single day."""
    
    date: date
    windows: List[TimeSlot]


class AvailabilityRequest(BaseModel):
    """Request parameters for checking availability."""
    
    service_type: Optional[str] = None
    date_from: date
    date_to: date
    technician_id: Optional[UUID] = None


class AvailabilityResponse(BaseModel):
    """Available time slots response."""
    
    slots: List[DayAvailability]


class SlotReservationRequest(BaseModel):
    """Request to temporarily reserve a slot."""
    
    date: date
    start_time: time
    end_time: time


class SlotReservationResponse(BaseModel):
    """Slot reservation response."""
    
    reservation_token: str
    date: date
    start_time: time
    end_time: time
    expires_at: datetime
    expires_in_seconds: int


class ScheduleBlockCreate(BaseModel):
    """Create a recurring schedule block."""
    
    technician_id: Optional[UUID] = None  # Null = business-wide
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time
    is_available: bool = True
    label: Optional[str] = Field(None, max_length=100)


class ScheduleBlockResponse(BaseModel):
    """Schedule block response."""
    
    id: UUID
    technician_id: Optional[UUID]
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool
    label: Optional[str]
    
    class Config:
        from_attributes = True


class TimeOffCreate(BaseModel):
    """Create time off / blocked dates."""
    
    technician_id: Optional[UUID] = None
    start_date: date
    end_date: date
    all_day: bool = True
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    reason: Optional[str] = Field(None, max_length=255)


class TimeOffResponse(BaseModel):
    """Time off response."""
    
    id: UUID
    technician_id: Optional[UUID]
    start_date: date
    end_date: date
    all_day: bool
    start_time: Optional[time]
    end_time: Optional[time]
    reason: Optional[str]
    
    class Config:
        from_attributes = True
