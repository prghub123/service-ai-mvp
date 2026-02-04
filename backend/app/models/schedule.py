"""Schedule and availability models."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Time, Integer, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class ScheduleBlock(Base):
    """Recurring availability blocks for technicians."""
    
    __tablename__ = "schedule_blocks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    technician_id = Column(UUID(as_uuid=True), ForeignKey("technicians.id"))  # Null = business-wide
    
    # Schedule
    day_of_week = Column(Integer, nullable=False)  # 0=Sunday, 1=Monday, ..., 6=Saturday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    # Status
    is_available = Column(Boolean, default=True)  # False = blocked time
    
    # Optional label
    label = Column(String(100))  # "Regular Hours", "On Call", etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = relationship("Business", back_populates="schedule_blocks")
    technician = relationship("Technician", back_populates="schedule_blocks")
    
    def __repr__(self):
        return f"<ScheduleBlock day={self.day_of_week} {self.start_time}-{self.end_time}>"


class SlotReservation(Base):
    """
    Temporary slot reservations to prevent double-booking.
    These are short-lived (5 minutes) and stored in both DB and Redis.
    """
    
    __tablename__ = "slot_reservations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    
    # Reservation details
    reservation_token = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"))
    
    # Slot being reserved
    slot_date = Column(Date, nullable=False)
    slot_start_time = Column(Time, nullable=False)
    slot_end_time = Column(Time, nullable=False)
    
    # Status
    is_confirmed = Column(Boolean, default=False)  # True when converted to job
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"))  # Set when confirmed
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    confirmed_at = Column(DateTime)
    
    def __repr__(self):
        return f"<SlotReservation {self.slot_date} {self.slot_start_time}>"


class TimeOff(Base):
    """Time off / blocked dates for technicians."""
    
    __tablename__ = "time_off"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    technician_id = Column(UUID(as_uuid=True), ForeignKey("technicians.id"))  # Null = business closed
    
    # Date range
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    
    # All day or partial
    all_day = Column(Boolean, default=True)
    start_time = Column(Time)  # If not all day
    end_time = Column(Time)    # If not all day
    
    # Reason
    reason = Column(String(255))  # "Vacation", "Sick", "Holiday", etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<TimeOff {self.start_date} - {self.end_date}>"
