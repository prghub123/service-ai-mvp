"""OpenAI integration with fallback and timeout handling."""

import asyncio
from typing import Optional, List, Dict, Any
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

settings = get_settings()


class OpenAIClient:
    """
    Client for OpenAI API with:
    - Timeout handling
    - Fallback to cheaper model
    - Retry logic
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.primary_model = settings.OPENAI_MODEL_PRIMARY
        self.fallback_model = settings.OPENAI_MODEL_FALLBACK
        self.timeout = settings.LLM_TIMEOUT_SECONDS
    
    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        use_fallback_on_timeout: bool = True,
    ) -> str:
        """
        Get a chat completion with timeout handling.
        Falls back to cheaper model if primary times out.
        """
        if not self.client:
            # Dev mode
            return "[DEV MODE] LLM response placeholder"
        
        model = model or self.primary_model
        
        try:
            response = await asyncio.wait_for(
                self._call_api(messages, model, temperature, max_tokens),
                timeout=self.timeout
            )
            return response
            
        except asyncio.TimeoutError:
            if use_fallback_on_timeout and model != self.fallback_model:
                # Try fallback model with extended timeout
                try:
                    response = await asyncio.wait_for(
                        self._call_api(messages, self.fallback_model, temperature, max_tokens),
                        timeout=self.timeout * 2
                    )
                    return response
                except asyncio.TimeoutError:
                    raise Exception("LLM request timed out on both primary and fallback models")
            else:
                raise Exception("LLM request timed out")
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2)
    )
    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Make the actual API call with retry."""
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    
    async def complete_with_functions(
        self,
        messages: List[Dict[str, str]],
        functions: List[Dict[str, Any]],
        function_call: str = "auto",
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get a completion with function calling support.
        Used by agents to decide which tools to call.
        """
        if not self.client:
            return {"type": "message", "content": "[DEV MODE] Function call placeholder"}
        
        model = model or self.primary_model
        
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    functions=functions,
                    function_call=function_call,
                ),
                timeout=self.timeout
            )
            
            message = response.choices[0].message
            
            if message.function_call:
                return {
                    "type": "function_call",
                    "function_name": message.function_call.name,
                    "arguments": message.function_call.arguments,
                }
            else:
                return {
                    "type": "message",
                    "content": message.content,
                }
                
        except asyncio.TimeoutError:
            raise Exception("LLM function call request timed out")
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text (for RAG)."""
        if not self.client:
            return [0.0] * 1536  # Dev mode placeholder
        
        response = await self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding
