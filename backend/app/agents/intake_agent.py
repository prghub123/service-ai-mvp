"""
Intake Agent - Handles customer intake via phone or chat.
Uses LangGraph for state management and tool orchestration.
"""

from typing import TypedDict, Annotated, Literal, Optional, List
from uuid import UUID
from datetime import datetime, date, time
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.agents.emergency_detector import EmergencyDetector, UrgencyLevel
from app.integrations.openai_client import OpenAIClient
from app.config import get_settings

settings = get_settings()


# State definition for the intake conversation
class IntakeState(TypedDict):
    """State maintained throughout the intake conversation."""
    
    # Conversation
    messages: List[dict]
    current_step: str
    
    # Business context
    business_id: str
    business_name: str
    
    # Customer info (may be pre-filled for in-app calls)
    customer_phone: Optional[str]
    customer_name: Optional[str]
    customer_id: Optional[str]
    
    # Extracted information
    service_type: Optional[str]
    issue_description: Optional[str]
    urgency: Optional[str]
    urgency_confidence: Optional[float]
    emergency_keywords: List[str]
    
    # Address
    address_street: Optional[str]
    address_city: Optional[str]
    address_state: Optional[str]
    address_zip: Optional[str]
    address_id: Optional[str]
    
    # Scheduling
    preferred_date: Optional[str]
    preferred_time: Optional[str]
    
    # Outcome
    job_id: Optional[str]
    job_confirmation_code: Optional[str]
    outcome: Optional[str]  # 'booking_confirmed', 'emergency_dispatched', 'callback_requested', etc.
    
    # Error handling
    error: Optional[str]


class IntakeAgent:
    """
    Agent that handles customer intake conversations.
    Supports both phone (via Vapi) and chat interfaces.
    """
    
    def __init__(
        self,
        business_id: str,
        business_name: str,
        db_session=None,
    ):
        self.business_id = business_id
        self.business_name = business_name
        self.db = db_session
        self.openai = OpenAIClient()
        self.emergency_detector = EmergencyDetector(self.openai)
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine for intake."""
        
        workflow = StateGraph(IntakeState)
        
        # Add nodes
        workflow.add_node("greet", self._greet_node)
        workflow.add_node("collect_issue", self._collect_issue_node)
        workflow.add_node("detect_urgency", self._detect_urgency_node)
        workflow.add_node("handle_emergency", self._handle_emergency_node)
        workflow.add_node("collect_contact", self._collect_contact_node)
        workflow.add_node("collect_address", self._collect_address_node)
        workflow.add_node("collect_schedule", self._collect_schedule_node)
        workflow.add_node("confirm_booking", self._confirm_booking_node)
        workflow.add_node("create_job", self._create_job_node)
        workflow.add_node("farewell", self._farewell_node)
        
        # Set entry point
        workflow.set_entry_point("greet")
        
        # Add edges
        workflow.add_edge("greet", "collect_issue")
        workflow.add_edge("collect_issue", "detect_urgency")
        
        # Conditional edge after urgency detection
        workflow.add_conditional_edges(
            "detect_urgency",
            self._route_after_urgency,
            {
                "emergency": "handle_emergency",
                "normal": "collect_contact",
            }
        )
        
        workflow.add_edge("handle_emergency", "farewell")
        workflow.add_edge("collect_contact", "collect_address")
        workflow.add_edge("collect_address", "collect_schedule")
        workflow.add_edge("collect_schedule", "confirm_booking")
        
        # Conditional edge after confirmation
        workflow.add_conditional_edges(
            "confirm_booking",
            self._route_after_confirmation,
            {
                "confirmed": "create_job",
                "modify": "collect_schedule",
                "cancel": "farewell",
            }
        )
        
        workflow.add_edge("create_job", "farewell")
        workflow.add_edge("farewell", END)
        
        return workflow.compile()
    
    # Node implementations
    
    async def _greet_node(self, state: IntakeState) -> IntakeState:
        """Initial greeting."""
        greeting = f"Hi! Thanks for calling {state['business_name']}. How can I help you today?"
        
        state["messages"].append({"role": "assistant", "content": greeting})
        state["current_step"] = "greeting"
        
        return state
    
    async def _collect_issue_node(self, state: IntakeState) -> IntakeState:
        """Collect and understand the customer's issue."""
        
        # Get the customer's response (last human message)
        customer_message = self._get_last_human_message(state)
        
        # Use LLM to extract service type and description
        extraction_prompt = f"""Extract the service type and issue description from this customer message.

Customer: "{customer_message}"

Service types: plumbing, hvac, water_heater, drain, general

Respond in this format:
SERVICE_TYPE: [type]
DESCRIPTION: [brief description of the issue]
NEEDS_CLARIFICATION: [yes/no]
CLARIFICATION_QUESTION: [question to ask if needed]"""

        response = await self.openai.complete(
            messages=[{"role": "user", "content": extraction_prompt}],
            temperature=0.3,
        )
        
        # Parse response
        for line in response.split("\n"):
            if line.startswith("SERVICE_TYPE:"):
                state["service_type"] = line.replace("SERVICE_TYPE:", "").strip().lower()
            elif line.startswith("DESCRIPTION:"):
                state["issue_description"] = line.replace("DESCRIPTION:", "").strip()
        
        state["current_step"] = "issue_collected"
        return state
    
    async def _detect_urgency_node(self, state: IntakeState) -> IntakeState:
        """Detect urgency level using multi-layer detection."""
        
        # Combine all relevant text for analysis
        text_to_analyze = state.get("issue_description", "")
        customer_messages = " ".join([
            m["content"] for m in state["messages"] 
            if m["role"] == "human"
        ])
        text_to_analyze = f"{text_to_analyze} {customer_messages}"
        
        # Run emergency detection
        result = await self.emergency_detector.detect(text_to_analyze)
        
        state["urgency"] = result.urgency.value
        state["urgency_confidence"] = result.confidence
        state["emergency_keywords"] = result.keywords_matched
        state["current_step"] = "urgency_detected"
        
        return state
    
    async def _handle_emergency_node(self, state: IntakeState) -> IntakeState:
        """Handle emergency dispatch."""
        
        # For emergencies, we need to:
        # 1. Get/confirm address immediately
        # 2. Find nearest available tech
        # 3. Auto-dispatch
        # 4. Notify everyone
        
        # If we have customer context (from app), we may already have address
        if state.get("address_id"):
            pass  # Use existing address
        else:
            # Ask for address
            state["messages"].append({
                "role": "assistant",
                "content": "I understand this is urgent. Let me get your address so I can send help right away. What's your address?"
            })
            # In a real implementation, this would wait for response
        
        # Create emergency job (placeholder - would use JobService)
        state["outcome"] = "emergency_dispatched"
        state["current_step"] = "emergency_handled"
        
        # Emergency response message
        state["messages"].append({
            "role": "assistant",
            "content": "I've dispatched a technician to your location. They should arrive within 30 minutes. You'll receive a text with their contact information. Is there anything else you need help with right now?"
        })
        
        return state
    
    async def _collect_contact_node(self, state: IntakeState) -> IntakeState:
        """Collect customer contact information."""
        
        # If we already have customer info (from app), skip
        if state.get("customer_phone") and state.get("customer_name"):
            state["current_step"] = "contact_collected"
            return state
        
        # Ask for contact info
        if not state.get("customer_name"):
            state["messages"].append({
                "role": "assistant",
                "content": "I'd be happy to help schedule that for you. Can I get your name?"
            })
        
        state["current_step"] = "collecting_contact"
        return state
    
    async def _collect_address_node(self, state: IntakeState) -> IntakeState:
        """Collect service address."""
        
        # If we have address from customer profile, confirm it
        if state.get("address_id"):
            state["messages"].append({
                "role": "assistant",
                "content": f"I have your address on file as {state.get('address_street')}. Is that where you need service?"
            })
        else:
            state["messages"].append({
                "role": "assistant",
                "content": "What's the address where you need service?"
            })
        
        state["current_step"] = "collecting_address"
        return state
    
    async def _collect_schedule_node(self, state: IntakeState) -> IntakeState:
        """Collect scheduling preferences."""
        
        # In real implementation, would check availability first
        state["messages"].append({
            "role": "assistant",
            "content": "I have availability tomorrow between 9-11am or 1-3pm. Which works better for you?"
        })
        
        state["current_step"] = "collecting_schedule"
        return state
    
    async def _confirm_booking_node(self, state: IntakeState) -> IntakeState:
        """Confirm the booking details."""
        
        confirmation = f"""Let me confirm the details:
- Service: {state.get('service_type', 'General service')}
- Issue: {state.get('issue_description', 'As discussed')}
- Address: {state.get('address_street', 'On file')}
- Time: {state.get('preferred_date', 'Tomorrow')} {state.get('preferred_time', '9-11am')}

Does that all look correct?"""
        
        state["messages"].append({"role": "assistant", "content": confirmation})
        state["current_step"] = "confirming"
        
        return state
    
    async def _create_job_node(self, state: IntakeState) -> IntakeState:
        """Create the job in the system."""
        
        # In real implementation, would use JobService
        state["job_confirmation_code"] = "SVC-ABC123"
        state["outcome"] = "booking_confirmed"
        state["current_step"] = "job_created"
        
        return state
    
    async def _farewell_node(self, state: IntakeState) -> IntakeState:
        """End the conversation."""
        
        if state.get("outcome") == "booking_confirmed":
            farewell = f"You're all set! Your confirmation code is {state.get('job_confirmation_code')}. You'll receive a text confirmation shortly. Is there anything else I can help with?"
        elif state.get("outcome") == "emergency_dispatched":
            farewell = "Help is on the way. Stay safe, and don't hesitate to call back if you need anything else."
        else:
            farewell = "Thank you for calling. Have a great day!"
        
        state["messages"].append({"role": "assistant", "content": farewell})
        state["current_step"] = "complete"
        
        return state
    
    # Routing functions
    
    def _route_after_urgency(self, state: IntakeState) -> Literal["emergency", "normal"]:
        """Route based on urgency level."""
        if state.get("urgency") == UrgencyLevel.EMERGENCY.value:
            return "emergency"
        return "normal"
    
    def _route_after_confirmation(self, state: IntakeState) -> Literal["confirmed", "modify", "cancel"]:
        """Route based on customer confirmation."""
        # In real implementation, would parse customer's response
        return "confirmed"
    
    # Helper methods
    
    def _get_last_human_message(self, state: IntakeState) -> str:
        """Get the last message from the human."""
        for msg in reversed(state["messages"]):
            if msg["role"] == "human":
                return msg["content"]
        return ""
    
    # Public interface
    
    async def process_message(
        self,
        message: str,
        state: Optional[IntakeState] = None,
    ) -> IntakeState:
        """
        Process a single message in the conversation.
        Can be called iteratively for chat, or with full transcript for voice.
        """
        
        # Initialize state if not provided
        if state is None:
            state = IntakeState(
                messages=[],
                current_step="start",
                business_id=self.business_id,
                business_name=self.business_name,
                customer_phone=None,
                customer_name=None,
                customer_id=None,
                service_type=None,
                issue_description=None,
                urgency=None,
                urgency_confidence=None,
                emergency_keywords=[],
                address_street=None,
                address_city=None,
                address_state=None,
                address_zip=None,
                address_id=None,
                preferred_date=None,
                preferred_time=None,
                job_id=None,
                job_confirmation_code=None,
                outcome=None,
                error=None,
            )
        
        # Add the human message
        state["messages"].append({"role": "human", "content": message})
        
        # Run the graph
        result = await self.graph.ainvoke(state)
        
        return result
    
    def get_last_response(self, state: IntakeState) -> str:
        """Get the last assistant message from the state."""
        for msg in reversed(state["messages"]):
            if msg["role"] == "assistant":
                return msg["content"]
        return ""
