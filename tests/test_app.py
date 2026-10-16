import json

import pytest

from app import create_app


@pytest.fixture
def client():
    # A new app for every test, so tests never share stored readings.
    return create_app().test_client()


def make_reading(**changes):
    reading = {
        "event_id": "event-001",
        "sensor_id": "room-01-temperature",
        "value": 22.4,
        "observed_at": "2026-10-12T10:00:00Z",
    }
    reading.update(changes)
    return reading


def body_with_raw_value(raw_value):
    # JSON text of a valid reading with "value" written as raw JSON text,
    # for values that json.dumps cannot produce (NaN, 1e400, huge integers).
    return json.dumps(make_reading(value="RAW")).replace('"RAW"', raw_value)


def assert_rejected(client, response):
    assert response.status_code == 422
    assert "error" in response.get_json()
    # Nothing from a rejected request may be stored.
    assert client.get("/sensors/room-01-temperature/latest").status_code == 404


# Accepting and reading


def test_new_reading_is_accepted_and_returned_as_latest(client):
    response = client.post("/readings", json=make_reading())
    assert response.status_code == 201
    assert response.get_json() == {"status": "accepted"}

    response = client.get("/sensors/room-01-temperature/latest")
    assert response.status_code == 200
    assert response.get_json() == make_reading()


@pytest.mark.parametrize(
    "readings_before",
    [[], [make_reading(sensor_id="room-02-temperature")]],
    ids=["empty-service", "other-sensor-only"],
)
def test_latest_is_404_when_sensor_has_no_readings(client, readings_before):
    for reading in readings_before:
        assert client.post("/readings", json=reading).status_code == 201

    response = client.get("/sensors/room-01-temperature/latest")
    assert response.status_code == 404
    assert "error" in response.get_json()


def test_sensor_id_with_slash_can_be_read_back(client):
    assert client.post("/readings", json=make_reading(sensor_id="room/01")).status_code == 201

    response = client.get("/sensors/room/01/latest")
    assert response.status_code == 200
    assert response.get_json() == make_reading(sensor_id="room/01")


# Validation: every invalid request gets 422 and stores nothing


@pytest.mark.parametrize(
    "raw_body",
    ["not json", "", "[1, 2]", "null", '"text"', "5"],
    ids=["not-json", "empty", "list", "null", "string", "number"],
)
def test_body_must_be_a_json_object(client, raw_body):
    response = client.post("/readings", data=raw_body, content_type="application/json")
    assert_rejected(client, response)


def test_body_without_content_type_is_accepted(client):
    response = client.post("/readings", data=json.dumps(make_reading()))
    assert response.status_code == 201


@pytest.mark.parametrize("field", ["event_id", "sensor_id", "value", "observed_at"])
def test_missing_field_is_rejected(client, field):
    reading = make_reading()
    del reading[field]
    assert_rejected(client, client.post("/readings", json=reading))


def test_unknown_field_is_rejected(client):
    assert_rejected(client, client.post("/readings", json=make_reading(unit="C")))


@pytest.mark.parametrize("field", ["event_id", "sensor_id"])
@pytest.mark.parametrize("bad_value", ["", 123, None])
def test_ids_must_be_non_empty_strings(client, field, bad_value):
    reading = make_reading()
    reading[field] = bad_value
    assert_rejected(client, client.post("/readings", json=reading))


def test_whitespace_only_id_is_accepted(client):
    # "Non-empty string" is read literally: only "" is rejected.
    response = client.post("/readings", json=make_reading(event_id="   "))
    assert response.status_code == 201


@pytest.mark.parametrize(
    "raw_value",
    [
        '"22.4"',
        "true",
        "false",
        "null",
        "NaN",
        "Infinity",
        "-Infinity",
        "1e400",
        pytest.param("1" + "0" * 400, id="1-and-400-zeros"),
        pytest.param("1" + "0" * 5000, id="1-and-5000-zeros"),
    ],
)
def test_value_must_be_a_finite_number(client, raw_value):
    response = client.post(
        "/readings", data=body_with_raw_value(raw_value), content_type="application/json"
    )
    assert_rejected(client, response)


@pytest.mark.parametrize("value", [0, -5, 22, 22.4])
def test_valid_values_are_accepted(client, value):
    assert client.post("/readings", json=make_reading(value=value)).status_code == 201


@pytest.mark.parametrize(
    "observed_at",
    [
        "2026-10-12T10:00:00Z",
        "2026-10-12T10:00:00.5Z",
        "2026-10-12T10:00:00.000Z",
        "2026-10-12T10:00:00.123456Z",
    ],
)
def test_valid_observed_at_is_accepted(client, observed_at):
    response = client.post("/readings", json=make_reading(observed_at=observed_at))
    assert response.status_code == 201


@pytest.mark.parametrize(
    "observed_at",
    [
        "2026-10-12T10:00:00+00:00",  # offset instead of Z
        "2026-10-12T10:00:00",  # no time zone
        "2026-10-12",  # date only
        "2026-10-12T10:00:00z",  # lowercase z
        "2026-10-12 10:00:00Z",  # space instead of T
        "2026-10-12T10:00Z",  # no seconds
        "20261012T100000Z",  # ISO basic format
        "2026-10-12T10:00:00.1234567Z",  # more than 6 fractional digits
        "2026-10-12T10:00:00.Z",  # dot without digits
        "2026-02-30T10:00:00Z",  # no such day
        "2026-10-12T25:00:00Z",  # no such hour
        "2026-12-31T23:59:60Z",  # leap second, datetime cannot store it
        pytest.param("", id="empty"),
        pytest.param("2026-10-12T10:00:00Z\n", id="trailing-newline"),
        pytest.param("٢٠٢٦-10-12T10:00:00Z", id="non-ascii-digits"),
        pytest.param(1760263200, id="number"),
    ],
)
def test_invalid_observed_at_is_rejected(client, observed_at):
    response = client.post("/readings", json=make_reading(observed_at=observed_at))
    assert_rejected(client, response)


def test_rejected_reading_does_not_reserve_event_id(client):
    assert_rejected(client, client.post("/readings", json=make_reading(value="bad")))
    # The same event_id with valid data is new: not a duplicate, not a conflict.
    assert client.post("/readings", json=make_reading()).status_code == 201
