"""Twilio integration for SMS and voice calls."""

import asyncio
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

settings = get_settings()


class TwilioClient:
    """Client for Twilio SMS and voice services."""
    
    def __init__(self):
        self.client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        ) if settings.TWILIO_ACCOUNT_SID else None
        self.from_number = settings.TWILIO_PHONE_NUMBER
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def send_sms(self, to: str, message: str) -> dict:
        """
        Send an SMS message.
        Returns dict with 'sid' and 'status'.
        """
        if not self.client:
            # Dev mode - just log
            print(f"[DEV] SMS to {to}: {message}")
            return {"sid": "dev_mode", "status": "sent"}
        
        try:
            # Twilio SDK is synchronous, run in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    body=message,
                    from_=self.from_number,
                    to=to,
                    status_callback=f"{settings.API_V1_PREFIX}/webhooks/twilio/status"
                )
            )
            
            return {
                "sid": result.sid,
                "status": result.status,
            }
            
        except TwilioRestException as e:
            raise Exception(f"Twilio SMS error: {e.msg}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def make_call(
        self, 
        to: str, 
        message: str,
        voice: str = "alice"
    ) -> dict:
        """
        Make a voice call with TTS message.
        Used for urgent owner notifications.
        """
        if not self.client:
            print(f"[DEV] Voice call to {to}: {message}")
            return {"sid": "dev_mode", "status": "initiated"}
        
        # Create TwiML for the call
        twiml = f"""
        <Response>
            <Say voice="{voice}">{message}</Say>
            <Pause length="1"/>
            <Say voice="{voice}">Press 1 to acknowledge this message.</Say>
            <Gather numDigits="1" timeout="10">
            </Gather>
            <Say voice="{voice}">No response received. Goodbye.</Say>
        </Response>
        """
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.client.calls.create(
                    twiml=twiml,
                    from_=self.from_number,
                    to=to,
                )
            )
            
            return {
                "sid": result.sid,
                "status": result.status,
            }
            
        except TwilioRestException as e:
            raise Exception(f"Twilio call error: {e.msg}")
    
    async def verify_phone_number(self, phone: str) -> bool:
        """
        Verify if a phone number is valid using Twilio Lookup.
        """
        if not self.client:
            return True  # Dev mode
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.client.lookups.v2.phone_numbers(phone).fetch()
            )
            return result.valid
        except:
            return False
