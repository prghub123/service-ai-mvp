"""Tools for sending notifications."""

from typing import Optional
from uuid import UUID
from langchain.tools import tool


def create_notification_tools(db_session, business_id: UUID):
    """Create notification tools bound to a specific session and business."""
    
    @tool
    async def send_sms_to_customer(
        customer_id: str,
        message: str,
        job_id: Optional[str] = None,
    ) -> dict:
        """
        Send an SMS notification to a customer.
        Used for confirmations, updates, etc.
        """
        from app.services.notification_service import NotificationService
        from app.services.customer_service import CustomerService
        
        customer_service = CustomerService(db_session, business_id)
        notification_service = NotificationService(db_session, business_id)
        
        customer = await customer_service.get_by_id(UUID(customer_id))
        if not customer:
            return {"success": False, "error": "Customer not found"}
        
        notifications = await notification_service.notify_customer(
            customer=customer,
            message=message,
            job_id=UUID(job_id) if job_id else None,
            trigger_event="agent_message",
        )
        
        return {
            "success": True,
            "notifications_sent": len(notifications),
        }
    
    @tool
    async def alert_business_owner(
        message: str,
        job_id: Optional[str] = None,
        urgent: bool = False,
    ) -> dict:
        """
        Send an alert to the business owner.
        Set urgent=True for emergencies (will trigger phone call).
        """
        from app.services.notification_service import NotificationService
        
        notification_service = NotificationService(db_session, business_id)
        
        notifications = await notification_service.notify_owner(
            message=message,
            job_id=UUID(job_id) if job_id else None,
            trigger_event="agent_alert",
            urgent=urgent,
        )
        
        return {
            "success": True,
            "notifications_sent": len(notifications),
            "urgent": urgent,
        }
    
    @tool
    async def notify_technician(
        technician_id: str,
        message: str,
        job_id: Optional[str] = None,
    ) -> dict:
        """
        Send a notification to a specific technician.
        Used for job assignments and updates.
        """
        from app.services.notification_service import NotificationService
        from sqlalchemy import select
        from app.models.technician import Technician
        
        result = await db_session.execute(
            select(Technician).where(
                Technician.id == UUID(technician_id),
                Technician.business_id == business_id,
            )
        )
        technician = result.scalar_one_or_none()
        
        if not technician:
            return {"success": False, "error": "Technician not found"}
        
        notification_service = NotificationService(db_session, business_id)
        
        notifications = await notification_service.notify_technician(
            technician=technician,
            message=message,
            job_id=UUID(job_id) if job_id else None,
            trigger_event="agent_message",
        )
        
        return {
            "success": True,
            "notifications_sent": len(notifications),
        }
    
    return [
        send_sms_to_customer,
        alert_business_owner,
        notify_technician,
    ]
