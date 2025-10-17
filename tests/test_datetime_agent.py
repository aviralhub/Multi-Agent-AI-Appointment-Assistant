import pytest

from graph.state import GraphState, ConversationTurn
from agents.datetime_agent import run_datetime


@pytest.mark.asyncio
async def test_datetime_tomorrow_3pm():
    st = GraphState()
    st.operation = "book"
    st.turns.append(ConversationTurn(role="user", content="Book a virtual appointment tomorrow at 3pm"))
    out = await run_datetime(st)
    assert out.appointment.time is not None
    assert out.appointment.date is not None


@pytest.mark.asyncio
async def test_datetime_reschedule_from_to():
    st = GraphState()
    st.operation = "reschedule"
    st.turns.append(ConversationTurn(role="user", content="Change my appointment from 5pm to 6pm"))
    out = await run_datetime(st)
    assert out.appointment.time is not None


@pytest.mark.asyncio
async def test_datetime_invalid_then_prompt():
    st = GraphState()
    st.operation = "book"
    st.turns.append(ConversationTurn(role="user", content="asdfasdf"))
    out = await run_datetime(st)
    if not out.appointment.time:
        out = await run_datetime(out)
    assert out.waiting_for_input or out.appointment.time is not None
