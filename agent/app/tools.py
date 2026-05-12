import os
from pymongo import MongoClient

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
    client = MongoClient(CONNECTION_STRING)
    db = client["ride_agent_db"]
    result = db["service_reminders"].insert_one({
        "service_type": service_type,
        "due_km": due_km,
        "due_date": due_date,
        "status": "open"
    })
    client.close()
    return {"status": "logged", "inserted_id": str(result.inserted_id)}