"""Customer models including addresses and OTP verification."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Customer(Base):
    """Customer entity - end users who book services."""
    
    __tablename__ = "customers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    
    # Contact Info
    phone = Column(String(20), nullable=False)
    phone_verified = Column(Boolean, default=False)
    email = Column(String(255))
    
    # Profile
    name = Column(String(255))
    
    # App-specific
    push_token = Column(String(500))  # FCM/APNs token
    app_platform = Column(String(20))  # 'ios' or 'android'
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active_at = Column(DateTime)
    
    # Relationships
    business = relationship("Business", back_populates="customers")
    addresses = relationship("CustomerAddress", back_populates="customer", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="customer")
    
    # Unique constraint: one phone per business
    __table_args__ = (
        Index("ix_customers_business_phone", "business_id", "phone", unique=True),
    )
    
    def __repr__(self):
        return f"<Customer {self.name or self.phone}>"


class CustomerAddress(Base):
    """Customer service addresses - customers can have multiple."""
    
    __tablename__ = "customer_addresses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    
    # Address Label
    label = Column(String(50), default="Home")  # Home, Office, Rental, etc.
    
    # Address Components
    street = Column(String(255), nullable=False)
    unit = Column(String(50))
    city = Column(String(100), nullable=False)
    state = Column(String(50), nullable=False)
    zip_code = Column(String(20), nullable=False)
    
    # Geocoded coordinates
    latitude = Column(String(20))
    longitude = Column(String(20))
    
    # Access Info (helpful for technicians)
    gate_code = Column(String(50))
    access_notes = Column(Text)
    
    # Default flag
    is_default = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="addresses")
    jobs = relationship("Job", back_populates="address")
    
    @property
    def full_address(self) -> str:
        """Return formatted full address."""
        parts = [self.street]
        if self.unit:
            parts.append(f"Unit {self.unit}")
        parts.append(f"{self.city}, {self.state} {self.zip_code}")
        return ", ".join(parts)
    
    def __repr__(self):
        return f"<CustomerAddress {self.street}, {self.city}>"


class OTPCode(Base):
    """OTP codes for phone verification."""
    
    __tablename__ = "otp_codes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    phone = Column(String(20), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    
    # For multi-tenant, track which business context
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"))
    
    # State
    verified = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)  # Track failed attempts
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    verified_at = Column(DateTime)
    
    def __repr__(self):
        return f"<OTPCode {self.phone}>"


# Need to import Integer for OTPCode
from sqlalchemy import Integer
