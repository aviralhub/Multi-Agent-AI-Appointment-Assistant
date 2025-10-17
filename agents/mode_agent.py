from typing import Optional
from graph.state import GraphState
from services.mcp_client import mcp_task_async
from services.storage import StorageService


def guess_mode_locally(text: str) -> Optional[str]:
    t = text.lower()
    if any(k in t for k in ["virtual", "video", "online"]):
        return "virtual"
    if any(k in t for k in ["phone", "tele", "call", "telephonic"]):
        return "telephonic"
    return None


async def run_mode(state: GraphState) -> GraphState:
    if state.operation not in {"book", "reschedule"}:
        return state

    user_utterance = next((t.content for t in reversed(state.turns) if t.role == "user"), "")

    result = await mcp_task_async(
        agent_name="mode",
        task="infer_mode",
        payload={"text": user_utterance},
        fallback=lambda: {"mode": "virtual"},
    )
    mode = result.get("mode") or "virtual"
    state.appointment.mode = mode

    storage = StorageService()
    # Check any-time-slot conflict (any user) for realism; still track per-user list
    if state.appointment.date and state.appointment.time and storage.has_time_slot_taken(state.appointment.date, state.appointment.time):
        state.fallback_reason = (
            f"A booking already exists at {state.appointment.date} {state.appointment.time}. "
            "Please provide a different time."
        )
        state.fallback_stage = "conflict"
        return state

    if state.appointment.date and state.appointment.time:
        state.conflicts = storage.find_conflicts(
            date=state.appointment.date,
            time=state.appointment.time,
            user_id=state.appointment.user_id or "default",
        )
    if state.conflicts:
        state.fallback_reason = "You already have an appointment at this time. Suggest another time."
        state.fallback_stage = "conflict"
    return state
