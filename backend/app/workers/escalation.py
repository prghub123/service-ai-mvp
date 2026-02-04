"""
Job escalation worker.
Checks for pending jobs and escalates according to the escalation ladder.
Runs every 15 minutes.
"""

import asyncio
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.business import Business
from app.services.escalation_service import EscalationService


async def run_escalation_checks():
    """
    Main escalation job.
    Checks all pending jobs across all businesses and escalates as needed.
    """
    async with AsyncSessionLocal() as db:
        # Get all active businesses
        result = await db.execute(
            select(Business).where(Business.is_active == True)
        )
        businesses = result.scalars().all()
        
        total_actions = []
        
        for business in businesses:
            escalation_service = EscalationService(db, business.id)
            actions = await escalation_service.check_and_escalate_jobs()
            
            if actions:
                print(f"Business {business.name}: {len(actions)} escalations")
                for action in actions:
                    print(f"  - Job {action['confirmation_code']}: {action['action']}")
            
            total_actions.extend(actions)
        
        return total_actions


# Entry point for running as standalone script
if __name__ == "__main__":
    actions = asyncio.run(run_escalation_checks())
    print(f"\nTotal escalations: {len(actions)}")
