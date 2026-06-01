import asyncio
import json
import os
import re
from pymongo import DESCENDING, MongoClient
from datetime import datetime, timezone, date as datetime_date, timedelta
import requests
from mcp import StdioServerParameters
from google.adk.tools.mcp_tool.mcp_session_manager import (
    MCPSessionManager,
    StdioConnectionParams,
)

from app.app_utils.typing import (
    DashboardTabData,
    ProfileTabData,
    RemindersTabData,
    TabDataBundle,
    TripsTabData,
    VehicleTabData,
)


def get_connection_string() -> str:
    connection_string = os.getenv("MDB_MCP_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("MDB_MCP_CONNECTION_STRING is not set")
    return connection_string


def _bool_env(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _get_mcp_env() -> dict[str, str]:
    connection_string = os.getenv("MDB_MCP_CONNECTION_STRING")
    if not connection_string:
        return {}
    return {
        "MDB_MCP_CONNECTION_STRING": connection_string,
        "MDB_MCP_DISABLED_TOOLS": "atlas,create-index,collection-indexes",
        "MDB_MCP_TELEMETRY": "disabled",
    }


def _coerce_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _coerce_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _extract_mcp_documents(payload: dict) -> list[dict]:
    structured = payload.get("structuredContent") or payload.get("structured_content")
    if isinstance(structured, list):
        return [item for item in structured if isinstance(item, dict)]
    if isinstance(structured, dict):
        for key in ("documents", "result", "data", "items", "records"):
            value = structured.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    content = payload.get("content") or []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str):
            continue
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, list):
            return [entry for entry in decoded if isinstance(entry, dict)]
        if isinstance(decoded, dict):
            return [decoded]
    return []


async def _run_mcp_aggregate(pipeline: list[dict]) -> dict | None:
    manager = MCPSessionManager(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "mongodb-mcp-server"],
                env=_get_mcp_env(),
            ),
            timeout=120,
        ),
    )
    try:
        session = await manager.create_session()
        result = await session.call_tool(
            "aggregate",
            arguments={
                "database": "ride_agent_db",
                "collection": "ride_logs",
                "pipeline": pipeline,
            },
        )
        return result.model_dump(exclude_none=True, mode="json")
    finally:
        await manager.close()


def _get_dashboard_totals_mcp() -> tuple[int | None, float | None] | None:
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_rides": {"$sum": 1},
                "total_distance_km": {"$sum": {"$ifNull": ["$distance_km", 0]}},
            }
        }
    ]
    try:
        payload = asyncio.run(_run_mcp_aggregate(pipeline))
    except RuntimeError:
        return None
    except Exception:
        return None
    if not payload:
        return None
    docs = _extract_mcp_documents(payload)
    if not docs:
        return None
    doc = docs[0]
    total_rides = _coerce_int(doc.get("total_rides"))
    total_distance_km = _coerce_float(
        doc.get("total_distance_km") or doc.get("total_distance")
    )
    if total_rides is None and total_distance_km is None:
        return None
    return total_rides, total_distance_km


def _get_dashboard_totals_python(db) -> tuple[int | None, float | None] | None:
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_rides": {"$sum": 1},
                "total_distance_km": {"$sum": {"$ifNull": ["$distance_km", 0]}},
            }
        }
    ]
    result = list(db["ride_logs"].aggregate(pipeline))
    if not result:
        return 0, 0.0
    doc = result[0]
    total_rides = _coerce_int(doc.get("total_rides"))
    total_distance_km = _coerce_float(doc.get("total_distance_km"))
    if total_rides is None and total_distance_km is None:
        return None
    return total_rides, total_distance_km


def _coerce_date(value: object) -> datetime_date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, datetime_date):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        candidate = raw.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(candidate).date()
        except Exception:
            pass
        try:
            return datetime_date.fromisoformat(raw)
        except Exception:
            return None
    return None


def _enrich_open_reminders_for_watch(
    open_reminders: list[dict[str, object]],
    latest_odometer_end_km: int | None,
) -> list[dict[str, object]]:
    today = datetime_date.today()
    enriched: list[dict[str, object]] = []

    for reminder in open_reminders:
        item = dict(reminder)
        due_km = _coerce_int(item.get("due_km"))
        due_date = _coerce_date(item.get("due_date"))

        km_until_due = None
        if due_km is not None and latest_odometer_end_km is not None:
            km_until_due = due_km - latest_odometer_end_km

        days_until_due = None
        if due_date is not None:
            days_until_due = (due_date - today).days

        overdue_by_km = km_until_due is not None and km_until_due < 0
        overdue_by_date = days_until_due is not None and days_until_due < 0
        is_overdue = overdue_by_km or overdue_by_date

        due_soon_by_km = km_until_due is not None and 0 <= km_until_due <= 1000
        due_soon_by_date = days_until_due is not None and 0 <= days_until_due <= 30
        is_due_soon = (not is_overdue) and (due_soon_by_km or due_soon_by_date)

        urgency = "safe"
        if is_overdue:
            urgency = "critical"
        elif is_due_soon:
            urgency = "warning"

        reasons: list[str] = []
        if overdue_by_km and km_until_due is not None:
            reasons.append(f"{abs(km_until_due)} km overdue")
        elif due_soon_by_km and km_until_due is not None:
            reasons.append(f"{km_until_due} km remaining")

        if overdue_by_date and days_until_due is not None:
            reasons.append(f"{abs(days_until_due)} days overdue")
        elif due_soon_by_date and days_until_due is not None:
            reasons.append(f"{days_until_due} days remaining")

        if not reasons:
            if due_km is not None:
                reasons.append(f"Due at {due_km} km")
            if due_date is not None:
                reasons.append(f"Due by {due_date.isoformat()}")

        item["km_until_due"] = km_until_due
        item["days_until_due"] = days_until_due
        item["is_overdue"] = is_overdue
        item["is_due_soon"] = is_due_soon
        item["urgency"] = urgency
        item["watch_reason"] = " · ".join(reasons) if reasons else "On track"
        enriched.append(item)

    return enriched


def _build_dashboard_tab_data(
    total_rides: int | None,
    total_distance_km: float | None,
) -> DashboardTabData:
    if total_rides is None and total_distance_km is None:
        return DashboardTabData(
            state="error",
            message="Dashboard metrics unavailable.",
        )
    if total_rides in (0, None):
        return DashboardTabData(
            state="empty",
            total_rides=total_rides or 0,
            total_distance_km=total_distance_km or 0.0,
            message="No ride history yet.",
        )
    return DashboardTabData(
        state="ready",
        total_rides=total_rides,
        total_distance_km=total_distance_km,
    )


def _parse_explicit_date(text: str) -> datetime_date | None:
    cleaned_text = text.strip()
    if not cleaned_text:
        return None

    for date_format in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(cleaned_text, date_format).date()
        except ValueError:
            continue

    return None


def parse_natural_date(text: str, *, today: datetime_date | None = None) -> datetime_date | None:
    """Parse a natural-language date into a concrete date when possible.

    Supports relative phrases like today, tomorrow, yesterday, next weekend,
    plus common explicit date formats.
    """
    today = today or datetime_date.today()
    cleaned_text = text.strip().lower()

    if not cleaned_text:
        return None

    if cleaned_text in {"today", "now"}:
        return today

    if cleaned_text == "tomorrow":
        return today + timedelta(days=1)

    if cleaned_text == "yesterday":
        return today - timedelta(days=1)

    if cleaned_text == "next weekend":
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        saturday = today + timedelta(days=days_until_saturday)
        return saturday

    explicit_date = _parse_explicit_date(text)
    if explicit_date:
        return explicit_date

    return None


def _parse_natural_date_range(text: str, *, today: datetime_date | None = None) -> tuple[str | None, str | None]:
    """Internal parser that returns a (start_date, end_date) tuple."""
    today = today or datetime_date.today()
    cleaned_text = text.strip()
    lowered_text = cleaned_text.lower()

    range_match = re.split(r"\s+(?:to|through|until|till)\s+", cleaned_text, maxsplit=1, flags=re.IGNORECASE)
    if len(range_match) == 2:
        start_text, end_text = range_match
        start_date = parse_natural_date(start_text, today=today)
        end_date = parse_natural_date(end_text, today=today)
        return (
            start_date.isoformat() if start_date else None,
            end_date.isoformat() if end_date else None,
        )

    if lowered_text == "next weekend":
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        saturday = today + timedelta(days=days_until_saturday)
        sunday = saturday + timedelta(days=1)
        return saturday.isoformat(), sunday.isoformat()

    parsed_date = parse_natural_date(cleaned_text, today=today)
    if parsed_date:
        iso_date = parsed_date.isoformat()
        return iso_date, iso_date

    return None, None


def parse_natural_date_range(text: str) -> dict:
        """Parse natural-language date text into tool-friendly structured output.

        Returns:
            {
                "status": "parsed" | "unparsed",
                "start_date": "YYYY-MM-DD" | None,
                "end_date": "YYYY-MM-DD" | None,
            }
        """
        start_date, end_date = _parse_natural_date_range(
                text,
                today=datetime.now(timezone.utc).date(),
        )
        return {
                "status": "parsed" if (start_date and end_date) else "unparsed",
                "start_date": start_date,
                "end_date": end_date,
        }


def insert_reminder(service_type: str, due_km: int, due_date: str) -> dict:
    """
    Logs a service reminder to the database after the user has approved it.
    Call this only when the user explicitly confirms with 'yes' or 'approve'.

    Args:
        service_type: The type of service e.g. 'chain_lubrication'
        due_km: The odometer reading at which this service is due
        due_date: The date the reminder is due in YYYY-MM-DD format

    Returns:
        A dict confirming the reminder was logged
    """
    connection_string = get_connection_string()

    with MongoClient(connection_string) as client:
        db = client["ride_agent_db"]
        result = db["service_reminders"].insert_one({
            "service_type": service_type,
            "due_km": due_km,
            "due_date": due_date,
            "status": "open"
        })

    return {"status": "logged", "inserted_id": str(result.inserted_id)}

def insert_ride_log(
    date: str | None = None,
    odometer_end_km: int | None = None,
    distance_km: int | None = None,
    route_type: str | None = None,
    avg_speed_kmh: int | None = None,
    fuel_used_liters: float | None = None,
    weather: str | None = None,
    notes: str | None = None,
) -> dict:
    """Logs a completed ride to the database with details about the trip.
    Insert will proceed even if some fields are missing; missing keys are written
    explicitly as null so downstream consumers see the same schema.

    Call this only when the user explicitly confirms with 'yes' or 'approve'.
    """
    connection_string = get_connection_string()

    # Normalize/validate inputs where possible, but allow missing fields.
    # Date: normalize natural language to an ISO date, defaulting to today if missing.
    if date:
        parsed_date, parsed_end_date = _parse_natural_date_range(
            date,
            today=datetime.now(timezone.utc).date(),
        )
        if parsed_end_date and parsed_end_date != parsed_date:
            return {
                "status": "error",
                "message": "Please provide a single ride date, not a date range.",
                "parsed_date": parsed_date,
                "parsed_end_date": parsed_end_date,
            }
        parsed_date = parsed_date or datetime.now(timezone.utc).date().isoformat()
    else:
        parsed_date = datetime.now(timezone.utc).date().isoformat()

    def _to_int(value):
        try:
            if value is None:
                return None
            return int(value)
        except Exception:
            return None

    def _to_float(value):
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    odometer_val = _to_int(odometer_end_km)
    distance_val = _to_int(distance_km)
    avg_speed_val = _to_int(avg_speed_kmh)
    fuel_val = _to_float(fuel_used_liters)

    # Ensure string fields are either a string or None
    route_type_val = route_type if isinstance(route_type, str) and route_type else None
    weather_val = weather if isinstance(weather, str) and weather else None
    notes_val = notes if isinstance(notes, str) and notes else None

    doc = {
        "date": parsed_date,
        "odometer_end_km": odometer_val,
        "distance_km": distance_val,
        "route_type": route_type_val,
        "avg_speed_kmh": avg_speed_val,
        "fuel_used_liters": fuel_val,
        "weather": weather_val,
        "notes": notes_val,
    }

    with MongoClient(connection_string) as client:
        db = client["ride_agent_db"]
        result = db["ride_logs"].insert_one(dict(doc))

    return {"status": "logged", "inserted_id": str(result.inserted_id), "doc": dict(doc)}


def get_rider_profile(user_id: str) -> dict:
    """
    Retrieves the rider profile from the database.

    Args:
        user_id: The unique identifier for the rider

    Returns:
        A dict containing the rider's profile information, or not_found
    """
    connection_string = get_connection_string()

    with MongoClient(connection_string) as client:
        db = client["ride_agent_db"]
        result = db["rider_profiles"].find_one(
            {"user_id": user_id},
            {"_id": 0}
        )

    return result if result else {"status": "not_found", "user_id": user_id}


def get_tab_data(user_id: str = "eval_user") -> dict:
    """Build the read-only tab payload used by the frontend."""

    connection_string = os.getenv("MDB_MCP_CONNECTION_STRING")
    if not connection_string:
        bundle = TabDataBundle(
            vehicle=VehicleTabData(
                state="empty",
                message="MongoDB is not configured.",
            ),
            reminders=RemindersTabData(
                state="empty",
                message="MongoDB is not configured.",
            ),
            trips=TripsTabData(
                state="empty",
                message="MongoDB is not configured.",
            ),
            profile=ProfileTabData(
                state="empty",
                user_id=user_id,
                message="MongoDB is not configured.",
            ),
            dashboard=DashboardTabData(
                state="empty",
                message="MongoDB is not configured.",
            ),
        )
        return bundle.model_dump(mode="json")

    with MongoClient(connection_string) as client:
        db = client["ride_agent_db"]

        latest_ride = (
            db["ride_logs"].find({}, {"_id": 0}).sort("date", DESCENDING).limit(1)
        )
        latest_ride_doc = next(latest_ride, None)

        open_reminders = list(
            db["service_reminders"]
            .find({"status": "open"}, {"_id": 0})
            .sort([("due_date", 1), ("due_km", 1)])
        )

        recent_rides = list(
            db["ride_logs"].find({}, {"_id": 0}).sort("date", DESCENDING).limit(5)
        )

        profile = db["rider_profiles"].find_one({"user_id": user_id}, {"_id": 0})

        dashboard_totals = None
        if not _bool_env("USE_PYTHON_FALLBACK"):
            dashboard_totals = _get_dashboard_totals_mcp()
        if dashboard_totals is None:
            dashboard_totals = _get_dashboard_totals_python(db)

    latest_odometer_end_km = None
    last_ride_date = None
    if latest_ride_doc:
        latest_odometer_end_km = latest_ride_doc.get("odometer_end_km")
        last_ride_date = latest_ride_doc.get("date")

    open_reminders = _enrich_open_reminders_for_watch(
        open_reminders=open_reminders,
        latest_odometer_end_km=_coerce_int(latest_odometer_end_km),
    )

    next_service_highlight = None
    if open_reminders:
        reminder = open_reminders[0]
        reminder_service_type = reminder.get("service_type") or "service"
        reminder_due_km = reminder.get("due_km")
        reminder_due_date = reminder.get("due_date")
        parts = [f"{reminder_service_type} due soon"]
        if reminder_due_km is not None:
            parts.append(f"at {reminder_due_km} km")
        if reminder_due_date:
            parts.append(f"by {reminder_due_date}")
        next_service_highlight = " ".join(parts)
    else:
        next_service_highlight = "No open service reminders."

    total_distance_km = 0
    total_fuel_liters = 0
    weather_values: list[str] = []
    for ride in recent_rides:
        distance_km = ride.get("distance_km")
        fuel_used_liters = ride.get("fuel_used_liters")
        weather = ride.get("weather")
        if isinstance(distance_km, (int, float)):
            total_distance_km += distance_km
        if isinstance(fuel_used_liters, (int, float)):
            total_fuel_liters += fuel_used_liters
        if isinstance(weather, str) and weather:
            weather_values.append(weather)

    weather_summary = None
    if weather_values:
        unique_weather = list(dict.fromkeys(weather_values))
        weather_summary = unique_weather[0] if len(unique_weather) == 1 else "Mixed recent weather"

    dashboard = None
    if dashboard_totals is not None:
        dashboard = _build_dashboard_tab_data(*dashboard_totals)

    bundle = TabDataBundle(
        vehicle=VehicleTabData(
            state="ready" if latest_ride_doc or open_reminders else "empty",
            latest_odometer_end_km=latest_odometer_end_km,
            last_ride_date=last_ride_date,
            next_service_highlight=next_service_highlight,
            message=None if (latest_ride_doc or open_reminders) else "No ride history or reminders found.",
        ),
        reminders=RemindersTabData(
            state="ready" if open_reminders else "empty",
            open_reminders=open_reminders,
            message=None if open_reminders else "No open service reminders.",
        ),
        trips=TripsTabData(
            state="ready" if recent_rides else "empty",
            recent_rides=recent_rides,
            totals={
                "ride_count": len(recent_rides),
                "distance_km": total_distance_km,
                "fuel_liters": total_fuel_liters,
            },
            weather_summary=weather_summary,
            message=None if recent_rides else "No recent rides found.",
        ),
        profile=ProfileTabData(
            state="ready" if profile else "empty",
            user_id=user_id,
            profile=profile or {},
            message=None if profile else f"No rider profile found for {user_id}.",
        ),
        dashboard=dashboard,
    )

    return bundle.model_dump(mode="json")

def update_rider_preferences(
    user_id: str,
    avoid_city: bool | None = None,
    avoid_highways: bool | None = None,
    prefer_curvy_roads: bool | None = None,
    prefer_countryside: bool | None = None,
    prefer_mountains: bool | None = None,
    avoid_heavy_rain: bool | None = None,
    avoid_strong_wind: bool | None = None,
    avoid_cold_below_c: int | None = None,
    max_heat_c: int | None = None,
    prefer_scenic_over_fastest: bool | None = None,
    likes_frequent_stops: bool | None = None,
    max_km_per_day: int | None = None,
    preferred_break_interval_km: int | None = None,
    comfortable_days_consecutive: int | None = None,
    wants_early_reminders: bool | None = None,
    reminder_lead_km: int | None = None,
    reminder_lead_days: int | None = None,
) -> dict:
    """
    Updates known rider preference fields without letting the model invent schema keys.
    Only provided fields are updated.

    Args:
        user_id: The rider identifier. For now use 'eval_user'.
        avoid_city: Whether the rider prefers to avoid city riding.
        avoid_highways: Whether the rider prefers to avoid highways.
        prefer_curvy_roads: Whether the rider prefers curvy roads.
        prefer_countryside: Whether the rider prefers countryside routes.
        prefer_mountains: Whether the rider prefers mountain routes.
        avoid_heavy_rain: Whether the rider prefers to avoid heavy rain.
        avoid_strong_wind: Whether the rider prefers to avoid strong wind.
        avoid_cold_below_c: Minimum comfortable temperature in Celsius.
        max_heat_c: Maximum comfortable temperature in Celsius.
        prefer_scenic_over_fastest: Whether scenic routes are preferred over fastest routes.
        likes_frequent_stops: Whether the rider prefers frequent stops.
        max_km_per_day: Maximum comfortable riding distance per day.
        preferred_break_interval_km: Preferred break interval in kilometers.
        comfortable_days_consecutive: Comfortable number of consecutive riding days.
        wants_early_reminders: Whether the rider wants maintenance reminders early.
        reminder_lead_km: How many km before due a reminder should be suggested.
        reminder_lead_days: How many days before due a reminder should be suggested.

    Returns:
        A dict confirming which fields were updated.
    """
    connection_string = get_connection_string()

    update_fields = {}

    field_map = {
        "preferences.route.avoid_city": avoid_city,
        "preferences.route.avoid_highways": avoid_highways,
        "preferences.route.prefer_curvy_roads": prefer_curvy_roads,
        "preferences.route.prefer_countryside": prefer_countryside,
        "preferences.route.prefer_mountains": prefer_mountains,
        "preferences.weather.avoid_heavy_rain": avoid_heavy_rain,
        "preferences.weather.avoid_strong_wind": avoid_strong_wind,
        "preferences.weather.avoid_cold_below_c": avoid_cold_below_c,
        "preferences.weather.max_heat_c": max_heat_c,
        "preferences.trip_style.prefer_scenic_over_fastest": prefer_scenic_over_fastest,
        "preferences.trip_style.likes_frequent_stops": likes_frequent_stops,
        "preferences.comfort_limits.max_km_per_day": max_km_per_day,
        "preferences.comfort_limits.preferred_break_interval_km": preferred_break_interval_km,
        "preferences.comfort_limits.comfortable_days_consecutive": comfortable_days_consecutive,
        "preferences.maintenance.wants_early_reminders": wants_early_reminders,
        "preferences.maintenance.reminder_lead_km": reminder_lead_km,
        "preferences.maintenance.reminder_lead_days": reminder_lead_days,
    }

    for mongo_field, value in field_map.items():
        if value is not None:
            update_fields[mongo_field] = value

    if not update_fields:
        return {
            "status": "no_update",
            "user_id": user_id,
            "message": "No preference fields were provided."
        }

    now = datetime.now(timezone.utc)

    with MongoClient(connection_string) as client:
        db = client["ride_agent_db"]
        result = db["rider_profiles"].update_one(
            {"user_id": user_id},
            {
                "$set": {
                    **update_fields,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "profile_version": 1,
                    "created_at": now,
                    "feedback_summary": {
                        "liked": [],
                        "disliked": []
                    }
                }
            },
            upsert=True
        )

    return {
        "status": "updated",
        "user_id": user_id,
        "updated_fields": list(update_fields.keys()),
        "matched_count": result.matched_count,
        "modified_count": result.modified_count,
        "upserted_id": str(result.upserted_id) if result.upserted_id else None,
    }


def get_weather_forecast(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    location_label: str,
) -> dict:
    """
    Retrieve forecast data for a candidate trip destination using Open-Meteo.

    Use this tool when evaluating destination candidates for a motorcycle trip.
    Provide latitude and longitude from the trip_candidates.weather_query field.
    Dates must be in YYYY-MM-DD format and must be within the forecast horizon.

    Args:
        latitude: Latitude of the destination candidate.
        longitude: Longitude of the destination candidate.
        start_date: Trip start date in YYYY-MM-DD format.
        end_date: Trip end date in YYYY-MM-DD format.
        location_label: Human-readable label for the destination, such as 'Lille,FR'.

    Returns:
        A dict with forecast summary information for the requested period.
    """
    try:
        start = datetime_date.fromisoformat(start_date)
        end = datetime_date.fromisoformat(end_date)
    except ValueError:
        return {
            "status": "error",
            "location_label": location_label,
            "message": "Dates must be in YYYY-MM-DD format.",
        }

    if end < start:
        return {
            "status": "error",
            "location_label": location_label,
            "message": "end_date must be on or after start_date.",
        }

    today = datetime.now(timezone.utc).date()

    if start < today:
        return {
            "status": "error",
            "location_label": location_label,
            "message": "Forecast API only supports today or future dates.",
        }

    max_forecast_date = today + timedelta(days=15)
    if end > max_forecast_date:
        return {
            "status": "error",
            "location_label": location_label,
            "message": f"Forecast API supports up to 16 days ahead. Latest allowed end_date is {max_forecast_date.isoformat()}.",
        }

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_hours",
            "wind_speed_10m_max",
            "weather_code",
        ],
        "timezone": "auto",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        daily = data.get("daily", {})
        times = daily.get("time", [])
        temp_max = daily.get("temperature_2m_max", [])
        temp_min = daily.get("temperature_2m_min", [])
        rain_sum = daily.get("precipitation_sum", [])
        rain_hours = daily.get("precipitation_hours", [])
        wind_max = daily.get("wind_speed_10m_max", [])
        weather_codes = daily.get("weather_code", [])

        if not times:
            return {
                "status": "error",
                "location_label": location_label,
                "message": "No forecast data returned for the requested dates.",
            }

        day_count = len(times)
        avg_temp_max = sum(temp_max) / len(temp_max) if temp_max else None
        avg_temp_min = sum(temp_min) / len(temp_min) if temp_min else None
        total_precipitation_mm = sum(rain_sum) if rain_sum else None
        total_precipitation_hours = sum(rain_hours) if rain_hours else None
        max_wind_kmh = max(wind_max) if wind_max else None

        return {
            "status": "success",
            "location_label": location_label,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "day_count": day_count,
            "avg_temp_max_c": avg_temp_max,
            "avg_temp_min_c": avg_temp_min,
            "total_precipitation_mm": total_precipitation_mm,
            "total_precipitation_hours": total_precipitation_hours,
            "max_wind_kmh": max_wind_kmh,
            "weather_codes": weather_codes,
            "raw_daily": daily,
        }

    except requests.exceptions.HTTPError:
        error_message = None
        try:
            error_payload = response.json()
            error_message = error_payload.get("reason")
        except Exception:
            error_message = response.text

        return {
            "status": "error",
            "location_label": location_label,
            "message": f"Weather API request failed: {error_message}",
        }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "location_label": location_label,
            "message": "Weather API request timed out.",
        }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "location_label": location_label,
            "message": f"Weather API request failed: {str(e)}",
        }