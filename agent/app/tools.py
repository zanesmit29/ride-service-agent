import os
from pymongo import MongoClient
from datetime import datetime, timezone

CONNECTION_STRING = os.getenv("MDB_MCP_CONNECTION_STRING")


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
    if not CONNECTION_STRING:
        raise ValueError("MDB_MCP_CONNECTION_STRING is not set")

    with MongoClient(CONNECTION_STRING) as client:
        db = client["ride_agent_db"]
        result = db["service_reminders"].insert_one({
            "service_type": service_type,
            "due_km": due_km,
            "due_date": due_date,
            "status": "open"
        })

    return {"status": "logged", "inserted_id": str(result.inserted_id)}


def get_rider_profile(user_id: str) -> dict:
    """
    Retrieves the rider profile from the database.

    Args:
        user_id: The unique identifier for the rider

    Returns:
        A dict containing the rider's profile information, or not_found
    """
    if not CONNECTION_STRING:
        raise ValueError("MDB_MCP_CONNECTION_STRING is not set")

    with MongoClient(CONNECTION_STRING) as client:
        db = client["ride_agent_db"]
        result = db["rider_profiles"].find_one(
            {"user_id": user_id},
            {"_id": 0}
        )

    return result if result else {"status": "not_found", "user_id": user_id}

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
    if not CONNECTION_STRING:
        raise ValueError("MDB_MCP_CONNECTION_STRING is not set")

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

    with MongoClient(CONNECTION_STRING) as client:
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