"""Customer service - handles customer-related business logic."""

import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import Customer, CustomerAddress, OTPCode
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerAddressCreate,
)
from app.config import get_settings

settings = get_settings()


class CustomerService:
    """Service for customer operations."""
    
    def __init__(self, db: AsyncSession, business_id: UUID):
        self.db = db
        self.business_id = business_id
    
    async def get_by_id(self, customer_id: UUID) -> Optional[Customer]:
        """Get customer by ID."""
        result = await self.db.execute(
            select(Customer)
            .options(selectinload(Customer.addresses))
            .where(
                Customer.id == customer_id,
                Customer.business_id == self.business_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_by_phone(self, phone: str) -> Optional[Customer]:
        """Get customer by phone number."""
        result = await self.db.execute(
            select(Customer)
            .options(selectinload(Customer.addresses))
            .where(
                Customer.phone == phone,
                Customer.business_id == self.business_id
            )
        )
        return result.scalar_one_or_none()
    
    async def create(self, data: CustomerCreate) -> Customer:
        """Create a new customer."""
        customer = Customer(
            business_id=self.business_id,
            phone=data.phone,
            name=data.name,
            email=data.email,
        )
        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer
    
    async def update(self, customer_id: UUID, data: CustomerUpdate) -> Optional[Customer]:
        """Update customer profile."""
        customer = await self.get_by_id(customer_id)
        if not customer:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(customer, field, value)
        
        customer.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(customer)
        return customer
    
    async def add_address(
        self, 
        customer_id: UUID, 
        data: CustomerAddressCreate
    ) -> Optional[CustomerAddress]:
        """Add an address to customer."""
        customer = await self.get_by_id(customer_id)
        if not customer:
            return None
        
        # If this is default, unset other defaults
        if data.is_default:
            for addr in customer.addresses:
                addr.is_default = False
        
        address = CustomerAddress(
            customer_id=customer_id,
            **data.model_dump()
        )
        self.db.add(address)
        await self.db.commit()
        await self.db.refresh(address)
        return address
    
    async def get_address(self, address_id: UUID, customer_id: UUID) -> Optional[CustomerAddress]:
        """Get a specific address."""
        result = await self.db.execute(
            select(CustomerAddress).where(
                CustomerAddress.id == address_id,
                CustomerAddress.customer_id == customer_id
            )
        )
        return result.scalar_one_or_none()
    
    async def delete_address(self, address_id: UUID, customer_id: UUID) -> bool:
        """Delete an address."""
        address = await self.get_address(address_id, customer_id)
        if not address:
            return False
        
        await self.db.delete(address)
        await self.db.commit()
        return True
    
    # OTP Methods
    
    async def create_otp(self, phone: str) -> str:
        """Generate and store OTP code."""
        # Generate 6-digit code
        code = "".join([str(secrets.randbelow(10)) for _ in range(6)])
        
        # Expire any existing OTPs for this phone
        existing = await self.db.execute(
            select(OTPCode).where(
                OTPCode.phone == phone,
                OTPCode.verified == False
            )
        )
        for otp in existing.scalars():
            await self.db.delete(otp)
        
        # Create new OTP
        otp = OTPCode(
            phone=phone,
            code=code,
            business_id=self.business_id,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        self.db.add(otp)
        await self.db.commit()
        
        return code
    
    async def verify_otp(self, phone: str, code: str) -> bool:
        """Verify OTP code."""
        result = await self.db.execute(
            select(OTPCode).where(
                OTPCode.phone == phone,
                OTPCode.code == code,
                OTPCode.verified == False,
                OTPCode.expires_at > datetime.utcnow()
            )
        )
        otp = result.scalar_one_or_none()
        
        if not otp:
            # Track failed attempt (optional: implement rate limiting)
            return False
        
        # Mark as verified
        otp.verified = True
        otp.verified_at = datetime.utcnow()
        
        # Mark customer phone as verified
        customer = await self.get_by_phone(phone)
        if customer:
            customer.phone_verified = True
        
        await self.db.commit()
        return True
    
    async def get_or_create_by_phone(self, phone: str, name: Optional[str] = None) -> Customer:
        """Get existing customer or create new one."""
        customer = await self.get_by_phone(phone)
        if customer:
            return customer
        
        return await self.create(CustomerCreate(phone=phone, name=name))
