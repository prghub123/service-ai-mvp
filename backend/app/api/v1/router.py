"""Main router for API v1."""

from fastapi import APIRouter

from app.api.v1 import auth, customers, jobs, availability, technicians, webhooks

api_router = APIRouter()

# Include all routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(availability.router, prefix="/availability", tags=["Availability"])
api_router.include_router(technicians.router, prefix="/technicians", tags=["Technicians"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
