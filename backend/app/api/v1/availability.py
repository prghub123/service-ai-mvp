"""Availability and slot reservation endpoints."""

from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_customer, get_current_business, get_optional_customer
from app.models.customer import Customer
from app.models.business import Business
from app.schemas.schedule import (
    AvailabilityResponse,
    SlotReservationRequest,
    SlotReservationResponse,
)
from app.services.schedule_service import ScheduleService
from app.config import get_settings

settings = get_settings()
router = APIRouter()


@router.get("", response_model=AvailabilityResponse)
async def get_availability(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    service_type: str = Query(None, description="Filter by service type"),
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_optional_customer),
):
    """
    Get available time slots for booking.
    Does not require authentication - can be used by unauthenticated users.
    """
    # Validate date range
    if date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from must be before date_to"
        )
    
    # Limit range to 14 days
    max_range = timedelta(days=14)
    if date_to - date_from > max_range:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 14 days"
        )
    
    # Don't allow past dates
    today = date.today()
    if date_from < today:
        date_from = today
    
    schedule_service = ScheduleService(db, business.id)
    
    availability = await schedule_service.get_availability(
        date_from=date_from,
        date_to=date_to,
        service_type=service_type,
    )
    
    return AvailabilityResponse(slots=availability)


@router.post("/reserve", response_model=SlotReservationResponse)
async def reserve_slot(
    data: SlotReservationRequest,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_current_customer),
):
    """
    Temporarily reserve a time slot (5 minute hold).
    Returns a reservation token to use when creating the job.
    This prevents double-booking during the booking flow.
    """
    schedule_service = ScheduleService(db, business.id)
    
    # Validate the slot is in the future
    today = date.today()
    if data.date < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reserve slots in the past"
        )
    
    # Check if slot is available
    availability = await schedule_service.get_availability(
        date_from=data.date,
        date_to=data.date,
    )
    
    if not availability:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No availability for selected date"
        )
    
    # Find the requested slot
    day_slots = availability[0]
    slot_available = False
    for slot in day_slots.windows:
        if slot.start == data.start_time and slot.end == data.end_time:
            slot_available = slot.available
            break
    
    if not slot_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected time slot is not available"
        )
    
    # Create reservation
    reservation = await schedule_service.reserve_slot(
        customer_id=customer.id,
        slot_date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
    )
    
    return SlotReservationResponse(
        reservation_token=reservation.reservation_token,
        date=reservation.slot_date,
        start_time=reservation.slot_start_time,
        end_time=reservation.slot_end_time,
        expires_at=reservation.expires_at,
        expires_in_seconds=settings.SLOT_RESERVATION_MINUTES * 60,
    )
