# LangGraph MCP Appointment Assistant

A stateful, multi-agent appointment assistant using LangGraph for orchestration and MCP for pluggable LLM-backed tasks. Supports booking, rescheduling, and canceling via natural language, with Anthropic-first LLM routing and deterministic local fallbacks.

## Architecture
- Agents (LangGraph nodes): `intent → datetime → mode → confirmation`
  - Intent detects: book, reschedule, cancel, query
  - Datetime extracts `date/day/time` from NL (e.g., “tomorrow at 3pm”, “from 5pm to 6pm”), with reliable local parsing
  - Mode infers virtual vs telephonic and checks conflicts
  - Confirmation persists to storage and generates human-friendly responses
- MCP client/server: tasks run remotely via FastAPI or locally with fallbacks
- Storage: JSON + Excel persistence, atomic writes, CRUD, conflict detection

## Setup
```bash
git clone <repo>
cd <repo>
python -m venv langraph
# Linux/macOS
source langraph/bin/activate
# Windows PowerShell
.\langraph\Scripts\activate
pip install -r requirements.txt
```

Start MCP server (optional, recommended):
```bash
uvicorn server:app --reload --port 8000
```

## Environment Variables
```
ANTHROPIC_API_KEY=<your_api_key>
MCP_ENDPOINT=http://127.0.0.1:8000
MCP_TIMEOUT=2
LLM_PROVIDER=anthropic
```

## Running Examples (CLI)
```bash
python -X utf8 -u demo_cli.py chat --message "Book an appointment for 5pm tomorrow" --user-id testuser
python -X utf8 -u demo_cli.py chat --message "Change my appointment from 5pm to 6pm" --user-id testuser
python -X utf8 -u demo_cli.py chat --message "Cancel my appointment" --user-id testuser
```

## Streamlit App
```bash
streamlit run streamlit_app.py
```

## Project Structure
```
├── agents/
├── services/
├── graph/
├── data/
├── server.py
├── demo_cli.py
├── requirements.txt
├── README.md
└── streamlit_app.py
```

## Features
- Anthropic-first LLM routing with local deterministic fallback
- Natural language datetime parsing (relative and ranges)
- JSON + Excel persistence with atomic writes
- Clean logs for MCP routing (remote/local/fallback)

## Notes
- If remote MCP isn’t reachable, the client falls back locally and logs the reason
- Use `MCP_TIMEOUT=1` for faster fallback during local development
