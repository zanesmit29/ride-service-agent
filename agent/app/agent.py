# ruff: noqa
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
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from .tools import (
    insert_reminder,
    get_rider_profile,
    update_rider_preferences,
    get_weather_forecast,
    insert_ride_log,
    parse_natural_date_range,
)
from .prompts import (
    ROOT_AGENT_INSTRUCTIONS,
    SERVICE_AGENT_INSTRUCTIONS,
    DIAGNOSTICS_AGENT_INSTRUCTIONS,
    TRIP_PLANNING_AGENT_INSTRUCTIONS,
    RIDE_LOGGING_AGENT_INSTRUCTIONS,
)

env_candidates = [
    Path(__file__).resolve().parents[1] / ".env",
    Path(__file__).resolve().parents[2] / ".env",
]
for env_path in env_candidates:
    if env_path.exists():
        load_dotenv(env_path)

# Do not raise at import time; allow the environment to be configured at runtime.
# Tools that need the connection string will validate and raise if it's missing.


def get_mongo_mcp_env() -> dict[str, str]:
    connection_string = os.getenv("MDB_MCP_CONNECTION_STRING")
    if not connection_string:
        return {}
    return {
        "MDB_MCP_CONNECTION_STRING": connection_string,
        "MDB_MCP_DISABLED_TOOLS": "atlas,create-index,collection-indexes",
        "MDB_MCP_TELEMETRY": "disabled",
    }


def build_mongo_toolset(tool_filter: list[str]) -> McpToolset:
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "mongodb-mcp-server"],
                env=get_mongo_mcp_env(),
            ),
            timeout=120,
        ),
        tool_filter=tool_filter,
    )


service_agent = Agent(
    model="gemini-2.5-pro",
    name="service_agent",
    description="Handles motorcycle maintenance analysis, trip-readiness checks, reminder checks, and parts availability using MongoDB data.",
    instruction=SERVICE_AGENT_INSTRUCTIONS,
    tools=[
        build_mongo_toolset(
            ["find", "aggregate", "collection-schema", "count", "list-collections"]
        ),
        insert_reminder,
    ],
    output_key="service_advice",
)

diagnostics_agent = Agent(
    model="gemini-2.5-pro",
    name="diagnostics_agent",
    description="Diagnoses motorcycle issues based on user-described symptoms and a database of known issues and fixes.",
    instruction=DIAGNOSTICS_AGENT_INSTRUCTIONS,
    tools=[
        build_mongo_toolset(["find", "collection-schema"]),
    ],
    output_key="diagnosis",
)

trip_planning_agent = Agent(
    model="gemini-2.5-pro",
    name="trip_planning_agent",
    description="Recommends a riding direction or destination region based on trip dates and rider weather preferences.",
    instruction=TRIP_PLANNING_AGENT_INSTRUCTIONS,
    tools=[
        build_mongo_toolset(["find"]),
        get_rider_profile,
        parse_natural_date_range,
        get_weather_forecast,
    ],
    output_key="trip_planning_advice",
)

ride_logging_agent = Agent(
    model="gemini-2.5-pro",
    name="ride_logging_agent",
    description="Logs ride details to the database after a trip is completed, including date, distance, and any notes about the ride.",
    instruction=RIDE_LOGGING_AGENT_INSTRUCTIONS,
    tools=[
        insert_ride_log,
    ],
    output_key="logging_confirmation",
)

root_agent = Agent(
    model="gemini-2.5-pro",
    name="ride_service_agent",
    description="Coordinates the motorcycle assistant, routing maintenance and trip-readiness questions to service_agent and symptom-based diagnosis questions to diagnostics_agent.",
    instruction=ROOT_AGENT_INSTRUCTIONS,
    tools=[get_rider_profile, update_rider_preferences],
    sub_agents=[
        service_agent,
        diagnostics_agent,
        trip_planning_agent,
        ride_logging_agent,
    ],
)
