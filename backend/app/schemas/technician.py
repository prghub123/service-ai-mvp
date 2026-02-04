"""Technician-related schemas."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class TechnicianSkillCreate(BaseModel):
    """Create a technician skill."""
    
    skill_type: str = Field(..., max_length=100)
    certification: Optional[str] = Field(None, max_length=255)
    certified_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None


class TechnicianSkillResponse(BaseModel):
    """Technician skill response."""
    
    id: UUID
    skill_type: str
    certification: Optional[str]
    certified_date: Optional[datetime]
    expiry_date: Optional[datetime]
    
    class Config:
        from_attributes = True


class TechnicianCreate(BaseModel):
    """Create a new technician."""
    
    name: str = Field(..., max_length=255)
    phone: str = Field(..., max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    is_on_call: bool = False
    skills: List[TechnicianSkillCreate] = []


class TechnicianUpdate(BaseModel):
    """Update technician profile."""
    
    name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    is_on_call: Optional[bool] = None
    push_token: Optional[str] = Field(None, max_length=500)
    app_platform: Optional[str] = Field(None, pattern="^(ios|android)$")


class TechnicianLocationUpdate(BaseModel):
    """Update technician's current location."""
    
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class TechnicianResponse(BaseModel):
    """Full technician response."""
    
    id: UUID
    name: str
    phone: str
    email: Optional[str]
    is_active: bool
    is_on_call: bool
    skills: List[TechnicianSkillResponse] = []
    current_latitude: Optional[float]
    current_longitude: Optional[float]
    location_updated_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class TechnicianBriefResponse(BaseModel):
    """Brief technician info for listings."""
    
    id: UUID
    name: str
    phone: str
    is_active: bool
    is_on_call: bool
    
    class Config:
        from_attributes = True
