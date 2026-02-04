"""Authentication endpoints for all user types."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.api.deps import (
    get_current_business,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.business import Business
from app.models.user import User, UserRole
from app.models.technician import Technician
from app.models.customer import Customer
from app.services.customer_service import CustomerService
from app.config import get_settings

settings = get_settings()
router = APIRouter()


# =============================================================================
# Pydantic Schemas for Auth
# =============================================================================

class LoginRequest(BaseModel):
    """Email/password login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response for all login types."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_type: str  # "owner", "technician", "customer"
    user_id: str
    user_name: str
    business_id: str
    business_name: str
    role: Optional[str] = None  # For owners: "owner", "admin", "dispatcher"


class OTPRequest(BaseModel):
    """OTP request for customer login."""
    phone: str


class OTPVerify(BaseModel):
    """OTP verification for customer login."""
    phone: str
    code: str


class RegisterOwnerRequest(BaseModel):
    """Register a new business owner."""
    business_name: str
    owner_name: str
    email: EmailStr
    password: str
    phone: str


class RegisterTechnicianRequest(BaseModel):
    """Register a new technician (by owner)."""
    name: str
    email: EmailStr
    password: str
    phone: str


# =============================================================================
# Owner Authentication
# =============================================================================

@router.post("/owner/login", response_model=TokenResponse)
async def owner_login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
    x_business_id: str = Header(..., alias="X-Business-ID"),
):
    """
    Login for business owners/admins.
    Requires email and password.
    """
    try:
        business_id = UUID(x_business_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid business ID format"
        )
    
    # Get business
    result = await db.execute(
        select(Business).where(Business.id == business_id, Business.is_active == True)
    )
    business = result.scalar_one_or_none()
    
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found"
        )
    
    # Find user by email
    result = await db.execute(
        select(User).where(
            User.email == data.email.lower(),
            User.business_id == business_id,
            User.is_active == True
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()
    
    # Create token
    access_token = create_access_token(
        subject=str(user.id),
        token_type="owner",
        business_id=str(business.id),
        extra_claims={"role": user.role.value}
    )
    
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_type="owner",
        user_id=str(user.id),
        user_name=user.name,
        business_id=str(business.id),
        business_name=business.name,
        role=user.role.value,
    )


@router.post("/owner/register", response_model=TokenResponse)
async def register_owner(
    data: RegisterOwnerRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new business and owner account.
    This is the entry point for new businesses.
    """
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == data.email.lower())
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create business
    business = Business(
        name=data.business_name,
        phone=data.phone,
        email=data.email,
        owner_name=data.owner_name,
        owner_phone=data.phone,
        owner_email=data.email,
    )
    db.add(business)
    await db.flush()
    
    # Create owner user
    user = User(
        business_id=business.id,
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        name=data.owner_name,
        phone=data.phone,
        role=UserRole.OWNER,
        email_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await db.refresh(business)
    
    # Create token
    access_token = create_access_token(
        subject=str(user.id),
        token_type="owner",
        business_id=str(business.id),
        extra_claims={"role": user.role.value}
    )
    
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_type="owner",
        user_id=str(user.id),
        user_name=user.name,
        business_id=str(business.id),
        business_name=business.name,
        role=user.role.value,
    )


# =============================================================================
# Technician Authentication
# =============================================================================

@router.post("/tech/login", response_model=TokenResponse)
async def technician_login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
    x_business_id: str = Header(..., alias="X-Business-ID"),
):
    """
    Login for technicians (mobile app).
    Requires email and password.
    """
    try:
        business_id = UUID(x_business_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid business ID format"
        )
    
    # Get business
    result = await db.execute(
        select(Business).where(Business.id == business_id, Business.is_active == True)
    )
    business = result.scalar_one_or_none()
    
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found"
        )
    
    # Find technician by email
    result = await db.execute(
        select(Technician).where(
            Technician.email == data.email.lower(),
            Technician.business_id == business_id,
            Technician.is_active == True
        )
    )
    technician = result.scalar_one_or_none()
    
    if not technician or not technician.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not verify_password(data.password, technician.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create token
    access_token = create_access_token(
        subject=str(technician.id),
        token_type="technician",
        business_id=str(business.id),
    )
    
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_type="technician",
        user_id=str(technician.id),
        user_name=technician.name,
        business_id=str(business.id),
        business_name=business.name,
    )


# =============================================================================
# Customer Authentication (OTP-based)
# =============================================================================

@router.post("/customer/request-otp", status_code=status.HTTP_200_OK)
async def customer_request_otp(
    data: OTPRequest,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    """
    Request OTP code for customer phone verification.
    Sends a 6-digit code via SMS.
    """
    customer_service = CustomerService(db, business.id)
    
    # Generate OTP
    code = await customer_service.create_otp(data.phone)
    
    # Send OTP via SMS
    message = f"Your {business.name} verification code is: {code}. Expires in 10 minutes."
    
    try:
        from app.integrations.twilio_client import TwilioClient
        twilio = TwilioClient()
        await twilio.send_sms(data.phone, message)
    except Exception as e:
        # Log error but don't expose to user
        # In dev mode, we can return the code for testing
        if settings.DEBUG:
            return {"message": "OTP sent successfully", "expires_in_seconds": 600, "debug_code": code}
    
    return {"message": "OTP sent successfully", "expires_in_seconds": 600}


@router.post("/customer/verify-otp", response_model=TokenResponse)
async def customer_verify_otp(
    data: OTPVerify,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    """
    Verify OTP and return access token.
    Creates customer account if doesn't exist.
    """
    customer_service = CustomerService(db, business.id)
    
    # Verify OTP
    is_valid = await customer_service.verify_otp(data.phone, data.code)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code"
        )
    
    # Get or create customer
    customer = await customer_service.get_or_create_by_phone(data.phone)
    
    # Create token
    access_token = create_access_token(
        subject=str(customer.id),
        token_type="customer",
        business_id=str(business.id),
    )
    
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_type="customer",
        user_id=str(customer.id),
        user_name=customer.name or "Customer",
        business_id=str(business.id),
        business_name=business.name,
    )


# =============================================================================
# Token Validation
# =============================================================================

@router.get("/me")
async def get_current_user_info(
    db: AsyncSession = Depends(get_db),
    credentials = Depends(HTTPBearer()),
):
    """
    Get current user info from token.
    Works for any user type (owner, technician, customer).
    """
    from app.api.deps import decode_token
    
    token = credentials.credentials
    payload = decode_token(token)
    
    user_id = payload.get("sub")
    token_type = payload.get("type")
    business_id = payload.get("business_id")
    
    # Get business
    result = await db.execute(
        select(Business).where(Business.id == UUID(business_id))
    )
    business = result.scalar_one_or_none()
    
    if token_type == "owner":
        result = await db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        user = result.scalar_one_or_none()
        return {
            "user_type": "owner",
            "user_id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "business_id": str(business.id),
            "business_name": business.name,
        }
    
    elif token_type == "technician":
        result = await db.execute(
            select(Technician).where(Technician.id == UUID(user_id))
        )
        tech = result.scalar_one_or_none()
        return {
            "user_type": "technician",
            "user_id": str(tech.id),
            "name": tech.name,
            "email": tech.email,
            "phone": tech.phone,
            "business_id": str(business.id),
            "business_name": business.name,
        }
    
    elif token_type == "customer":
        result = await db.execute(
            select(Customer).where(Customer.id == UUID(user_id))
        )
        customer = result.scalar_one_or_none()
        return {
            "user_type": "customer",
            "user_id": str(customer.id),
            "name": customer.name,
            "phone": customer.phone,
            "business_id": str(business.id),
            "business_name": business.name,
        }
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token type"
    )


# Import HTTPBearer for /me endpoint
from fastapi.security import HTTPBearer
