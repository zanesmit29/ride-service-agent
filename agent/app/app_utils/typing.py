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
import uuid
from datetime import date
from typing import (
    Literal,
)

from google.adk.events.event import Event
from google.genai.types import Content
from pydantic import (
    BaseModel,
    Field,
)


class Request(BaseModel):
    """Represents the input for a chat request with optional configuration."""

    message: Content
    events: list[Event]
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    model_config = {"extra": "allow"}


class Feedback(BaseModel):
    """Represents feedback for a conversation."""

    score: int | float
    text: str | None = ""
    log_type: Literal["feedback"] = "feedback"
    service_name: Literal["agent"] = "agent"
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class VehicleTabData(BaseModel):
    """Read-only vehicle status payload for the UI."""

    state: Literal["loading", "ready", "empty", "error"] = "ready"
    latest_odometer_end_km: int | None = None
    last_ride_date: date | None = None
    next_service_highlight: str | None = None
    message: str | None = None


class RemindersTabData(BaseModel):
    """Read-only reminders payload for the UI."""

    state: Literal["loading", "ready", "empty", "error"] = "ready"
    open_reminders: list[dict[str, object]] = Field(default_factory=list)
    message: str | None = None


class TripsTabData(BaseModel):
    """Read-only trip summary payload for the UI."""

    state: Literal["loading", "ready", "empty", "error"] = "ready"
    recent_rides: list[dict[str, object]] = Field(default_factory=list)
    totals: dict[str, object] = Field(default_factory=dict)
    weather_summary: str | None = None
    message: str | None = None


class ProfileTabData(BaseModel):
    """Read-only rider profile payload for the UI."""

    state: Literal["loading", "ready", "empty", "error"] = "ready"
    user_id: str
    profile: dict[str, object] = Field(default_factory=dict)
    message: str | None = None


class TabDataBundle(BaseModel):
    """Combined tab-data contract for the frontend."""

    vehicle: VehicleTabData
    reminders: RemindersTabData
    trips: TripsTabData
    profile: ProfileTabData
