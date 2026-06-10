from app.tools import _build_service_watch_items_from_intervals, _enrich_open_reminders_for_watch


def test_tyre_pressure_uses_days_only_when_interval_km_zero() -> None:
    service_intervals = [
        {
            "service_type": "tyre_pressure_check",
            "interval_km": 0,
            "interval_days": 14,
            "last_done_km": 38108,
            "last_done_date": "2026-05-20",
        }
    ]

    items = _build_service_watch_items_from_intervals(service_intervals, open_reminders=[])

    assert len(items) == 1
    item = items[0]
    assert item["service_type"] == "tyre_pressure_check"
    assert "due_km" not in item
    assert item["due_date"] == "2026-06-03"


def test_brake_fluid_prefers_months_over_days() -> None:
    service_intervals = [
        {
            "service_type": "brake_fluid_check",
            "interval_km": 0,
            "interval_days": 14,
            "interval_months": 12,
            "last_done_km": 34000,
            "last_done_date": "2026-03-01",
        }
    ]

    items = _build_service_watch_items_from_intervals(service_intervals, open_reminders=[])

    assert len(items) == 1
    item = items[0]
    assert "due_km" not in item
    assert item["due_date"] == "2027-03-01"


def test_air_filter_uses_km_only_when_no_time_interval() -> None:
    service_intervals = [
        {
            "service_type": "air_filter_check",
            "interval_km": 10000,
            "last_done_km": 30000,
            "last_done_date": "2025-05-15",
        }
    ]

    items = _build_service_watch_items_from_intervals(service_intervals, open_reminders=[])

    assert len(items) == 1
    item = items[0]
    assert item["due_km"] == 40000
    assert "due_date" not in item


def test_reminder_metadata_does_not_override_computed_due_values() -> None:
    service_intervals = [
        {
            "service_type": "air_filter_check",
            "interval_km": 10000,
            "last_done_km": 30000,
            "last_done_date": "2025-05-15",
        }
    ]
    reminders = [
        {
            "service_type": "air_filter_check",
            "due_km": 39000,
            "due_date": "2026-05-16",
            "status": "open",
        }
    ]

    items = _build_service_watch_items_from_intervals(service_intervals, open_reminders=reminders)

    assert len(items) == 1
    item = items[0]
    assert item["due_km"] == 40000
    assert item["has_open_reminder"] is True
    assert item["reminder_due_km"] == 39000


def test_enrich_shows_km_delta_even_when_not_due_soon() -> None:
    reminders = [{"service_type": "air_filter_check", "due_km": 40000}]

    enriched = _enrich_open_reminders_for_watch(reminders, latest_odometer_end_km=38420)

    assert len(enriched) == 1
    item = enriched[0]
    assert item["is_overdue"] is False
    assert item["is_due_soon"] is False
    assert item["watch_reason"] == "1580 km remaining"


def test_enrich_shows_days_delta_even_when_not_due_soon() -> None:
    reminders = [{"service_type": "brake_fluid_check", "due_date": "2027-03-01"}]

    enriched = _enrich_open_reminders_for_watch(reminders, latest_odometer_end_km=None)

    assert len(enriched) == 1
    item = enriched[0]
    assert item["is_overdue"] is False
    assert item["is_due_soon"] is False
    assert "days remaining" in str(item["watch_reason"])
