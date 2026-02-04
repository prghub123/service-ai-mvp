"""User model for business owners/admins."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, PyEnum):
    """User roles for access control."""
    OWNER = "owner"           # Business owner - full access
    ADMIN = "admin"           # Admin staff - most access
    DISPATCHER = "dispatcher" # Can manage jobs but not settings


class User(Base):
    """User entity - business owners and admin staff."""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    
    # Auth
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # Profile
    name = Column(String(255), nullable=False)
    phone = Column(String(20))
    
    # Role
    role = Column(Enum(UserRole), default=UserRole.ADMIN, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)
    
    # Relationships
    business = relationship("Business", back_populates="users")
    
    # Unique constraint: one email per business
    __table_args__ = (
        Index("ix_users_business_email", "business_id", "email", unique=True),
    )
    
    def __repr__(self):
        return f"<User {self.email} ({self.role.value})>"
