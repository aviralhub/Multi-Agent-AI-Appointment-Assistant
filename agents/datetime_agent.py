from typing import Dict, Optional
import dateparser
from graph.state import GraphState, ConversationTurn
from services.mcp_client import mcp_task_async


def parse_datetime_locally(text: str) -> Dict[str, Optional[str]]:
    dt = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})
    if not dt:
        return {"date": None, "day": None, "time": None}
    return {
        "date": dt.strftime("%Y-%m-%d"),
        "day": dt.strftime("%A"),
        "time": dt.strftime("%H:%M"),
    }


async def run_datetime(state: GraphState) -> GraphState:
    if state.operation not in {"book", "reschedule"}:
        return state

    user_utterance = next((t.content for t in reversed(state.turns) if t.role == "user"), "")
    result = await mcp_task_async(
        agent_name="datetime",
        task="extract_datetime",
        payload={"text": user_utterance},
        fallback=lambda: {"date": None, "day": None, "time": None},
    )
    date = result.get("date")
    day = result.get("day")
    time = result.get("time")

    if not date or not time:
        state.datetime_attempts += 1
        if state.datetime_attempts >= 2:
            state.turns.append(ConversationTurn(
                role="assistant",
                content="I couldn’t understand the date/time. Please provide a specific date (YYYY-MM-DD) and time (HH:MM)."
            ))
            state.waiting_for_input = True
            state.fallback_reason = None
            state.fallback_stage = None
            return state
        state.fallback_reason = "Invalid or missing date/time"
        state.fallback_stage = "datetime"
        return state

    state.appointment.date = date
    state.appointment.day = day
    state.appointment.time = time
    state.datetime_attempts = 0
    state.waiting_for_input = False
    return state
