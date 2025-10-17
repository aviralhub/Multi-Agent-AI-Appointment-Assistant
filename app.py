import os
import uuid
import traceback
from dotenv import load_dotenv
import streamlit as st
import asyncio

from graph.graph import build_graph
from graph.state import GraphState
from services.storage import StorageService

# Load environment variables from .env if present
load_dotenv(override=False)

st.set_page_config(page_title="LangGraph MCP Appointment Assistant", page_icon="🗓️", layout="centered")

st.title("🗓️ LangGraph MCP Appointment Assistant")

# Sidebar: environment and MCP info
with st.sidebar:
    st.subheader("Environment")
    st.caption("Values loaded from environment / .env")
    st.text_input("LLM_PROVIDER", os.getenv("LLM_PROVIDER", "(not set)"))
    st.text_input("ANTHROPIC_API_KEY", "***" if os.getenv("ANTHROPIC_API_KEY") else "(not set)")
    st.text_input("MCP_ENDPOINT", os.getenv("MCP_ENDPOINT", "(not set)"))
    st.text_input("MCP_TIMEOUT", os.getenv("MCP_TIMEOUT", "(not set)"))

# App state
if "state" not in st.session_state:
    st.session_state.state = GraphState()
    st.session_state.state.appointment.user_id = str(uuid.uuid4())
    st.session_state.graph = build_graph()

state: GraphState = st.session_state.state
graph = st.session_state.graph

st.subheader("Chat")
text = st.text_area("Message", placeholder="Book an appointment for 3pm tomorrow", height=120)
if st.button("Send", type="primary") and text.strip():
    # Append as plain dicts to avoid Pydantic cross-module type issues
    state.turns.append({"role": "user", "content": text.strip()})
    try:
        # Build a fully normalized dict for GraphState
        # Normalize turns
        turns = []
        for t in state.turns:
            if isinstance(t, dict):
                turns.append({"role": t.get("role"), "content": t.get("content")})
            else:
                turns.append({"role": getattr(t, "role", None), "content": getattr(t, "content", None)})
        # Normalize appointment
        appt = state.appointment
        appt_dict = {
            "date": getattr(appt, "date", None) if not isinstance(appt, dict) else appt.get("date"),
            "day": getattr(appt, "day", None) if not isinstance(appt, dict) else appt.get("day"),
            "time": getattr(appt, "time", None) if not isinstance(appt, dict) else appt.get("time"),
            "mode": getattr(appt, "mode", None) if not isinstance(appt, dict) else appt.get("mode"),
            "notes": getattr(appt, "notes", None) if not isinstance(appt, dict) else appt.get("notes"),
            "user_id": getattr(appt, "user_id", None) if not isinstance(appt, dict) else appt.get("user_id"),
        }
        norm = {
            "turns": turns,
            "intent": getattr(state, "intent", None),
            "operation": getattr(state, "operation", None),
            "appointment": appt_dict,
            "conflicts": getattr(state, "conflicts", []),
            "fallback_reason": getattr(state, "fallback_reason", None),
            "fallback_stage": getattr(state, "fallback_stage", None),
            "datetime_attempts": getattr(state, "datetime_attempts", 0),
            "waiting_for_input": getattr(state, "waiting_for_input", False),
            "done": getattr(state, "done", False),
        }
        out = asyncio.run(graph.ainvoke(GraphState(**norm)))
        st.session_state.state = out if isinstance(out, GraphState) else GraphState(**norm)
    except Exception as e:
        st.error(f"Error during graph execution: {e}")
        st.code(traceback.format_exc())

if state.turns:
    st.markdown("### Conversation")
    for t in state.turns[-12:]:
        if isinstance(t, dict):
            role_v = t.get("role")
            content_v = t.get("content")
        else:
            role_v = getattr(t, "role", None)
            content_v = getattr(t, "content", None)
        role = "You" if role_v == "user" else "Assistant"
        st.markdown(f"**{role}:** {content_v}")

st.markdown("### Your Appointments")
store = StorageService()
items = store.list_appointments(user_id=state.appointment.user_id)
if items:
    st.table(items)
else:
    st.caption("No appointments yet.")
