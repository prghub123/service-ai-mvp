"""Customer-related Pydantic schemas."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
import phonenumbers


class CustomerAddressCreate(BaseModel):
    """Schema for creating a customer address."""
    
    label: str = Field(default="Home", max_length=50)
    street: str = Field(..., max_length=255)
    unit: Optional[str] = Field(None, max_length=50)
    city: str = Field(..., max_length=100)
    state: str = Field(..., max_length=50)
    zip_code: str = Field(..., max_length=20)
    gate_code: Optional[str] = Field(None, max_length=50)
    access_notes: Optional[str] = None
    is_default: bool = False
    
    # Geocoded (optional, can be set by backend)
    latitude: Optional[str] = None
    longitude: Optional[str] = None


class CustomerAddressResponse(BaseModel):
    """Schema for address response."""
    
    id: UUID
    label: str
    street: str
    unit: Optional[str]
    city: str
    state: str
    zip_code: str
    gate_code: Optional[str]
    access_notes: Optional[str]
    latitude: Optional[str]
    longitude: Optional[str]
    is_default: bool
    full_address: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class CustomerCreate(BaseModel):
    """Schema for creating a customer (during registration)."""
    
    phone: str = Field(..., description="Phone number with country code")
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate and normalize phone number."""
        try:
            parsed = phonenumbers.parse(v, "US")
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError("Invalid phone number")
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
        except phonenumbers.NumberParseException as e:
            raise ValueError(f"Invalid phone number: {e}")


class CustomerUpdate(BaseModel):
    """Schema for updating customer profile."""
    
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    push_token: Optional[str] = Field(None, max_length=500)
    app_platform: Optional[str] = Field(None, pattern="^(ios|android)$")


class CustomerResponse(BaseModel):
    """Schema for customer response."""
    
    id: UUID
    phone: str
    phone_verified: bool
    name: Optional[str]
    email: Optional[str]
    addresses: List[CustomerAddressResponse] = []
    created_at: datetime
    
    class Config:
        from_attributes = True


# Auth schemas

class OTPRequest(BaseModel):
    """Request OTP for phone verification."""
    
    phone: str = Field(..., description="Phone number to send OTP to")
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            parsed = phonenumbers.parse(v, "US")
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError("Invalid phone number")
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
        except phonenumbers.NumberParseException as e:
            raise ValueError(f"Invalid phone number: {e}")


class OTPVerify(BaseModel):
    """Verify OTP code."""
    
    phone: str
    code: str = Field(..., min_length=6, max_length=6)


class TokenResponse(BaseModel):
    """JWT token response."""
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    customer: CustomerResponse
