"""Business (tenant) model."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Business(Base):
    """Business entity - represents a plumbing/HVAC company (tenant)."""
    
    __tablename__ = "businesses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic Info
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(255))
    
    # Address
    address_street = Column(String(255))
    address_city = Column(String(100))
    address_state = Column(String(50))
    address_zip = Column(String(20))
    
    # Configuration
    timezone = Column(String(50), default="America/New_York")
    is_active = Column(Boolean, default=True)
    
    # Service Area (GeoJSON polygon or list of zip codes)
    service_area = Column(JSON, default=list)
    
    # Owner contact for emergencies
    owner_name = Column(String(255))
    owner_phone = Column(String(20))
    owner_email = Column(String(255))
    backup_contact_phone = Column(String(20))  # Secondary emergency contact
    
    # Settings
    settings = Column(JSON, default=dict)
    # Example settings:
    # {
    #   "auto_assign_enabled": false,
    #   "emergency_auto_assign": true,
    #   "default_slot_duration_minutes": 120,
    #   "business_hours": {"mon": {"start": "08:00", "end": "17:00"}, ...},
    #   "emergency_keywords": ["flood", "burst", "gas leak"],
    # }
    
    # AI Configuration
    ai_config = Column(JSON, default=dict)
    # Example:
    # {
    #   "greeting": "Thanks for calling ABC Plumbing",
    #   "voice_id": "...",
    #   "personality": "friendly and professional",
    # }
    
    # Partner network for overflow
    partner_businesses = Column(JSON, default=list)  # List of partner business IDs
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customers = relationship("Customer", back_populates="business")
    technicians = relationship("Technician", back_populates="business")
    jobs = relationship("Job", back_populates="business")
    schedule_blocks = relationship("ScheduleBlock", back_populates="business")
    
    def __repr__(self):
        return f"<Business {self.name}>"
