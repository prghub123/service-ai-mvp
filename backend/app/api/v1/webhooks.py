"""Webhook endpoints for external services (Vapi, Twilio, etc.)."""

import hmac
import hashlib
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.notification import CallLog
from app.config import get_settings

settings = get_settings()
router = APIRouter()


class VapiCallEndPayload(BaseModel):
    """Payload from Vapi when a call ends."""
    call_id: str
    assistant_id: str
    phone_number: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    outcome: Optional[str] = None
    duration_seconds: Optional[int] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    # Custom data we pass to Vapi
    metadata: Optional[dict] = None


@router.post("/vapi/call-end")
async def vapi_call_end(
    payload: VapiCallEndPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_vapi_signature: Optional[str] = Header(None),
):
    """
    Webhook called by Vapi when a call ends.
    This is critical for creating jobs from phone conversations.
    """
    
    # Verify webhook signature (if configured)
    if settings.VAPI_WEBHOOK_SECRET and x_vapi_signature:
        body = await request.body()
        expected_sig = hmac.new(
            settings.VAPI_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_sig, x_vapi_signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
    
    # Extract business ID from metadata
    business_id = payload.metadata.get("business_id") if payload.metadata else None
    if not business_id:
        # Log error but don't fail - we'll reconcile later
        return {"status": "error", "message": "No business_id in metadata"}
    
    # Log the call for reconciliation purposes
    call_log = CallLog(
        business_id=business_id,
        external_call_id=payload.call_id,
        provider="vapi",
        caller_phone=payload.phone_number,
        call_direction="inbound",
        call_type="intake",
        transcript=payload.transcript,
        call_summary=payload.summary,
        call_outcome=payload.outcome,
        duration_seconds=str(payload.duration_seconds) if payload.duration_seconds else None,
        webhook_received=datetime.utcnow(),
    )
    
    if payload.started_at:
        try:
            call_log.started_at = datetime.fromisoformat(payload.started_at.replace("Z", "+00:00"))
        except:
            pass
    
    if payload.ended_at:
        try:
            call_log.ended_at = datetime.fromisoformat(payload.ended_at.replace("Z", "+00:00"))
        except:
            pass
    
    db.add(call_log)
    
    # Process the call based on outcome
    if payload.outcome == "booking_confirmed":
        # The agent should have already created the job during the call
        # via tool calls. This is just for tracking.
        call_log.webhook_processed = datetime.utcnow()
        
    elif payload.outcome == "emergency_dispatched":
        # Emergency jobs are created immediately during the call
        call_log.webhook_processed = datetime.utcnow()
        
    elif payload.outcome == "callback_requested":
        # Customer requested callback - notify owner
        from app.services.notification_service import NotificationService
        from uuid import UUID
        
        notification_service = NotificationService(db, UUID(business_id))
        await notification_service.notify_owner(
            message=f"Callback requested from {payload.phone_number}. Summary: {payload.summary}",
            trigger_event="callback_requested",
        )
        call_log.webhook_processed = datetime.utcnow()
    
    await db.commit()
    
    return {"status": "processed", "call_id": payload.call_id}


class TwilioStatusPayload(BaseModel):
    """Twilio message status webhook payload."""
    MessageSid: str
    MessageStatus: str
    To: Optional[str] = None
    ErrorCode: Optional[str] = None
    ErrorMessage: Optional[str] = None


@router.post("/twilio/status")
async def twilio_message_status(
    payload: TwilioStatusPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook for Twilio SMS delivery status updates.
    Updates our notification tracking.
    """
    from sqlalchemy import select, update
    from app.models.notification import Notification, NotificationStatus
    
    # Map Twilio status to our status
    status_map = {
        "queued": NotificationStatus.SENT,
        "sent": NotificationStatus.SENT,
        "delivered": NotificationStatus.DELIVERED,
        "failed": NotificationStatus.FAILED,
        "undelivered": NotificationStatus.FAILED,
    }
    
    new_status = status_map.get(payload.MessageStatus.lower())
    if not new_status:
        return {"status": "ignored"}
    
    # Update notification record
    stmt = (
        update(Notification)
        .where(Notification.external_id == payload.MessageSid)
        .values(
            status=new_status,
            external_status=payload.MessageStatus,
            error_message=payload.ErrorMessage if payload.ErrorCode else None,
            delivered_at=datetime.utcnow() if new_status == NotificationStatus.DELIVERED else None,
            failed_at=datetime.utcnow() if new_status == NotificationStatus.FAILED else None,
        )
    )
    
    await db.execute(stmt)
    await db.commit()
    
    return {"status": "updated"}
