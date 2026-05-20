# ride-service-agent

A personal motorcycle reliability agent built with Gemini and the Google ADK.

Status: Work in progress — the FastAPI integration is not fully wired yet. The primary development focus is the agent implementation contained in `agent/app/agent.py`, `agent/app/tools.py`, and `agent/app/prompts.py`.

Overview
This repository contains the core agent logic for a motorcycle assistant. The agents coordinate to provide maintenance advice, trip-readiness checks, reminders, and symptom-based diagnostics using a MongoDB-backed data model. The FastAPI app exists but is currently secondary and may not be fully operational in this branch.

Key files (focus)

- `agent/app/agent.py` — agent definitions and composition
	- Defines three main Agent instances:
		- `service_agent`: handles scheduled maintenance, trip-readiness, reminders, and parts availability. Uses a `McpToolset` to query MongoDB and an `insert_reminder` tool for logging reminders.
		- `diagnostics_agent`: diagnoses issues from user-described symptoms by querying `motorbike_issues`.
		- `root_agent`: coordinates routing between the specialist agents and answers simple greetings directly.
	- Agents use Gemini models (configured as `gemini-2.5-pro` in the code) and are configured with instruction text and toolsets.
	- The MCP tool integration launches a local MCP server via `npx mongodb-mcp-server` (configured in `StdioServerParameters`) and filters allowed DB operations.

- `agent/app/tools.py` — helper tools exposed to agents
	- `insert_reminder(service_type: str, due_km: int, due_date: str) -> dict`:
		- Connects to MongoDB using `MDB_MCP_CONNECTION_STRING` and inserts a document into `ride_agent_db.service_reminders`.
		- Intended to be called only after user confirmation; returns a confirmation dict with `inserted_id`.

- `agent/app/prompts.py` — agent instruction prompts and domain rules
	- Contains long-form instruction templates used to configure agent behavior and routing rules.
	- Key areas covered:
		- Routing and clarification rules for the `root_agent`.
		- Detailed `SERVICE_AGENT` logic covering assessment modes (normal vs trip), how to use `ride_logs` and `service_intervals`, parts-stock checks, and reminder rules.
		- `DIAGNOSTICS_AGENT` instructions for symptom extraction and matching against `motorbike_issues`.
		- Database schema expectations and collection names under the `DATABASE_RULES` block (e.g., `ride_logs`, `service_intervals`, `service_reminders`, `parts_stock`, `motorbike_issues`).

Environment & prerequisites (agent-focused)

- Python 3.10–3.13
- Node.js (for `npx`) — required to run `mongodb-mcp-server` when using the MCP toolset locally
- A running MongoDB instance and connection string for `MDB_MCP_CONNECTION_STRING` (or use the MCP server helper)
- Optional: a `.env` file with `MDB_MCP_CONNECTION_STRING` for local development

Installing Python dependencies

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# POSIX
# source .venv/bin/activate

cd agent
pip install -e .
```

Running the MCP server (local toolset)

The agent code expects an MCP server to be available; the agent configuration launches `npx -y mongodb-mcp-server` when the toolset is invoked. You can run the server separately for debugging:

```bash
# Example: set your MongoDB connection string then run the MCP server
export MDB_MCP_CONNECTION_STRING="mongodb://user:pass@host:port/db"
npx -y mongodb-mcp-server

# On Windows PowerShell use:
# $env:MDB_MCP_CONNECTION_STRING = "mongodb://..."
# npx -y mongodb-mcp-server
```

Testing agent tools locally
- Ensure `MDB_MCP_CONNECTION_STRING` is set and points to a test database with the expected collections.
- From a Python REPL you can import the agents and call them programmatically (the project does not yet ship an interactive runner):

```python
from app.agent import root_agent
# Use root_agent.run(...) or the ADK APIs to send a message to the agent (see ADK docs)
```

Notes
- `insert_reminder` in `tools.py` performs a direct `pymongo` insert into `ride_agent_db.service_reminders` and closes the client — ensure your connection string and DB permissions are correct.
- `prompts.py` contains the authoritative domain rules and expected collection schemas; if you modify the DB layout, update these rules accordingly.
- FastAPI (`agent/app/fast_api_app.py`) is present but not the immediate focus — current work is on agent behavior and tooling.

Next steps I can take for you
- Expand README with example agent interactions (short scripts) and a minimal test dataset.
- Add a `dev` runner script to start a local MCP server and a tiny REPL client.
- Help wire FastAPI to call the `root_agent` once you want the HTTP surface working.

If you want one of those, tell me which and I will add it next.
