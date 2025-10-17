import sys
import uuid
import click
import asyncio
from typing import Optional
from graph.graph import build_graph
from graph.state import GraphState, ConversationTurn
from services.logger import setup_logger

logger = setup_logger("cli")


@click.group()
def cli() -> None:
    pass


async def run_graph_message(graph, state: GraphState, text: str) -> GraphState:
    state.turns.append(ConversationTurn(role="user", content=text))
    try:
        output = await graph.ainvoke(state)
    except Exception as e:
        click.secho(f"Error during graph execution: {e}", fg="red")
        return state
    # Be resilient if some execution path returned a dict or unexpected object
    turns = getattr(output, "turns", None)
    if isinstance(turns, list):
        last = next((t for t in reversed(turns) if getattr(t, "role", None) == "assistant"), None)
        if last:
            click.secho(getattr(last, "content", ""), fg="green")
    return output


@cli.command()
@click.option("--user-id", default=None, help="User ID for multi-user support")
@click.option("--message", default=None, help="Send a single message and exit")
@click.option("--example", is_flag=True, help="Run example conversation")
def chat(user_id: Optional[str], message: Optional[str], example: bool) -> None:
    """Start an interactive chat or send one message for booking."""
    graph = build_graph()
    state = GraphState()
    state.appointment.user_id = user_id or str(uuid.uuid4())

    async def interactive() -> None:
        click.echo("Appointment Assistant. Type 'exit' to quit.")
        while True:
            try:
                text = click.prompt("You")
            except (EOFError, KeyboardInterrupt):
                click.echo()
                break
            if text.lower().strip() in {"exit", "quit"}:
                break
            new_state = await run_graph_message(graph, state, text)
            # Safely update state only if expected attributes are present
            for attr in [
                "turns",
                "intent",
                "operation",
                "appointment",
                "fallback_stage",
                "fallback_reason",
                "waiting_for_input",
                "datetime_attempts",
                "done",
            ]:
                if hasattr(new_state, attr):
                    setattr(state, attr, getattr(new_state, attr))
            if new_state.done:
                click.secho("Session complete.", fg="yellow")
                break

    async def single() -> None:
        new_state = await run_graph_message(graph, state, message or "")
        _ = new_state

    async def examples() -> None:
        # Example 1: booking flow
        await run_graph_message(graph, state, "Book a virtual appointment tomorrow at 3pm.")
        if not state.done:
            await run_graph_message(graph, state, "Tomorrow 3pm virtual.")
        # Example reschedule
        state.done = False
        await run_graph_message(graph, state, "Change my appointment from 5pm to 6pm.")
        if not state.done:
            await run_graph_message(graph, state, "Move it to 18:00 on the same day.")

    if example:
        asyncio.run(examples())
        return
    if message:
        asyncio.run(single())
        return
    asyncio.run(interactive())


if __name__ == "__main__":
    cli()
