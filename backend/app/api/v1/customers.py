"""Customer profile endpoints."""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_customer, get_current_business
from app.models.customer import Customer
from app.models.business import Business
from app.schemas.customer import (
    CustomerResponse,
    CustomerUpdate,
    CustomerAddressCreate,
    CustomerAddressResponse,
)
from app.services.customer_service import CustomerService

router = APIRouter()


@router.get("/me", response_model=CustomerResponse)
async def get_profile(
    customer: Customer = Depends(get_current_customer),
):
    """Get current customer's profile."""
    return customer


@router.patch("/me", response_model=CustomerResponse)
async def update_profile(
    data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_current_customer),
):
    """Update current customer's profile."""
    customer_service = CustomerService(db, business.id)
    
    updated = await customer_service.update(customer.id, data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    return updated


# Address endpoints

@router.get("/me/addresses", response_model=List[CustomerAddressResponse])
async def list_addresses(
    customer: Customer = Depends(get_current_customer),
):
    """List customer's saved addresses."""
    return customer.addresses


@router.post("/me/addresses", response_model=CustomerAddressResponse, status_code=status.HTTP_201_CREATED)
async def add_address(
    data: CustomerAddressCreate,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_current_customer),
):
    """Add a new address to customer's profile."""
    customer_service = CustomerService(db, business.id)
    
    address = await customer_service.add_address(customer.id, data)
    if not address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add address"
        )
    
    return address


@router.get("/me/addresses/{address_id}", response_model=CustomerAddressResponse)
async def get_address(
    address_id: UUID,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_current_customer),
):
    """Get a specific address."""
    customer_service = CustomerService(db, business.id)
    
    address = await customer_service.get_address(address_id, customer.id)
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    return address


@router.delete("/me/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: UUID,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_current_customer),
):
    """Delete an address."""
    customer_service = CustomerService(db, business.id)
    
    success = await customer_service.delete_address(address_id, customer.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
