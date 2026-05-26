import os
from pymongo import MongoClient
from datetime import datetime, timezone, date, timedelta
import requests


def get_connection_string() -> str:
    connection_string = os.getenv("MDB_MCP_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("MDB_MCP_CONNECTION_STRING is not set")
    return connection_string


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
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
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