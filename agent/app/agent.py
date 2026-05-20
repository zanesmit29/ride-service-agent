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
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from .tools import insert_reminder
from .prompts import ROOT_AGENT_INSTRUCTIONS, SERVICE_AGENT_INSTRUCTIONS, DIAGNOSTICS_AGENT_INSTRUCTIONS

load_dotenv()

CONNECTION_STRING = os.getenv("MDB_MCP_CONNECTION_STRING")
if not CONNECTION_STRING:
    raise ValueError("MDB_MCP_CONNECTION_STRING is not set in the environment.")

MONGO_MCP_ENV = {
    "MDB_MCP_CONNECTION_STRING": CONNECTION_STRING,
    "MDB_MCP_DISABLED_TOOLS": "atlas,create-index,collection-indexes",
    "MDB_MCP_TELEMETRY": "disabled",
}

def build_mongo_toolset(tool_filter: list[str]) -> McpToolset:
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "mongodb-mcp-server"],
                env=MONGO_MCP_ENV,
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
        build_mongo_toolset(["find", "aggregate", "collection-schema", "count", "list-collections"]),
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

root_agent = Agent(
    model="gemini-2.5-pro",
    name="ride_service_agent",
    description="Coordinates the motorcycle assistant, routing maintenance and trip-readiness questions to service_agent and symptom-based diagnosis questions to diagnostics_agent.",
    instruction=ROOT_AGENT_INSTRUCTIONS,
    tools=[],
    sub_agents=[service_agent, diagnostics_agent],
)

