from typing import Any
import sys
try:
    from langgraph.graph import StateGraph, END  # type: ignore
except Exception:
    from lib.langgraph_shim import StateGraph, END  # fallback
from .state import GraphState, ConversationTurn
from agents.intent_agent import run_intent
from agents.datetime_agent import run_datetime
from agents.mode_agent import run_mode
from agents.confirmation_agent import run_confirmation

NODE_INTENT = "intent"
NODE_DATETIME = "datetime"
NODE_MODE = "mode"
NODE_CONFIRM = "confirm"
NODE_FALLBACK = "fallback"


def build_graph() -> Any:
    # Increase recursion limit for deep flows
    try:
        sys.setrecursionlimit(max(sys.getrecursionlimit(), 100))
    except Exception:
        pass
    graph = StateGraph(GraphState)

    graph.add_node(NODE_INTENT, run_intent)
    graph.add_node(NODE_DATETIME, run_datetime)
    graph.add_node(NODE_MODE, run_mode)
    graph.add_node(NODE_CONFIRM, run_confirmation)

    graph.set_entry_point(NODE_INTENT)

    # Conditional routing that avoids loops and short-circuits based on operation/state

    def route_after_intent(state: GraphState) -> str:
        if state.waiting_for_input:
            return "end"
        if state.fallback_reason:
            return "fallback"
        # Decide next step based on intent/operation and collected data
        if state.operation == "cancel":
            return "confirm"
        if state.operation in {"book", "reschedule"}:
            if not state.appointment.date or not state.appointment.time:
                return "datetime"
            if not state.appointment.mode:
                return "mode"
            return "confirm"
        # Unknown or query → ask again via fallback
        return "fallback"

    graph.add_conditional_edges(
        NODE_INTENT,
        route_after_intent,
        {
            "end": END,
            "fallback": NODE_FALLBACK,
            "datetime": NODE_DATETIME,
            "mode": NODE_MODE,
            "confirm": NODE_CONFIRM,
        },
    )

    def route_after_datetime(state: GraphState) -> str:
        if state.waiting_for_input:
            return "end"
        if state.fallback_reason:
            return "fallback"
        if not state.appointment.mode:
            return "mode"
        return "confirm"

    graph.add_conditional_edges(
        NODE_DATETIME,
        route_after_datetime,
        {"end": END, "fallback": NODE_FALLBACK, "mode": NODE_MODE, "confirm": NODE_CONFIRM},
    )

    def route_after_mode(state: GraphState) -> str:
        if state.waiting_for_input:
            return "end"
        if state.fallback_reason:
            return "fallback"
        return "confirm"

    graph.add_conditional_edges(
        NODE_MODE,
        route_after_mode,
        {"end": END, "fallback": NODE_FALLBACK, "confirm": NODE_CONFIRM},
    )

    def route_after_confirm(state: GraphState) -> str:
        return "end"

    graph.add_conditional_edges(
        NODE_CONFIRM,
        route_after_confirm,
        {"end": END},
    )

    async def handle_fallback(state: GraphState) -> GraphState:
        reason = state.fallback_reason or ""
        stage = state.fallback_stage or "unknown"
        if stage == "intent":
            state.turns.append(ConversationTurn(role="assistant", content="I didn’t catch what you want to do. Do you want to book, cancel, or reschedule?"))
            state.done = False
            state.fallback_reason = None
            state.fallback_stage = None
            return state
        if stage == "datetime":
            state.turns.append(ConversationTurn(role="assistant", content="I couldn’t understand the date/time. Please provide a date (e.g., 2025-10-24) and time (e.g., 14:00)."))
            state.done = False
            state.fallback_reason = None
            state.fallback_stage = None
            return state
        if stage == "conflict":
            state.turns.append(ConversationTurn(role="assistant", content=reason or "That time is unavailable. Please propose another time."))
            state.done = False
            state.fallback_reason = None
            state.fallback_stage = None
            return state
        state.turns.append(ConversationTurn(role="assistant", content="Let’s try again. What would you like to do?"))
        state.done = False
        state.fallback_reason = None
        state.fallback_stage = None
        return state

    graph.add_node(NODE_FALLBACK, handle_fallback)

    def route_from_fallback_key(state: GraphState) -> str:
        if state.intent in {None, "other"}:
            return "intent"
        if state.operation in {"book", "reschedule"} and (not state.appointment.date or not state.appointment.time):
            return "datetime"
        if state.operation in {"book", "reschedule"} and not state.appointment.mode:
            return "mode"
        if state.waiting_for_input:
            return "end"
        return "intent"

    graph.add_conditional_edges(
        NODE_FALLBACK,
        route_from_fallback_key,
        {"intent": NODE_INTENT, "datetime": NODE_DATETIME, "mode": NODE_MODE, "end": END},
    )

    return graph.compile()
