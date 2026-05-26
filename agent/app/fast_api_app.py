# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from pathlib import Path

from dotenv import load_dotenv

import google.auth
from fastapi import FastAPI
from fastapi.responses import FileResponse
from google.adk.cli.fast_api import get_fast_api_app
from google.cloud import logging as google_cloud_logging

from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback

env_candidates = [
    Path(__file__).resolve().parents[1] / ".env",
    Path(__file__).resolve().parents[2] / ".env",
]
for env_path in env_candidates:
    if env_path.exists():
        load_dotenv(env_path)

setup_telemetry()
try:
    _, project_id = google.auth.default()
except Exception:
    project_id = None

try:
    logging_client = google_cloud_logging.Client()
    logger = logging_client.logger(__name__)
except Exception:
    import logging as _logging

    logger = _logging.getLogger(__name__)
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

# Artifact bucket for ADK (created by Terraform, passed via env var)
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# In-memory session configuration - no persistent storage
session_service_uri = None

artifact_service_uri = f"gs://{logs_bucket_name}" if logs_bucket_name else None

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=artifact_service_uri,
    allow_origins=allow_origins,
    session_service_uri=session_service_uri,
    otel_to_cloud=True,
)
app.title = "agent"
app.description = "API for interacting with the Agent agent"

UI_INDEX_PATH = Path(__file__).parent / "ui" / "index.html"


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logger.log_struct(feedback.model_dump(), severity="INFO")
    return {"status": "success"}


@app.get("/health")
def health_check() -> dict[str, str]:
    """Simple liveness probe for the service."""
    return {"status": "ok"}


@app.get("/ui")
def ui() -> FileResponse:
    """Serve the lightweight chat UI."""
    return FileResponse(UI_INDEX_PATH)


@app.get("/ready")
def readiness_check() -> dict[str, object]:
    """Readiness probe. Reports whether optional external wiring is configured.

    - `mdb_configured`: True when `MDB_MCP_CONNECTION_STRING` is set in env.
    """
    mdb_configured = bool(os.environ.get("MDB_MCP_CONNECTION_STRING"))
    return {"ready": True, "mdb_configured": mdb_configured}


@app.get("/readyz")
def readiness_check_alias() -> dict[str, object]:
    """Alias for readiness probe to avoid conflicts with platform reserved paths."""
    return {"ready": True, "mdb_configured": bool(os.environ.get("MDB_MCP_CONNECTION_STRING"))}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
