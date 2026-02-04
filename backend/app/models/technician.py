"""Technician models."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Technician(Base):
    """Technician entity - field service workers."""
    
    __tablename__ = "technicians"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    
    # Basic Info
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(255))
    
    # Status
    is_active = Column(Boolean, default=True)
    is_on_call = Column(Boolean, default=False)  # Available for emergencies after hours
    
    # App-specific
    push_token = Column(String(500))
    app_platform = Column(String(20))
    
    # Current location (updated by mobile app)
    current_latitude = Column(Float)
    current_longitude = Column(Float)
    location_updated_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = relationship("Business", back_populates="technicians")
    skills = relationship("TechnicianSkill", back_populates="technician", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="technician")
    schedule_blocks = relationship("ScheduleBlock", back_populates="technician")
    
    def __repr__(self):
        return f"<Technician {self.name}>"


class TechnicianSkill(Base):
    """Skills/certifications for technicians."""
    
    __tablename__ = "technician_skills"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    technician_id = Column(UUID(as_uuid=True), ForeignKey("technicians.id"), nullable=False)
    
    # Skill info
    skill_type = Column(String(100), nullable=False)  # 'plumbing', 'hvac', 'water_heater', etc.
    certification = Column(String(255))  # Optional certification name
    certified_date = Column(DateTime)
    expiry_date = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    technician = relationship("Technician", back_populates="skills")
    
    def __repr__(self):
        return f"<TechnicianSkill {self.skill_type}>"
