import math
import re
from datetime import datetime

from flask import Flask, request

REQUIRED_FIELDS = {"event_id", "sensor_id", "value", "observed_at"}

# YYYY-MM-DDTHH:MM:SS, optional 1-6 fractional digits, then Z.
# [0-9] instead of \d, because \d also matches non-ASCII digits (e.g. Arabic-Indic digits).
OBSERVED_AT_FORMAT = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?Z"
)


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


def create_app():
    app = Flask(__name__)

    # sensor_id -> the latest accepted reading, exactly as the client sent it.
    latest_by_sensor = {}

    @app.post("/readings")
    def add_reading():
        # force: parse the body as JSON even without a Content-Type header.
        # silent: return None instead of an HTTP 400 error if parsing fails.
        body = request.get_json(force=True, silent=True)
        error = validate_reading(body)
        if error is not None:
            return {"error": error}, 422

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
