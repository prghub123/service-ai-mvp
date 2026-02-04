"""API dependencies for dependency injection and authentication."""

from typing import Optional, Union
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.database import get_db
from app.config import get_settings
from app.models.customer import Customer
from app.models.technician import Technician
from app.models.business import Business
from app.models.user import User, UserRole

settings = get_settings()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =============================================================================
# Password Utilities
# =============================================================================

def hash_password(password: str) -> str:
    """Hash a password for storing."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a stored password against a provided password."""
    return pwd_context.verify(plain_password, hashed_password)


# =============================================================================
# JWT Token Utilities
# =============================================================================

def create_access_token(
    subject: str,
    token_type: str,  # "owner", "technician", "customer"
    business_id: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": subject,
        "type": token_type,
        "business_id": business_id,
        "exp": expire,
    }
    
    if extra_claims:
        to_encode.update(extra_claims)
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# =============================================================================
# Business Context
# =============================================================================

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


# =============================================================================
# Role-Based Authentication Dependencies
# =============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated owner/admin user from JWT token."""
    
    token = credentials.credentials
    payload = decode_token(token)
    
    user_id = payload.get("sub")
    token_type = payload.get("type")
    business_id = payload.get("business_id")
    
    if not user_id or token_type != "owner":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for this endpoint",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(
        select(User).where(
            User.id == UUID(user_id),
            User.business_id == UUID(business_id),
            User.is_active == True
        )
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_owner(
    user: User = Depends(get_current_user),
) -> User:
    """Require the current user to be an owner."""
    if user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required"
        )
    return user


async def get_current_technician(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Technician:
    """Get current authenticated technician from JWT token."""
    
    token = credentials.credentials
    payload = decode_token(token)
    
    tech_id = payload.get("sub")
    token_type = payload.get("type")
    business_id = payload.get("business_id")
    
    if not tech_id or token_type != "technician":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for this endpoint",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(
        select(Technician).where(
            Technician.id == UUID(tech_id),
            Technician.business_id == UUID(business_id),
            Technician.is_active == True
        )
    )
    technician = result.scalar_one_or_none()
    
    if technician is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Technician not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return technician


async def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Customer:
    """Get current authenticated customer from JWT token."""
    
    token = credentials.credentials
    payload = decode_token(token)
    
    customer_id = payload.get("sub")
    token_type = payload.get("type")
    business_id = payload.get("business_id")
    
    if not customer_id or token_type != "customer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for this endpoint",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(
        select(Customer).where(
            Customer.id == UUID(customer_id),
            Customer.business_id == UUID(business_id)
        )
    )
    customer = result.scalar_one_or_none()
    
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Customer not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return customer


# =============================================================================
# Utility Functions for Getting Business from Token
# =============================================================================

async def get_business_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Business:
    """Extract business from JWT token (any role)."""
    
    token = credentials.credentials
    payload = decode_token(token)
    business_id = payload.get("business_id")
    
    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token - no business context",
        )
    
    result = await db.execute(
        select(Business).where(
            Business.id == UUID(business_id),
            Business.is_active == True
        )
    )
    business = result.scalar_one_or_none()
    
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found or inactive"
        )
    
    return business


# =============================================================================
# Optional Auth Dependencies
# =============================================================================

async def get_optional_customer(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
) -> Optional[Customer]:
    """Get customer if authenticated, None otherwise."""
    if not credentials:
        return None
    
    try:
        return await get_current_customer(credentials, db)
    except HTTPException:
        return None
