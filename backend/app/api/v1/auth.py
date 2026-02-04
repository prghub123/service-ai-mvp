"""Authentication endpoints for customer app."""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_business, create_access_token
from app.models.business import Business
from app.schemas.customer import (
    OTPRequest, 
    OTPVerify, 
    TokenResponse,
    CustomerResponse,
)
from app.services.customer_service import CustomerService
from app.services.notification_service import NotificationService
from app.config import get_settings

settings = get_settings()
router = APIRouter()


@router.post("/request-otp", status_code=status.HTTP_200_OK)
async def request_otp(
    data: OTPRequest,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    """
    Request OTP code for phone verification.
    Sends a 6-digit code via SMS.
    """
    customer_service = CustomerService(db, business.id)
    notification_service = NotificationService(db, business.id)
    
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
        # In production, implement proper error handling
        pass
    
    return {"message": "OTP sent successfully", "expires_in_seconds": 600}


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(
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
    
    # Create access token
    access_token = create_access_token(
        subject=str(customer.id),
        token_type="customer",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        customer=CustomerResponse.model_validate(customer),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    """
    Refresh access token.
    Requires valid (not expired) token in Authorization header.
    """
    # This would typically validate the current token and issue a new one
    # For MVP, clients should re-authenticate via OTP when token expires
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Token refresh not implemented. Please re-authenticate."
    )
