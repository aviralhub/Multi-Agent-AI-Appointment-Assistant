from typing import Dict
from graph.state import GraphState
from services.mcp_client import mcp_task_async

INTENTS = ["book", "cancel", "reschedule", "query", "other"]


async def run_intent(state: GraphState) -> GraphState:
    user_utterance = next((t.content for t in reversed(state.turns) if t.role == "user"), "")
    result: Dict = await mcp_task_async(
        agent_name="intent",
        task="classify_intent",
        payload={"text": user_utterance, "labels": INTENTS},
        fallback=lambda: {"intent": "other"},
    )
    intent = result.get("intent", "other")
    state.intent = intent
    if intent in {"book", "reschedule", "cancel"}:
        state.operation = intent
    if intent == "other":
        state.fallback_reason = "Unclear intent"
        state.fallback_stage = "intent"
    return state
