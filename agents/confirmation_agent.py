from typing import Dict
from graph.state import GraphState
from services.storage import StorageService
from services.mcp_client import mcp_task_async


async def run_confirmation(state: GraphState) -> GraphState:
    op = state.operation
    storage = StorageService()

    if op == "cancel":
        ok = storage.delete_latest_for_user(state.appointment.user_id or "default")
        text = "Your latest appointment has been cancelled." if ok else "No appointment found to cancel."
        from graph.state import ConversationTurn
        state.turns.append(ConversationTurn(role="assistant", content=text))
        state.done = True
        return state

    if op == "reschedule":
        # Update latest for user with new date/time/mode
        updated = storage.update_latest_for_user(
            state.appointment.user_id or "default",
            lambda it: {
                **it,
                "Date": state.appointment.date,
                "Day": state.appointment.day,
                "Time": state.appointment.time,
                "Mode": state.appointment.mode,
            },
        )
        if not updated:
            from graph.state import ConversationTurn
            state.turns.append(ConversationTurn(role="assistant", content="No existing appointment to reschedule."))
            state.done = True
            return state

    if op in {"book", "reschedule"}:
        if state.fallback_stage == "conflict":
            msg = state.fallback_reason or "There is a conflict. Please propose another time."
            from graph.state import ConversationTurn
            state.turns.append(ConversationTurn(role="assistant", content=msg))
            state.done = False
            return state

        if op == "book":
            storage.save_appointment(
                date=state.appointment.date,
                day=state.appointment.day,
                time=state.appointment.time,
                mode=state.appointment.mode,
                notes=state.appointment.notes or "",
                user_id=state.appointment.user_id or "default",
            )

        resp = await mcp_task_async(
            agent_name="confirmation",
            task="generate_confirmation",
            payload={
                "date": state.appointment.date,
                "day": state.appointment.day,
                "time": state.appointment.time,
                "mode": state.appointment.mode,
            },
            fallback=lambda: {"text": f"Booked {state.appointment.mode} appointment on {state.appointment.day}, {state.appointment.date} at {state.appointment.time}."},
        )
        text = resp.get("text") or (
            f"Your {state.appointment.mode} appointment is booked for {state.appointment.date}, {state.appointment.day} at {state.appointment.time}."
        )
        from graph.state import ConversationTurn
        state.turns.append(ConversationTurn(role="assistant", content=text))
        state.done = True
        return state

    # default fallthrough
    state.done = True
    return state
