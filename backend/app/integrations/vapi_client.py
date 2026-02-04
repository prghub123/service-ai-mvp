"""Vapi.ai integration for voice AI."""

import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from app.config import get_settings

settings = get_settings()

VAPI_BASE_URL = "https://api.vapi.ai"


class VapiClient:
    """Client for Vapi.ai voice AI platform."""
    
    def __init__(self):
        self.api_key = settings.VAPI_API_KEY
        self.assistant_id = settings.VAPI_ASSISTANT_ID
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
    ) -> dict:
        """Make authenticated request to Vapi API."""
        if not self.api_key:
            return {"dev_mode": True}
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=f"{VAPI_BASE_URL}{endpoint}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=data,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
    
    async def list_calls(
        self,
        created_after: Optional[datetime] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        """
        List recent calls for reconciliation.
        Used to recover jobs if webhooks fail.
        """
        params = {"limit": limit}
        if created_after:
            params["createdAtGte"] = created_after.isoformat()
        if status:
            params["status"] = status
        
        # Vapi uses query params, convert to endpoint
        query = "&".join(f"{k}={v}" for k, v in params.items())
        result = await self._request("GET", f"/call?{query}")
        
        return result if isinstance(result, list) else result.get("calls", [])
    
    async def get_call(self, call_id: str) -> dict:
        """Get details of a specific call."""
        return await self._request("GET", f"/call/{call_id}")
    
    async def get_call_token(
        self,
        customer_context: dict,
        business_id: str,
    ) -> dict:
        """
        Get a token for in-app VoIP calling.
        This allows the customer app to initiate calls through Vapi.
        """
        if not self.api_key:
            return {
                "token": "dev_mode_token",
                "expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
            }
        
        # Create a temporary assistant override with customer context
        data = {
            "assistant_id": self.assistant_id,
            "assistant_overrides": {
                "metadata": {
                    "business_id": business_id,
                    "customer_id": customer_context.get("customer_id"),
                    "customer_name": customer_context.get("name"),
                    "customer_phone": customer_context.get("phone"),
                    "known_addresses": customer_context.get("addresses", []),
                },
                "first_message": f"Hi {customer_context.get('name', 'there')}! I see you're calling from the app. What can I help you with today?",
            },
        }
        
        result = await self._request("POST", "/call/web", data)
        return result
    
    async def create_outbound_call(
        self,
        phone_number: str,
        message: str,
        business_id: str,
    ) -> dict:
        """
        Initiate an outbound call (e.g., for callbacks).
        """
        data = {
            "assistant_id": self.assistant_id,
            "phone_number": phone_number,
            "assistant_overrides": {
                "metadata": {
                    "business_id": business_id,
                    "call_type": "outbound_callback",
                },
                "first_message": message,
            },
        }
        
        return await self._request("POST", "/call/phone", data)


class VapiWebhookPayload:
    """Helper class to parse Vapi webhook payloads."""
    
    def __init__(self, data: dict):
        self.data = data
        self.call_id = data.get("call", {}).get("id")
        self.type = data.get("type")  # 'call.started', 'call.ended', etc.
        self.transcript = data.get("transcript")
        self.summary = data.get("summary")
        self.metadata = data.get("call", {}).get("metadata", {})
    
    @property
    def business_id(self) -> Optional[str]:
        return self.metadata.get("business_id")
    
    @property
    def customer_id(self) -> Optional[str]:
        return self.metadata.get("customer_id")
    
    @property
    def phone_number(self) -> Optional[str]:
        return self.data.get("call", {}).get("customer", {}).get("number")
    
    @property
    def duration_seconds(self) -> Optional[int]:
        return self.data.get("call", {}).get("duration")
    
    @property
    def outcome(self) -> Optional[str]:
        """Extract outcome from call analysis or metadata."""
        analysis = self.data.get("analysis", {})
        return analysis.get("outcome") or self.metadata.get("outcome")
