from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class Appointment(BaseModel):
    date: Optional[str] = None
    day: Optional[str] = None
    time: Optional[str] = None
    mode: Optional[str] = None
    notes: Optional[str] = None
    user_id: Optional[str] = None

class ConversationTurn(BaseModel):
    role: str
    content: str

class GraphState(BaseModel):
    turns: List[ConversationTurn] = Field(default_factory=list)
    intent: Optional[str] = None  # book | cancel | reschedule | query | other
    operation: Optional[str] = None  # book | cancel | reschedule
    appointment: Appointment = Field(default_factory=Appointment)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    fallback_reason: Optional[str] = None  # human readable
    fallback_stage: Optional[str] = None  # intent | datetime | mode | conflict
    datetime_attempts: int = 0  # prevent infinite retries in a single turn
    waiting_for_input: bool = False  # pause graph until next user input
    done: bool = False
