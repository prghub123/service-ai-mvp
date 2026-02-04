"""Tools for customer-related operations."""

from typing import Optional
from uuid import UUID
from langchain.tools import tool


def create_customer_tools(db_session, business_id: UUID):
    """Create customer tools bound to a specific session and business."""
    
    @tool
    async def lookup_customer_by_phone(phone: str) -> dict:
        """
        Look up a customer by their phone number.
        Returns customer profile including name, addresses, and service history.
        """
        from app.services.customer_service import CustomerService
        
        service = CustomerService(db_session, business_id)
        customer = await service.get_by_phone(phone)
        
        if not customer:
            return {"found": False}
        
        return {
            "found": True,
            "customer_id": str(customer.id),
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "addresses": [
                {
                    "id": str(addr.id),
                    "label": addr.label,
                    "full_address": addr.full_address,
                    "is_default": addr.is_default,
                }
                for addr in customer.addresses
            ],
        }
    
    @tool
    async def create_customer(
        phone: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> dict:
        """
        Create a new customer record.
        Used when a new caller is not found in the system.
        """
        from app.services.customer_service import CustomerService
        from app.schemas.customer import CustomerCreate
        
        service = CustomerService(db_session, business_id)
        customer = await service.create(CustomerCreate(
            phone=phone,
            name=name,
            email=email,
        ))
        
        return {
            "customer_id": str(customer.id),
            "name": customer.name,
            "phone": customer.phone,
        }
    
    @tool
    async def get_customer_service_history(customer_id: str, limit: int = 5) -> dict:
        """
        Get a customer's recent service history.
        Useful for context when handling their call.
        """
        from app.services.job_service import JobService
        
        service = JobService(db_session, business_id)
        jobs, _ = await service.list_jobs(
            customer_id=UUID(customer_id),
            page=1,
            page_size=limit,
        )
        
        return {
            "jobs": [
                {
                    "id": str(job.id),
                    "service_type": job.service_type,
                    "status": job.status.value,
                    "scheduled_date": str(job.scheduled_date) if job.scheduled_date else None,
                    "description": job.description,
                }
                for job in jobs
            ]
        }
    
    return [
        lookup_customer_by_phone,
        create_customer,
        get_customer_service_history,
    ]
