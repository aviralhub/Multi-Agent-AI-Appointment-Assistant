# LangGraph MCP Appointment Assistant

A stateful, multi-agent appointment assistant using LangGraph for orchestration and MCP for pluggable LLM-backed tasks. Supports booking, rescheduling, and canceling via natural language, with Anthropic-first LLM routing and deterministic local fallbacks.

## Architecture
- Agents (LangGraph nodes): `intent → datetime → mode → confirmation`
  - Intent detects: book, reschedule, cancel, query
  - Datetime extracts `date/day/time` from NL (e.g., “tomorrow at 3pm”, “from 5pm to 6pm”), with reliable local parsing
  - Mode infers virtual vs telephonic and checks conflicts
  - Confirmation persists to storage and generates human-friendly responses
- MCP client/server: tasks run remotely via FastAPI or locally with fallbacks
- Storage: JSON + Excel persistence by default; optional SQLite backend available (opt-in)

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
ANTHROPIC_API_KEY=<your_api_key>   # optional, used by Anthropic provider
OPENAI_API_KEY=<your_api_key>      # optional, used by OpenAI provider
LLM_PROVIDER=anthropic             # provider to prefer (anthropic|openai|bedrock|local)
MCP_ENDPOINT=http://127.0.0.1:8000 # optional: run the local MCP FastAPI server
MCP_TIMEOUT=2                      # seconds for remote MCP calls

# Storage (optional SQLite backend)
USE_SQLITE=0                       # set to 1/true to enable SQLite backend
SQLITE_DB_PATH=data/appointments.db # optional path for the SQLite DB (default in data/)
```

## Running Examples (CLI)
```bash
python -X utf8 -u demo_cli.py chat --message "Book an appointment for 5pm tomorrow" --user-id testuser
python -X utf8 -u demo_cli.py chat --message "Change my appointment from 5pm to 6pm" --user-id testuser
python -X utf8 -u demo_cli.py chat --message "Cancel my appointment" --user-id testuser
```

## Streamlit App
```bash
streamlit run app.py
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

## Storage details & verification
- Default: JSON storage at `data/appointments.json` (atomic writes). The app will also try to write `data/appointments.xlsx` when pandas is available.
- Optional: SQLite backend. Enable with `USE_SQLITE=1` and (optionally) `SQLITE_DB_PATH` before starting the app/server.

How to inspect storage:
- JSON: open `data/appointments.json` or run in PowerShell:
  ```powershell
  Get-Content .\data\appointments.json -Raw | ConvertFrom-Json | ConvertTo-Json -Depth 4
  ```
- SQLite: inspect with Python:
  ```powershell
  python - <<'PY'
  import sqlite3, os
  db = os.getenv('SQLITE_DB_PATH', 'data/appointments.db')
  conn = sqlite3.connect(db)
  conn.row_factory = sqlite3.Row
  for r in conn.execute('SELECT * FROM appointments'):
      print(dict(r))
  conn.close()
  PY
  ```

Note: SQLite is synchronous and protected by a simple lock for local development. For production or concurrent deployments consider using Postgres or a proper DB with pooling.

## Testing
- The repo contains unit tests under `tests/`. Async tests require `pytest-asyncio` to run. Install and run tests:
```powershell
python -m pip install -r requirements.txt
python -m pip install pytest pytest-asyncio
python -m pytest -q
```

## Cleanup / removed helpers
- The repo previously included an ad-hoc `scripts/verify_storage.py` helper for manual verification; it has been removed. Use the Streamlit UI, the `demo_cli.py` examples, or the inspection commands above to verify storage behavior.

## Notes
- If remote MCP isn’t reachable, the client falls back locally and logs the reason
- Use `MCP_TIMEOUT=1` for faster fallback during local development
