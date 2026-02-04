"""Notification tracking models."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class NotificationChannel(str, PyEnum):
    """Notification delivery channels."""
    SMS = "sms"
    PUSH = "push"
    EMAIL = "email"
    VOICE_CALL = "voice_call"


class NotificationStatus(str, PyEnum):
    """Notification delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class NotificationRecipientType(str, PyEnum):
    """Who the notification is for."""
    CUSTOMER = "customer"
    TECHNICIAN = "technician"
    OWNER = "owner"


class Notification(Base):
    """
    Track all notifications sent for delivery confirmation and retry.
    This is critical for the hardened MVP to ensure messages are delivered.
    """
    
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    
    # What triggered this notification
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    trigger_event = Column(String(100))  # 'job_created', 'tech_assigned', 'tech_en_route', etc.
    
    # Recipient
    recipient_type = Column(Enum(NotificationRecipientType), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), nullable=False)
    recipient_contact = Column(String(255))  # Phone number or email
    
    # Delivery
    channel = Column(Enum(NotificationChannel), nullable=False)
    status = Column(Enum(NotificationStatus), default=NotificationStatus.PENDING)
    
    # Content
    message = Column(Text, nullable=False)
    
    # External tracking
    external_id = Column(String(100))  # Twilio SID, FCM message ID, etc.
    external_status = Column(String(50))  # Raw status from provider
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(String(10), default="0")
    max_retries = Column(String(10), default="3")
    next_retry_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    failed_at = Column(DateTime)
    
    def __repr__(self):
        return f"<Notification {self.channel} to {self.recipient_type}>"


class CallLog(Base):
    """
    Log of all voice calls for reconciliation.
    Used to recover jobs if webhooks fail.
    """
    
    __tablename__ = "call_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    
    # Vapi/Twilio identifiers
    external_call_id = Column(String(100), unique=True, nullable=False, index=True)
    provider = Column(String(50), default="vapi")  # 'vapi', 'twilio'
    
    # Call details
    caller_phone = Column(String(20))
    call_direction = Column(String(20))  # 'inbound', 'outbound'
    call_type = Column(String(50))  # 'intake', 'emergency', 'followup'
    
    # Transcript and outcome
    transcript = Column(Text)
    call_summary = Column(Text)  # AI-generated summary
    call_outcome = Column(String(50))  # 'booking_confirmed', 'inquiry', 'cancelled', etc.
    
    # Duration
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    duration_seconds = Column(String(10))
    
    # Linking
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"))  # If a job was created
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"))
    
    # Webhook processing
    webhook_received = Column(DateTime)
    webhook_processed = Column(DateTime)
    processing_error = Column(Text)
    
    # Reconciliation
    was_reconciled = Column(String(10), default="false")  # 'true' if recovered by reconciliation job
    reconciled_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<CallLog {self.external_call_id}>"
