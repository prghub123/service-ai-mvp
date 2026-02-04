"""Main router for API v1."""

from fastapi import APIRouter

from app.api.v1 import auth
from app.api.v1.owner.router import router as owner_router
from app.api.v1.tech.router import router as tech_router
from app.api.v1.customer.router import router as customer_router

# Legacy routes (can be deprecated later)
from app.api.v1 import jobs, availability, technicians, webhooks, customers

api_router = APIRouter()

# =============================================================================
# Authentication (shared)
# =============================================================================
api_router.include_router(
    auth.router, 
    prefix="/auth", 
    tags=["Authentication"]
)

# =============================================================================
# Role-Based Routes
# =============================================================================

# Owner/Admin Dashboard Routes
api_router.include_router(
    owner_router, 
    prefix="/owner", 
    tags=["Owner Dashboard"]
)

# Technician Mobile App Routes
api_router.include_router(
    tech_router, 
    prefix="/tech", 
    tags=["Technician App"]
)

# Customer Mobile App Routes
api_router.include_router(
    customer_router, 
    prefix="/customer", 
    tags=["Customer App"]
)

# =============================================================================
# Webhooks (for external services)
# =============================================================================
api_router.include_router(
    webhooks.router, 
    prefix="/webhooks", 
    tags=["Webhooks"]
)

# =============================================================================
# Legacy Routes (for backwards compatibility)
# These can be deprecated once frontends migrate to role-based routes
# =============================================================================
api_router.include_router(
    jobs.router, 
    prefix="/jobs", 
    tags=["Jobs (Legacy)"],
    deprecated=True
)
api_router.include_router(
    availability.router, 
    prefix="/availability", 
    tags=["Availability (Legacy)"],
    deprecated=True
)
api_router.include_router(
    technicians.router, 
    prefix="/technicians", 
    tags=["Technicians (Legacy)"],
    deprecated=True
)
api_router.include_router(
    customers.router, 
    prefix="/customers", 
    tags=["Customers (Legacy)"],
    deprecated=True
)
