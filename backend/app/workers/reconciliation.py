"""
Call reconciliation worker.
Recovers missed jobs from failed webhooks by checking Vapi call logs.
Runs every 5 minutes.
"""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.notification import CallLog
from app.models.business import Business
from app.integrations.vapi_client import VapiClient
from app.services.job_service import JobService


async def reconcile_calls():
    """
    Main reconciliation job.
    Fetches recent calls from Vapi and creates any missing jobs.
    """
    async with AsyncSessionLocal() as db:
        # Get all active businesses
        result = await db.execute(
            select(Business).where(Business.is_active == True)
        )
        businesses = result.scalars().all()
        
        vapi = VapiClient()
        
        for business in businesses:
            await _reconcile_business_calls(db, business, vapi)


async def _reconcile_business_calls(
    db: AsyncSession,
    business: Business,
    vapi: VapiClient,
):
    """Reconcile calls for a specific business."""
    
    # Get calls from last 30 minutes
    since = datetime.utcnow() - timedelta(minutes=30)
    
    try:
        calls = await vapi.list_calls(
            created_after=since,
            status="completed",
        )
    except Exception as e:
        print(f"Failed to fetch Vapi calls for {business.id}: {e}")
        return
    
    for call in calls:
        # Check if this call's business_id matches
        call_business_id = call.get("metadata", {}).get("business_id")
        if call_business_id != str(business.id):
            continue
        
        call_id = call.get("id")
        
        # Check if we already have a record
        existing = await db.execute(
            select(CallLog).where(CallLog.external_call_id == call_id)
        )
        call_log = existing.scalar_one_or_none()
        
        if call_log and call_log.webhook_processed:
            # Already processed
            continue
        
        # Check if outcome indicates a job should exist
        outcome = call.get("analysis", {}).get("outcome")
        
        if outcome in ["booking_confirmed", "emergency_dispatched"]:
            # Check if job exists
            job_service = JobService(db, business.id)
            existing_job = await job_service.get_jobs_by_call_id(call_id)
            
            if not existing_job:
                # MISSING JOB - attempt recovery
                await _recover_job_from_call(db, business, call)
                
                # Log the reconciliation
                if call_log:
                    call_log.was_reconciled = "true"
                    call_log.reconciled_at = datetime.utcnow()
                else:
                    call_log = CallLog(
                        business_id=business.id,
                        external_call_id=call_id,
                        provider="vapi",
                        call_outcome=outcome,
                        was_reconciled="true",
                        reconciled_at=datetime.utcnow(),
                    )
                    db.add(call_log)
                
                await db.commit()
                
                print(f"Reconciled missing job from call {call_id}")


async def _recover_job_from_call(
    db: AsyncSession,
    business: Business,
    call: dict,
):
    """
    Attempt to create a job from a call that didn't get processed.
    This is a best-effort recovery.
    """
    from app.services.customer_service import CustomerService
    from app.services.job_service import JobService
    from app.services.notification_service import NotificationService
    from app.schemas.job import JobCreate
    from app.models.job import JobSource, JobPriority
    from datetime import date, time
    
    metadata = call.get("metadata", {})
    transcript = call.get("transcript", "")
    summary = call.get("summary", "")
    
    # Get or create customer
    customer_phone = call.get("customer", {}).get("number")
    if not customer_phone:
        print(f"Cannot recover job - no phone number in call {call.get('id')}")
        return
    
    customer_service = CustomerService(db, business.id)
    customer = await customer_service.get_or_create_by_phone(customer_phone)
    
    # Try to extract details from summary/transcript
    # This is imperfect but better than losing the job
    job_service = JobService(db, business.id)
    
    # Create a basic job with what we know
    try:
        from app.schemas.job import JobAddressInline
        
        # Default to tomorrow 9-11am if we can't parse
        tomorrow = date.today() + timedelta(days=1)
        
        job = await job_service.create(
            customer_id=customer.id,
            data=JobCreate(
                service_type="general",  # Default
                description=f"[RECOVERED FROM CALL] {summary or 'See transcript'}",
                address_id=customer.addresses[0].id if customer.addresses else None,
                preferred_date=tomorrow,
                preferred_time_start=time(9, 0),
                preferred_time_end=time(11, 0),
            ),
            source=JobSource.PHONE_AGENT,
            source_call_id=call.get("id"),
        )
        
        # Notify owner about recovered job
        notification_service = NotificationService(db, business.id)
        await notification_service.notify_owner(
            message=f"⚠️ RECOVERED JOB: {job.confirmation_code} was created from a call that didn't process correctly. Please review and confirm details with customer.",
            job_id=job.id,
            trigger_event="job_recovered",
            urgent=True,
        )
        
        # Notify customer
        await notification_service.notify_customer(
            customer=customer,
            message=f"Your service request has been received. Confirmation: {job.confirmation_code}. We'll contact you shortly to confirm details.",
            job_id=job.id,
            trigger_event="job_recovered",
        )
        
    except Exception as e:
        print(f"Failed to recover job from call {call.get('id')}: {e}")


# Entry point for running as standalone script
if __name__ == "__main__":
    asyncio.run(reconcile_calls())
