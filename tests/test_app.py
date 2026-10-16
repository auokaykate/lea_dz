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
