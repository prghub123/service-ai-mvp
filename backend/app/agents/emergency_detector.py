"""
Multi-layer emergency detection system.
Layer 1: Keyword matching (instant, no LLM)
Layer 2: LLM classification 
Layer 3: Safety checks and confidence thresholds
"""

import re
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from app.integrations.openai_client import OpenAIClient


class UrgencyLevel(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"
    EMERGENCY = "emergency"


@dataclass
class EmergencyDetectionResult:
    """Result of emergency detection pipeline."""
    urgency: UrgencyLevel
    confidence: float
    keywords_matched: list
    llm_reasoning: Optional[str]
    review_recommended: bool
    safety_override: bool


# Emergency keywords by category
EMERGENCY_KEYWORDS = {
    "water": [
        r"\bflood(ing|ed)?\b",
        r"\bwater\s+everywhere\b",
        r"\bburst\s*(pipe)?\b",
        r"\bspray(ing|ed)?\b",
        r"\bgushing\b",
        r"\bpipe\s+broke\b",
        r"\bwater\s+damage\b",
        r"\bsewage\b",
        r"\boverflow(ing|ed)?\b",
        r"\bbacked?\s*up\b",
    ],
    "gas": [
        r"\bgas\s+smell\b",
        r"\bgas\s+leak\b",
        r"\bsmell(s|ing)?\s+gas\b",
        r"\brotten\s+egg\b",
    ],
    "hvac_extreme": [
        r"\bno\s+(heat|heating)\b",
        r"\bno\s+(ac|air|cooling)\b",
        r"\bfreezing\b",
        r"\bheat\s*stroke\b",
        r"\belderly\b.*\b(hot|cold)\b",
        r"\bbaby\b.*\b(hot|cold)\b",
        r"\binfant\b.*\b(hot|cold)\b",
    ],
    "electrical": [
        r"\bspark(ing|s)?\b",
        r"\bsmoke\b",
        r"\bburn(ing|t)?\s+smell\b",
        r"\belectrical\s+fire\b",
    ],
    "urgency_words": [
        r"\bemergency\b",
        r"\burgent(ly)?\b",
        r"\basap\b",
        r"\bimmediate(ly)?\b",
        r"\bright\s+now\b",
        r"\bcan'?t\s+wait\b",
    ],
}


class EmergencyDetector:
    """
    Multi-layer emergency detection system.
    Designed to err on the side of caution - better to escalate than miss an emergency.
    """
    
    def __init__(self, openai_client: Optional[OpenAIClient] = None):
        self.openai = openai_client or OpenAIClient()
        
        # Compile regex patterns for efficiency
        self.patterns = {}
        for category, keywords in EMERGENCY_KEYWORDS.items():
            self.patterns[category] = [
                re.compile(pattern, re.IGNORECASE) 
                for pattern in keywords
            ]
    
    async def detect(self, text: str) -> EmergencyDetectionResult:
        """
        Run full emergency detection pipeline.
        
        Layer 1: Keyword matching (instant)
        Layer 2: LLM classification
        Layer 3: Safety checks
        """
        
        # Layer 1: Keyword matching
        keywords_matched, keyword_urgency = self._keyword_detection(text)
        
        # Layer 2: LLM classification
        llm_urgency, llm_confidence, llm_reasoning = await self._llm_classification(text)
        
        # Layer 3: Safety checks and final decision
        final_result = self._safety_check(
            text=text,
            keyword_urgency=keyword_urgency,
            keywords_matched=keywords_matched,
            llm_urgency=llm_urgency,
            llm_confidence=llm_confidence,
            llm_reasoning=llm_reasoning,
        )
        
        return final_result
    
    def _keyword_detection(self, text: str) -> Tuple[list, UrgencyLevel]:
        """
        Layer 1: Fast keyword-based detection.
        Returns list of matched keywords and suggested urgency.
        """
        matched = []
        
        for category, patterns in self.patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    matched.append(f"{category}:{pattern.pattern}")
        
        # Determine urgency from keywords
        if any("gas" in kw for kw in matched):
            return matched, UrgencyLevel.EMERGENCY
        elif any("water" in kw and ("flood" in kw or "burst" in kw or "spray" in kw) for kw in matched):
            return matched, UrgencyLevel.EMERGENCY
        elif any("electrical" in kw for kw in matched):
            return matched, UrgencyLevel.EMERGENCY
        elif matched:
            return matched, UrgencyLevel.URGENT
        else:
            return matched, UrgencyLevel.ROUTINE
    
    async def _llm_classification(self, text: str) -> Tuple[UrgencyLevel, float, str]:
        """
        Layer 2: LLM-based urgency classification.
        """
        prompt = f"""Classify the urgency of this customer service request for a plumbing/HVAC business.

Customer message: "{text}"

Classification rules:
- EMERGENCY: Immediate danger to property or people (flooding, gas leak, no heat in freezing temps, no AC with vulnerable people)
- URGENT: Needs attention within 24 hours (water leak not causing damage, partial HVAC failure, hot water out)
- ROUTINE: Can be scheduled normally (maintenance, minor issues, quotes)

IMPORTANT: When in doubt, err toward higher urgency. It's better to treat a routine issue as urgent than miss an emergency.

Respond in this exact format:
URGENCY: [EMERGENCY/URGENT/ROUTINE]
CONFIDENCE: [0.0-1.0]
REASONING: [brief explanation]"""

        try:
            response = await self.openai.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )
            
            # Parse response
            lines = response.strip().split("\n")
            urgency = UrgencyLevel.ROUTINE
            confidence = 0.5
            reasoning = ""
            
            for line in lines:
                if line.startswith("URGENCY:"):
                    urgency_str = line.replace("URGENCY:", "").strip().upper()
                    if urgency_str == "EMERGENCY":
                        urgency = UrgencyLevel.EMERGENCY
                    elif urgency_str == "URGENT":
                        urgency = UrgencyLevel.URGENT
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(line.replace("CONFIDENCE:", "").strip())
                    except:
                        confidence = 0.5
                elif line.startswith("REASONING:"):
                    reasoning = line.replace("REASONING:", "").strip()
            
            return urgency, confidence, reasoning
            
        except Exception as e:
            # If LLM fails, return uncertain result
            return UrgencyLevel.URGENT, 0.5, f"LLM classification failed: {str(e)}"
    
    def _safety_check(
        self,
        text: str,
        keyword_urgency: UrgencyLevel,
        keywords_matched: list,
        llm_urgency: UrgencyLevel,
        llm_confidence: float,
        llm_reasoning: str,
    ) -> EmergencyDetectionResult:
        """
        Layer 3: Safety checks and final decision.
        Applies conservative rules to avoid missing emergencies.
        """
        
        safety_override = False
        review_recommended = False
        
        # Rule 1: If keywords say emergency but LLM doesn't, trust keywords but flag for review
        if keyword_urgency == UrgencyLevel.EMERGENCY and llm_urgency != UrgencyLevel.EMERGENCY:
            final_urgency = UrgencyLevel.URGENT  # At minimum
            review_recommended = True
            safety_override = True
        
        # Rule 2: If LLM has low confidence on routine, upgrade to urgent
        elif llm_urgency == UrgencyLevel.ROUTINE and llm_confidence < 0.8:
            final_urgency = UrgencyLevel.URGENT
            review_recommended = True
        
        # Rule 3: If keywords matched and LLM confidence is low, use keyword result
        elif keywords_matched and llm_confidence < 0.7:
            final_urgency = keyword_urgency
            safety_override = True
        
        # Rule 4: Otherwise trust LLM
        else:
            final_urgency = llm_urgency
        
        # Rule 5: Gas-related keywords always trigger emergency review
        if any("gas" in kw for kw in keywords_matched):
            if final_urgency != UrgencyLevel.EMERGENCY:
                review_recommended = True
        
        return EmergencyDetectionResult(
            urgency=final_urgency,
            confidence=llm_confidence,
            keywords_matched=keywords_matched,
            llm_reasoning=llm_reasoning,
            review_recommended=review_recommended,
            safety_override=safety_override,
        )
    
    def quick_check(self, text: str) -> bool:
        """
        Quick synchronous check for obvious emergencies.
        Used when we need immediate decision without LLM.
        """
        _, urgency = self._keyword_detection(text)
        return urgency == UrgencyLevel.EMERGENCY
