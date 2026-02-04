"""Pydantic schemas for API request/response validation."""

from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerAddressCreate,
    CustomerAddressResponse,
    OTPRequest,
    OTPVerify,
    TokenResponse,
)
from app.schemas.job import (
    JobCreate,
    JobUpdate,
    JobResponse,
    JobListResponse,
    JobNoteCreate,
    JobNoteResponse,
    JobStatusUpdate,
)
from app.schemas.schedule import (
    AvailabilityRequest,
    AvailabilityResponse,
    SlotReservationRequest,
    SlotReservationResponse,
    TimeSlot,
)
from app.schemas.technician import (
    TechnicianCreate,
    TechnicianUpdate,
    TechnicianResponse,
    TechnicianLocationUpdate,
)

__all__ = [
    # Customer
    "CustomerCreate",
    "CustomerUpdate", 
    "CustomerResponse",
    "CustomerAddressCreate",
    "CustomerAddressResponse",
    "OTPRequest",
    "OTPVerify",
    "TokenResponse",
    # Job
    "JobCreate",
    "JobUpdate",
    "JobResponse",
    "JobListResponse",
    "JobNoteCreate",
    "JobNoteResponse",
    "JobStatusUpdate",
    # Schedule
    "AvailabilityRequest",
    "AvailabilityResponse",
    "SlotReservationRequest",
    "SlotReservationResponse",
    "TimeSlot",
    # Technician
    "TechnicianCreate",
    "TechnicianUpdate",
    "TechnicianResponse",
    "TechnicianLocationUpdate",
]
