import json
import math
import re
import threading
from datetime import datetime

from flask import Flask, request

REQUIRED_FIELDS = {"event_id", "sensor_id", "value", "observed_at"}

# YYYY-MM-DDTHH:MM:SS, optional 1-6 fractional digits, then Z.
# [0-9] instead of \d, because \d also matches non-ASCII digits (e.g. Arabic-Indic digits).
OBSERVED_AT_FORMAT = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?Z"
)


def parse_json_body(raw_body):
    """Return the parsed JSON body, or None if it is not valid JSON."""
    try:
        return json.loads(raw_body)
    # ValueError: broken JSON, bad encoding, an integer longer than 4300 digits.
    # RecursionError: very deeply nested JSON such as [[[[...]]]].
    except (ValueError, RecursionError):
        return None


def validate_reading(body):
    """Return an error message if the reading is invalid, otherwise None."""
    if not isinstance(body, dict):
        return "request body must be a valid JSON object"

    missing = REQUIRED_FIELDS - body.keys()
    if missing:
        return f"missing fields: {', '.join(sorted(missing))}"
    unknown = body.keys() - REQUIRED_FIELDS
    if unknown:
        return f"unknown fields: {', '.join(sorted(unknown))}"

    for field in ("event_id", "sensor_id"):
        if not isinstance(body[field], str) or body[field] == "":
            return f"{field} must be a non-empty string"

    value = body["value"]
    # bool is a subclass of int in Python, so it must be rejected explicitly.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "value must be a number"
    try:
        is_finite = math.isfinite(value)
    except OverflowError:  # an int too large for a float, e.g. 10**400
        is_finite = False
    if not is_finite:
        return "value must be a finite number"

    observed_at = body["observed_at"]
    if not isinstance(observed_at, str) or not OBSERVED_AT_FORMAT.fullmatch(observed_at):
        return "observed_at must be a UTC time like 2026-10-12T10:00:00Z (at most 6 fractional digits)"
    try:
        datetime.fromisoformat(observed_at)
    except ValueError:  # matches the format, but no such date or time, e.g. February 30
        return "observed_at is not a valid date and time"

    return None


def observed_moment(reading):
    """observed_at of a valid reading as a datetime, so it compares as a moment, not as text."""
    return datetime.fromisoformat(reading["observed_at"])


def same_reading(a, b):
    """True if two valid readings with the same event_id carry the same data."""
    return (
        a["sensor_id"] == b["sensor_id"]
        # 22 == 22.0 is True in Python.
        and a["value"] == b["value"]
        # "10:00:00Z" and "10:00:00.000Z" are the same moment.
        and observed_moment(a) == observed_moment(b)
    )


def create_app():
    app = Flask(__name__)

    # event_id -> every accepted reading, kept to recognise repeats.
    readings_by_event = {}
    # sensor_id -> the reading with the latest observed_at, exactly as the client sent it.
    latest_by_sensor = {}
    # The dev server runs requests in threads. The lock makes "look up event_id,
    # then store" one step, so two requests cannot both see the event_id as new.
    lock = threading.Lock()

    @app.post("/readings")
    def add_reading():
        # The Content-Type header is ignored: any body is parsed as JSON.
        body = parse_json_body(request.get_data())
        error = validate_reading(body)
        if error is not None:
            return {"error": error}, 422

        with lock:
            stored = readings_by_event.get(body["event_id"])
            if stored is not None:
                if same_reading(stored, body):
                    return {"status": "duplicate"}, 200
                return {"error": f"event_id '{body['event_id']}' already exists with different data"}, 409

            readings_by_event[body["event_id"]] = body
            current = latest_by_sensor.get(body["sensor_id"])
            # Strictly later only: with equal observed_at the reading accepted first stays.
            if current is None or observed_moment(body) > observed_moment(current):
                latest_by_sensor[body["sensor_id"]] = body
        return {"status": "accepted"}, 201

    # "path" (not the default "string") lets sensor_id contain "/".
    @app.get("/sensors/<path:sensor_id>/latest")
    def get_latest(sensor_id):
        reading = latest_by_sensor.get(sensor_id)
        if reading is None:
            return {"error": f"no readings for sensor '{sensor_id}'"}, 404
        return reading, 200

    return app
