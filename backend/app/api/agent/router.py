"""Agent API router for AI-powered endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from uuid import UUID

from app.database import get_db
from app.api.deps import get_current_business, get_current_customer
from app.models.business import Business
from app.models.customer import Customer
from app.agents.intake_agent import IntakeAgent
from app.agents.emergency_detector import EmergencyDetector
from app.integrations.vapi_client import VapiClient

router = APIRouter()


class IntakeRequest(BaseModel):
    """Request for intake agent."""
    message: str
    session_id: Optional[str] = None  # For continuing conversations
    context: Optional[dict] = None


class IntakeResponse(BaseModel):
    """Response from intake agent."""
    response: str
    session_id: str
    outcome: Optional[str] = None
    job_id: Optional[str] = None
    job_confirmation_code: Optional[str] = None
    urgency: Optional[str] = None


class EmergencyCheckRequest(BaseModel):
    """Request for emergency check."""
    text: str


class EmergencyCheckResponse(BaseModel):
    """Response from emergency check."""
    urgency: str
    confidence: float
    keywords_matched: list
    review_recommended: bool


class CallTokenResponse(BaseModel):
    """Response with Vapi call token."""
    token: str
    assistant_id: str
    expires_at: str


@router.post("/intake", response_model=IntakeResponse)
async def process_intake(
    request: IntakeRequest,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_current_customer),
):
    """
    Process an intake message through the AI agent.
    Used for chat-based booking in the customer app.
    """
    
    # Create agent instance
    agent = IntakeAgent(
        business_id=str(business.id),
        business_name=business.name,
        db_session=db,
    )
    
    # Initialize state with customer context
    initial_state = None
    if request.context:
        # Pre-fill with customer info
        pass
    
    # Process the message
    result = await agent.process_message(
        message=request.message,
        state=initial_state,
    )
    
    return IntakeResponse(
        response=agent.get_last_response(result),
        session_id=request.session_id or "new_session",
        outcome=result.get("outcome"),
        job_id=result.get("job_id"),
        job_confirmation_code=result.get("job_confirmation_code"),
        urgency=result.get("urgency"),
    )


@router.post("/emergency-check", response_model=EmergencyCheckResponse)
async def check_emergency(
    request: EmergencyCheckRequest,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
):
    """
    Check if a message indicates an emergency.
    Can be used by the app to decide UI treatment.
    """
    
    detector = EmergencyDetector()
    result = await detector.detect(request.text)
    
    return EmergencyCheckResponse(
        urgency=result.urgency.value,
        confidence=result.confidence,
        keywords_matched=result.keywords_matched,
        review_recommended=result.review_recommended,
    )


@router.get("/call-token", response_model=CallTokenResponse)
async def get_call_token(
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_current_business),
    customer: Customer = Depends(get_current_customer),
):
    """
    Get a token for initiating a VoIP call through the app.
    The token includes customer context so the AI knows who's calling.
    """
    
    vapi = VapiClient()
    
    # Build customer context
    customer_context = {
        "customer_id": str(customer.id),
        "name": customer.name,
        "phone": customer.phone,
        "addresses": [
            {
                "id": str(addr.id),
                "label": addr.label,
                "full_address": addr.full_address,
            }
            for addr in customer.addresses
        ],
    }
    
    # Get token from Vapi
    result = await vapi.get_call_token(
        customer_context=customer_context,
        business_id=str(business.id),
    )
    
    return CallTokenResponse(
        token=result.get("token", ""),
        assistant_id=result.get("assistant_id", ""),
        expires_at=result.get("expires_at", ""),
    )
