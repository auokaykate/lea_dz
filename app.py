from flask import Flask, request


def create_app():
    app = Flask(__name__)

    # sensor_id -> the latest accepted reading, exactly as the client sent it.
    latest_by_sensor = {}

    @app.post("/readings")
    def add_reading():
        reading = request.get_json()
        latest_by_sensor[reading["sensor_id"]] = reading
        return {"status": "accepted"}, 201

    # "path" (not the default "string") lets sensor_id contain "/".
    @app.get("/sensors/<path:sensor_id>/latest")
    def get_latest(sensor_id):
        reading = latest_by_sensor.get(sensor_id)
        if reading is None:
            return {"error": f"no readings for sensor '{sensor_id}'"}, 404
        return reading, 200

    return app
