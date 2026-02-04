"""Notification service - handles multi-channel notifications with tracking."""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import (
    Notification, 
    NotificationChannel, 
    NotificationStatus,
    NotificationRecipientType,
)
from app.models.job import Job
from app.models.customer import Customer
from app.models.technician import Technician
from app.models.business import Business
from app.integrations.twilio_client import TwilioClient
from app.config import get_settings

settings = get_settings()


class NotificationService:
    """Service for sending and tracking notifications."""
    
    def __init__(self, db: AsyncSession, business_id: UUID):
        self.db = db
        self.business_id = business_id
        self.twilio = TwilioClient()
    
    async def notify_customer(
        self,
        customer: Customer,
        message: str,
        job_id: Optional[UUID] = None,
        trigger_event: str = "general",
        channels: List[NotificationChannel] = None,
    ) -> List[Notification]:
        """
        Send notification to customer via multiple channels.
        Default: Push + SMS for reliability.
        """
        if channels is None:
            channels = [NotificationChannel.PUSH, NotificationChannel.SMS]
        
        notifications = []
        
        for channel in channels:
            notification = await self._send_notification(
                recipient_type=NotificationRecipientType.CUSTOMER,
                recipient_id=customer.id,
                recipient_contact=customer.phone if channel == NotificationChannel.SMS else customer.push_token,
                channel=channel,
                message=message,
                job_id=job_id,
                trigger_event=trigger_event,
            )
            notifications.append(notification)
        
        return notifications
    
    async def notify_technician(
        self,
        technician: Technician,
        message: str,
        job_id: Optional[UUID] = None,
        trigger_event: str = "general",
        channels: List[NotificationChannel] = None,
    ) -> List[Notification]:
        """Send notification to technician."""
        if channels is None:
            channels = [NotificationChannel.PUSH, NotificationChannel.SMS]
        
        notifications = []
        
        for channel in channels:
            contact = technician.phone if channel == NotificationChannel.SMS else technician.push_token
            if not contact:
                continue
                
            notification = await self._send_notification(
                recipient_type=NotificationRecipientType.TECHNICIAN,
                recipient_id=technician.id,
                recipient_contact=contact,
                channel=channel,
                message=message,
                job_id=job_id,
                trigger_event=trigger_event,
            )
            notifications.append(notification)
        
        return notifications
    
    async def notify_owner(
        self,
        message: str,
        job_id: Optional[UUID] = None,
        trigger_event: str = "general",
        channels: List[NotificationChannel] = None,
        urgent: bool = False,
    ) -> List[Notification]:
        """
        Send notification to business owner.
        For urgent notifications, includes voice call.
        """
        if channels is None:
            channels = [NotificationChannel.SMS]
            if urgent:
                channels.append(NotificationChannel.VOICE_CALL)
        
        # Get business owner info
        result = await self.db.execute(
            select(Business).where(Business.id == self.business_id)
        )
        business = result.scalar_one_or_none()
        if not business or not business.owner_phone:
            return []
        
        notifications = []
        
        for channel in channels:
            notification = await self._send_notification(
                recipient_type=NotificationRecipientType.OWNER,
                recipient_id=self.business_id,  # Use business ID for owner
                recipient_contact=business.owner_phone,
                channel=channel,
                message=message,
                job_id=job_id,
                trigger_event=trigger_event,
            )
            notifications.append(notification)
        
        # If urgent and primary fails, try backup contact
        if urgent and business.backup_contact_phone:
            backup_notification = await self._send_notification(
                recipient_type=NotificationRecipientType.OWNER,
                recipient_id=self.business_id,
                recipient_contact=business.backup_contact_phone,
                channel=NotificationChannel.SMS,
                message=f"[BACKUP] {message}",
                job_id=job_id,
                trigger_event=f"{trigger_event}_backup",
            )
            notifications.append(backup_notification)
        
        return notifications
    
    async def _send_notification(
        self,
        recipient_type: NotificationRecipientType,
        recipient_id: UUID,
        recipient_contact: Optional[str],
        channel: NotificationChannel,
        message: str,
        job_id: Optional[UUID] = None,
        trigger_event: str = "general",
    ) -> Notification:
        """Send a single notification and track it."""
        
        # Create notification record
        notification = Notification(
            business_id=self.business_id,
            job_id=job_id,
            trigger_event=trigger_event,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            recipient_contact=recipient_contact or "",
            channel=channel,
            status=NotificationStatus.PENDING,
            message=message,
        )
        self.db.add(notification)
        await self.db.flush()
        
        # Actually send the notification
        if not recipient_contact:
            notification.status = NotificationStatus.FAILED
            notification.error_message = "No contact information available"
            notification.failed_at = datetime.utcnow()
        else:
            try:
                if channel == NotificationChannel.SMS:
                    result = await self.twilio.send_sms(recipient_contact, message)
                    notification.external_id = result.get("sid")
                    notification.status = NotificationStatus.SENT
                    notification.sent_at = datetime.utcnow()
                    
                elif channel == NotificationChannel.VOICE_CALL:
                    result = await self.twilio.make_call(recipient_contact, message)
                    notification.external_id = result.get("sid")
                    notification.status = NotificationStatus.SENT
                    notification.sent_at = datetime.utcnow()
                    
                elif channel == NotificationChannel.PUSH:
                    # TODO: Implement push notification (FCM/APNs)
                    notification.status = NotificationStatus.SENT
                    notification.sent_at = datetime.utcnow()
                    
                elif channel == NotificationChannel.EMAIL:
                    # TODO: Implement email (SendGrid)
                    notification.status = NotificationStatus.SENT
                    notification.sent_at = datetime.utcnow()
                    
            except Exception as e:
                notification.status = NotificationStatus.FAILED
                notification.error_message = str(e)
                notification.failed_at = datetime.utcnow()
                notification.next_retry_at = datetime.utcnow() + timedelta(minutes=5)
        
        await self.db.commit()
        await self.db.refresh(notification)
        
        return notification
    
    async def get_failed_notifications_for_retry(self) -> List[Notification]:
        """Get failed notifications that need retry."""
        result = await self.db.execute(
            select(Notification).where(
                Notification.business_id == self.business_id,
                Notification.status.in_([
                    NotificationStatus.FAILED, 
                    NotificationStatus.RETRYING
                ]),
                Notification.retry_count < Notification.max_retries,
                Notification.next_retry_at <= datetime.utcnow()
            )
        )
        return list(result.scalars())
    
    async def retry_notification(self, notification_id: UUID) -> Optional[Notification]:
        """Retry a failed notification."""
        result = await self.db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.business_id == self.business_id
            )
        )
        notification = result.scalar_one_or_none()
        
        if not notification:
            return None
        
        notification.status = NotificationStatus.RETRYING
        notification.retry_count = str(int(notification.retry_count) + 1)
        
        # Attempt to resend
        try:
            if notification.channel == NotificationChannel.SMS:
                result = await self.twilio.send_sms(
                    notification.recipient_contact, 
                    notification.message
                )
                notification.external_id = result.get("sid")
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.utcnow()
        except Exception as e:
            notification.error_message = str(e)
            notification.status = NotificationStatus.FAILED
            notification.next_retry_at = datetime.utcnow() + timedelta(minutes=15)
        
        await self.db.commit()
        await self.db.refresh(notification)
        
        return notification
    
    # Pre-built notification templates
    
    async def notify_job_created(self, job: Job, customer: Customer) -> None:
        """Notify when a new job is created."""
        message = (
            f"Your service request has been received! "
            f"Confirmation: {job.confirmation_code}. "
            f"We'll confirm your appointment shortly."
        )
        await self.notify_customer(
            customer=customer,
            message=message,
            job_id=job.id,
            trigger_event="job_created",
        )
        
        # Also notify owner
        owner_msg = (
            f"New job request: {job.service_type} - {job.confirmation_code}. "
            f"Customer: {customer.name or customer.phone}"
        )
        await self.notify_owner(
            message=owner_msg,
            job_id=job.id,
            trigger_event="job_created",
        )
    
    async def notify_tech_assigned(
        self, 
        job: Job, 
        customer: Customer, 
        technician: Technician
    ) -> None:
        """Notify when a technician is assigned."""
        
        # Notify customer
        customer_msg = (
            f"Great news! {technician.name} has been assigned to your "
            f"{job.service_type} appointment on {job.scheduled_date} "
            f"between {job.scheduled_time_start}-{job.scheduled_time_end}."
        )
        await self.notify_customer(
            customer=customer,
            message=customer_msg,
            job_id=job.id,
            trigger_event="tech_assigned",
        )
        
        # Notify technician
        tech_msg = (
            f"New job assigned: {job.service_type} at "
            f"{job.address.full_address if job.address else 'TBD'}. "
            f"Scheduled: {job.scheduled_date} {job.scheduled_time_start}."
        )
        await self.notify_technician(
            technician=technician,
            message=tech_msg,
            job_id=job.id,
            trigger_event="tech_assigned",
        )
    
    async def notify_tech_en_route(
        self, 
        job: Job, 
        customer: Customer, 
        technician: Technician,
        eta_minutes: int
    ) -> None:
        """Notify customer that tech is on the way."""
        message = (
            f"{technician.name} is on the way! "
            f"ETA: {eta_minutes} minutes. "
            f"Track your technician in the app."
        )
        await self.notify_customer(
            customer=customer,
            message=message,
            job_id=job.id,
            trigger_event="tech_en_route",
        )
    
    async def notify_emergency_dispatch(
        self,
        job: Job,
        customer: Customer,
        technician: Technician,
        eta_minutes: int
    ) -> None:
        """Send emergency notifications to all parties."""
        
        # Customer
        customer_msg = (
            f"🚨 Emergency help is on the way! {technician.name} "
            f"will arrive in approximately {eta_minutes} minutes. "
            f"Confirmation: {job.confirmation_code}"
        )
        await self.notify_customer(
            customer=customer,
            message=customer_msg,
            job_id=job.id,
            trigger_event="emergency_dispatch",
        )
        
        # Technician (urgent)
        tech_msg = (
            f"🚨 EMERGENCY DISPATCH: {job.service_type} at "
            f"{job.address.full_address if job.address else 'See app'}. "
            f"Customer: {customer.phone}. RESPOND IMMEDIATELY."
        )
        await self.notify_technician(
            technician=technician,
            message=tech_msg,
            job_id=job.id,
            trigger_event="emergency_dispatch",
        )
        
        # Owner (for awareness)
        owner_msg = (
            f"🚨 Emergency dispatched: {technician.name} sent to "
            f"{customer.name or customer.phone} for {job.service_type}. "
            f"Job: {job.confirmation_code}"
        )
        await self.notify_owner(
            message=owner_msg,
            job_id=job.id,
            trigger_event="emergency_dispatch",
            urgent=False,  # Owner doesn't need call for dispatched emergencies
        )
