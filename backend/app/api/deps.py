"""API dependencies for dependency injection."""

from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.database import get_db
from app.config import get_settings
from app.models.customer import Customer
from app.models.technician import Technician
from app.models.business import Business
from app.services.customer_service import CustomerService
from sqlalchemy import select

settings = get_settings()
security = HTTPBearer()


async def get_current_business(
    x_business_id: str = Header(..., alias="X-Business-ID"),
    db: AsyncSession = Depends(get_db),
) -> Business:
    """Get current business from header."""
    try:
        business_id = UUID(x_business_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid business ID format"
        )
    
    result = await db.execute(
        select(Business).where(Business.id == business_id, Business.is_active == True)
    )
    business = result.scalar_one_or_none()
    
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found"
        )
    
    return business


async def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
) -> Customer:
    """Get current authenticated customer from JWT token."""
    
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        customer_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if customer_id is None or token_type != "customer":
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    # Get customer
    result = await db.execute(
        select(Customer).where(
            Customer.id == UUID(customer_id),
            Customer.business_id == business.id
        )
    )
    customer = result.scalar_one_or_none()
    
    if customer is None:
        raise credentials_exception
    
    return customer


async def get_current_technician(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
) -> Technician:
    """Get current authenticated technician from JWT token."""
    
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        tech_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if tech_id is None or token_type != "technician":
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(
        select(Technician).where(
            Technician.id == UUID(tech_id),
            Technician.business_id == business.id,
            Technician.is_active == True
        )
    )
    technician = result.scalar_one_or_none()
    
    if technician is None:
        raise credentials_exception
    
    return technician


def create_access_token(
    subject: str,
    token_type: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": subject,
        "type": token_type,
        "exp": expire,
    }
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


# Optional dependencies for endpoints that can work with or without auth

async def get_optional_customer(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
) -> Optional[Customer]:
    """Get customer if authenticated, None otherwise."""
    if not credentials:
        return None
    
    try:
        return await get_current_customer(credentials, db, business)
    except HTTPException:
        return None
