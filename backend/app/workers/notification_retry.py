"""
Notification retry worker.
Retries failed notifications according to retry policy.
Runs every 5 minutes.
"""

import asyncio
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.business import Business
from app.services.notification_service import NotificationService


async def retry_failed_notifications():
    """
    Main notification retry job.
    Finds failed notifications and retries them.
    """
    async with AsyncSessionLocal() as db:
        # Get all active businesses
        result = await db.execute(
            select(Business).where(Business.is_active == True)
        )
        businesses = result.scalars().all()
        
        total_retries = 0
        total_successes = 0
        
        for business in businesses:
            notification_service = NotificationService(db, business.id)
            
            # Get failed notifications that need retry
            failed = await notification_service.get_failed_notifications_for_retry()
            
            for notification in failed:
                result = await notification_service.retry_notification(notification.id)
                total_retries += 1
                
                if result and result.status.value == "sent":
                    total_successes += 1
                    print(f"Retry successful: {notification.id}")
                else:
                    print(f"Retry failed: {notification.id}")
        
        return {
            "retries_attempted": total_retries,
            "successes": total_successes,
        }


# Entry point for running as standalone script
if __name__ == "__main__":
    result = asyncio.run(retry_failed_notifications())
    print(f"\nRetry results: {result}")
