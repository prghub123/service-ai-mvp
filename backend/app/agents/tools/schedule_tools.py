"""Tools for scheduling operations."""

from typing import Optional
from uuid import UUID
from datetime import date, timedelta
from langchain.tools import tool


def create_schedule_tools(db_session, business_id: UUID):
    """Create schedule tools bound to a specific session and business."""
    
    @tool
    async def check_availability(
        date_from: str,
        date_to: str,
        service_type: Optional[str] = None,
    ) -> dict:
        """
        Check available time slots for a date range.
        Returns available windows for scheduling.
        """
        from app.services.schedule_service import ScheduleService
        
        service = ScheduleService(db_session, business_id)
        
        availability = await service.get_availability(
            date_from=date.fromisoformat(date_from),
            date_to=date.fromisoformat(date_to),
            service_type=service_type,
        )
        
        return {
            "slots": [
                {
                    "date": str(day.date),
                    "windows": [
                        {
                            "start": str(slot.start),
                            "end": str(slot.end),
                            "available": slot.available,
                        }
                        for slot in day.windows
                    ]
                }
                for day in availability
            ]
        }
    
    @tool
    async def find_next_available_slot(
        service_type: Optional[str] = None,
        days_to_search: int = 7,
    ) -> dict:
        """
        Find the next available time slot.
        Useful for quickly offering an appointment.
        """
        from app.services.schedule_service import ScheduleService
        
        service = ScheduleService(db_session, business_id)
        
        today = date.today()
        availability = await service.get_availability(
            date_from=today,
            date_to=today + timedelta(days=days_to_search),
            service_type=service_type,
        )
        
        # Find first available slot
        for day in availability:
            for slot in day.windows:
                if slot.available:
                    return {
                        "found": True,
                        "date": str(day.date),
                        "start": str(slot.start),
                        "end": str(slot.end),
                    }
        
        return {"found": False, "message": "No availability in the next {days_to_search} days"}
    
    @tool
    async def find_nearest_available_technician(
        service_type: str,
        latitude: float,
        longitude: float,
        urgency: str = "normal",
    ) -> dict:
        """
        Find the nearest available technician for a job.
        Used for emergency dispatch.
        """
        from app.services.schedule_service import ScheduleService
        
        service = ScheduleService(db_session, business_id)
        
        result = await service.find_available_technician(
            service_type=service_type,
            location_lat=latitude,
            location_lng=longitude,
            urgency=urgency,
        )
        
        if not result:
            return {
                "found": False,
                "message": "No technicians currently available",
            }
        
        return {
            "found": True,
            "technician_id": str(result["tech_id"]),
            "technician_name": result["tech_name"],
            "eta_minutes": result["eta_minutes"],
            "distance_miles": result["distance_miles"],
        }
    
    return [
        check_availability,
        find_next_available_slot,
        find_nearest_available_technician,
    ]
