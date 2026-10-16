# Sensor readings service

A small HTTP service that accepts readings from room sensors and returns the latest
reading of each sensor. Python + Flask; the data is kept in the memory of one process.
This is a homework task on synthetic data.

## Requirements

- Python 3.11 or newer. The code needs `datetime.fromisoformat` to understand the `Z`
  suffix, which was added in Python 3.11.
- Tests pass on Windows 10 (Python 3.14) and Linux (WSL, Python 3.12). The manual curl
  check was done on Windows.
- Dependencies (pinned in `requirements.txt`): Flask 3.1.3, pytest 9.1.1.

## Install

Linux / macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

On Debian/Ubuntu, `python3 -m venv` needs the `python3-venv` package.

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

All commands in this README call the Python of the virtual environment directly, so the
environment does not need to be activated.

## Run the service

Linux / macOS:

```bash
.venv/bin/flask --app app run
```

Windows (PowerShell):

```powershell
.venv\Scripts\flask --app app run
```

The service listens on `http://127.0.0.1:5000`. If port 5000 is busy (on macOS the
AirPlay Receiver often uses it), add `--port 5001`. Stop the service with Ctrl+C.
This is Flask's development server; the task does not need a deployment.

## Run the tests

Linux / macOS:

```bash
.venv/bin/python -m pytest
```

Windows (PowerShell):

```powershell
.venv\Scripts\python -m pytest
```

Expected result: `75 passed`.

## API

### POST /readings

Accepts one reading:

```json
{
  "event_id": "event-001",
  "sensor_id": "room-01-temperature",
  "value": 22.4,
  "observed_at": "2026-10-12T10:00:00Z"
}
```

| Situation | Status | Body |
|---|---|---|
| New `event_id` | 201 | `{"status": "accepted"}` |
| Known `event_id`, same `sensor_id`, `value` and `observed_at` | 200 | `{"status": "duplicate"}` |
| Known `event_id`, different data | 409 | `{"error": "..."}` |
| Invalid request | 422 | `{"error": "..."}` |

### GET /sensors/{sensor_id}/latest

Returns 200 and the latest reading of the sensor, or 404 and `{"error": "..."}` if the
sensor has no readings.

### Rules and decisions

Where the task leaves room for interpretation, these choices were made.

Validation (every invalid request gets 422 and changes nothing):

- All four fields are required; unknown fields are rejected.
- `event_id` and `sensor_id` must be non-empty strings. Only `""` is rejected; a string
  of spaces is accepted, because the task only says "non-empty".
- `value` must be a JSON number (not a string, not a boolean) and finite. It also has to
  fit in a 64-bit float: `NaN`, `Infinity`, `1e400` and an integer such as 1 followed by
  400 zeros are rejected.
- `observed_at` must look like `YYYY-MM-DDTHH:MM:SS`, with an optional fraction of 1 to 6
  digits and an uppercase `Z`, and it must be a real date and time. Rejected, for example:
  `+00:00` instead of `Z`, no time zone, lowercase `z`, no seconds, February 30.
- The body is parsed as JSON whatever the `Content-Type` header says. A body that is not
  valid JSON, or is valid JSON but not an object, gets 422.
- The error message describes the first problem found.
- Validation runs before the duplicate check, so an invalid repeat of a known `event_id`
  gets 422, not 409.

Duplicates and conflicts:

- `event_id` is unique across the whole service, not per sensor.
- `value` is compared as a number (`22` equals `22.0`); `observed_at` is compared as a
  moment (`10:00:00Z` equals `10:00:00.000Z`).

Latest reading:

- Chosen by `observed_at`, not by arrival time. A reading replaces the latest one only if
  its `observed_at` is strictly later, so with equal `observed_at` the reading accepted
  first stays.
- Older readings are stored too, so their repeats are still recognised (200 or 409).
- GET returns the reading exactly as it was sent in the accepted request (`22` stays `22`,
  `.000Z` stays `.000Z`). Flask sorts the JSON keys alphabetically.
- `sensor_id` may contain `/`: a reading for `room/01` is read back with
  `GET /sensors/room/01/latest`.

Flask's development server handles requests in threads, so a lock makes "look up the
`event_id`, then store" one step.

## Examples

Start the service, then run these commands in another terminal with bash (Linux, macOS,
WSL or Git Bash on Windows). `-w '%{http_code}\n'` prints the status code after the body.
The lines starting with `#` after a command show its real output.

The five steps from the task:

```bash
# Step 1: new reading -> 201
curl -s -w '%{http_code}\n' http://127.0.0.1:5000/readings -H 'Content-Type: application/json' \
  -d '{"event_id": "event-001", "sensor_id": "room-01-temperature", "value": 22.4, "observed_at": "2026-10-12T10:00:00Z"}'
# {"status":"accepted"}
# 201

curl -s -w '%{http_code}\n' http://127.0.0.1:5000/sensors/room-01-temperature/latest
# {"event_id":"event-001","observed_at":"2026-10-12T10:00:00Z","sensor_id":"room-01-temperature","value":22.4}
# 200

# Step 2: exact repeat of event-001 -> 200, latest does not change
curl -s -w '%{http_code}\n' http://127.0.0.1:5000/readings -H 'Content-Type: application/json' \
  -d '{"event_id": "event-001", "sensor_id": "room-01-temperature", "value": 22.4, "observed_at": "2026-10-12T10:00:00Z"}'
# {"status":"duplicate"}
# 200

# Step 3: older reading event-002 -> 201, latest is still event-001
curl -s -w '%{http_code}\n' http://127.0.0.1:5000/readings -H 'Content-Type: application/json' \
  -d '{"event_id": "event-002", "sensor_id": "room-01-temperature", "value": 21.8, "observed_at": "2026-10-12T09:59:00Z"}'
# {"status":"accepted"}
# 201

# Step 4: event-001 with another value -> 409, latest does not change
curl -s -w '%{http_code}\n' http://127.0.0.1:5000/readings -H 'Content-Type: application/json' \
  -d '{"event_id": "event-001", "sensor_id": "room-01-temperature", "value": 25.0, "observed_at": "2026-10-12T10:00:00Z"}'
# {"error":"event_id 'event-001' already exists with different data"}
# 409

curl -s -w '%{http_code}\n' http://127.0.0.1:5000/sensors/room-01-temperature/latest
# {"event_id":"event-001","observed_at":"2026-10-12T10:00:00Z","sensor_id":"room-01-temperature","value":22.4}
# 200

# Step 5: newer reading event-003 -> 201, latest is event-003
curl -s -w '%{http_code}\n' http://127.0.0.1:5000/readings -H 'Content-Type: application/json' \
  -d '{"event_id": "event-003", "sensor_id": "room-01-temperature", "value": 23.0, "observed_at": "2026-10-12T10:01:00Z"}'
# {"status":"accepted"}
# 201

curl -s -w '%{http_code}\n' http://127.0.0.1:5000/sensors/room-01-temperature/latest
# {"event_id":"event-003","observed_at":"2026-10-12T10:01:00Z","sensor_id":"room-01-temperature","value":23.0}
# 200
```

Errors:

```bash
# Boolean value -> 422
curl -s -w '%{http_code}\n' http://127.0.0.1:5000/readings -H 'Content-Type: application/json' \
  -d '{"event_id": "event-004", "sensor_id": "room-01-temperature", "value": true, "observed_at": "2026-10-12T10:02:00Z"}'
# {"error":"value must be a number"}
# 422

# Unknown field -> 422
curl -s -w '%{http_code}\n' http://127.0.0.1:5000/readings -H 'Content-Type: application/json' \
  -d '{"event_id": "event-004", "sensor_id": "room-01-temperature", "value": 23.5, "observed_at": "2026-10-12T10:02:00Z", "unit": "C"}'
# {"error":"unknown fields: unit"}
# 422

# Broken JSON -> 422
curl -s -w '%{http_code}\n' http://127.0.0.1:5000/readings -H 'Content-Type: application/json' \
  -d '{"event_id": "event-004",'
# {"error":"request body must be a valid JSON object"}
# 422

# Sensor without readings -> 404
curl -s -w '%{http_code}\n' http://127.0.0.1:5000/sensors/room-99-humidity/latest
# {"error":"no readings for sensor 'room-99-humidity'"}
# 404
```

In Windows PowerShell 5.1, `curl` is an alias of `Invoke-WebRequest`, so the commands
above do not work there. Use Git Bash or WSL, or `Invoke-RestMethod`:

```powershell
$body = '{"event_id": "event-001", "sensor_id": "room-01-temperature", "value": 22.4, "observed_at": "2026-10-12T10:00:00Z"}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/readings -ContentType 'application/json' -Body $body | ConvertTo-Json -Compress
# {"status":"accepted"}
Invoke-RestMethod -Uri http://127.0.0.1:5000/sensors/room-01-temperature/latest | ConvertTo-Json -Compress
# {"event_id":"event-001","observed_at":"2026-10-12T10:00:00Z","sensor_id":"room-01-temperature","value":22.4}
```

## Project layout

- `app.py`: JSON parsing, validation (`validate_reading`), in-memory storage and the two
  routes.
- `tests/test_app.py`: 75 test cases (pytest and Flask's test client), including the
  five-step example from the task as one test.
- `requirements.txt`, `pytest.ini` (lets the tests import `app.py`).
- `AI_LOG.md`: step-by-step log of how AI was used.

Flask was chosen so that every validation rule is plain code in one function. With
FastAPI and Pydantic, the default behaviour (for example, turning the string `"22.4"`
into a number, or accepting many date formats) would need extra configuration to match
the task.

## Time spent

Time spent: about 3 hours.

## Not done and limitations

Everything the task asks for is implemented. Known limitations:

- The data lives in the memory of one process and is lost on restart (allowed by the
  task). With several worker processes (for example `gunicorn -w 4`) each process would
  have its own data, and GET could return 404 for a reading that another process accepted.
- Every accepted reading is kept forever, because repeats of any `event_id` must be
  recognised. Memory use grows without a limit.
- The lock works only inside one process. It is not covered by tests: a race between
  threads is hard to reproduce reliably.
- `observed_at` may have at most 6 fractional digits, because Python's `datetime` stores
  microseconds. More digits get 422 instead of being cut silently. A leap second
  (`23:59:60Z`) gets 422 because `datetime` cannot store it.
- `value` must fit in a 64-bit float, so an integer such as 1 followed by 400 zeros gets
  422 although it is finite. Numbers that are equal as 64-bit floats are treated as the
  same value.
- Future dates are not checked (as the task says). A reading with a wrong future
  `observed_at` becomes the latest one and cannot be replaced by correct readings.
- Only the first validation problem is reported.
- If a JSON body has the same key twice, the last one is used (Python's `json` module).
- The request body size is not limited.
- Unknown URLs and wrong methods (for example `GET /readings` or `/sensors//latest`) get
  Flask's default HTML 404 and 405 pages, not JSON.
- Only Flask's development server is used; there is no production setup (not required).

## Use of AI

I used two AI assistants:

- Claude Code (model Claude Opus 5.5) wrote the tests and the code with me, step by step.
- A second assistant, Claude in a chat, worked as a reviewer. I showed it the plan and the
  result of every step and discussed with it what to accept and what to ask for next.

The decisions were mine, but I did not always find the problems myself: several of my
requests and corrections came out of the discussion with the reviewer. The full
step-by-step log is in `AI_LOG.md`.

What I used Claude Code for:

- reading the task, making a plan and listing the points where the task allows two
  readings. The decisions on these points were mine (see "Rules and decisions");
- a table of 45 edge cases with expected responses, before any tests were written;
- writing the tests and the code step by step, with an explanation of every line;
- small Python experiments to confirm the traps before writing code: `bool` is a subclass
  of `int`, `json` accepts `NaN` and turns `1e400` into infinity, `fromisoformat` accepts
  more formats than the task allows, `math.isfinite` fails on huge integers;
- the manual check with curl and a draft of this README.

How I worked and checked the result:

- Tests before code. For each step the tests were written first and run to show that they
  fail, then the code was written until they passed. Each step is a separate commit.
- Mutation checks. After each step one rule at a time was broken in a copy of the code
  (for example: no `bool` check, `observed_at` compared as strings, `>` changed to `>=`)
  to see which tests fail. This also showed what the tests do not catch: the lock, and
  two details of the `observed_at` regular expression that `datetime.fromisoformat`
  rejects anyway.
- Fresh clone. The repository was cloned into an empty folder, installed from
  `requirements.txt` into a new virtual environment, and all 75 tests passed (Windows,
  Python 3.14).
- My own Linux run: WSL, Python 3.12.3, a clean virtual environment in `/tmp`,
  `pip install -r requirements.txt`, `pytest -q`: 75 passed.
- Manual check: the service was started and the five steps from the task plus several
  errors were sent with curl (Windows). The responses matched the task.
- I read the explanation of every step and checked the test results myself before
  accepting it.

Additions and corrections that came out of the review discussion. I decided on each of
them, but I did not always notice the problem first.

Requests to Claude Code:

- a test with an integer `value` of 1 followed by 400 zeros (it caused a 500 before the
  fix);
- an integer longer than 4300 digits tested through `POST /readings`, not only through
  `json.loads`;
- all checks in one `validate_reading` function;
- similar test cases grouped with `pytest.mark.parametrize`.

Mistakes of Claude Code found in the review:

- It said that the non-ASCII digits in one test were written as escape sequences, but
  the file contained the real characters. Fixed: all files are ASCII only now.
- It recorded my first test run from WSL as a Linux check, but that run used the Windows
  Python from `.venv/Scripts`. I then ran the tests on real Linux (see above).

Mistakes Claude Code found itself:

- Its first mutation-check script never applied the changes (wrong path), so the first
  results meant nothing. It noticed this and ran the check again.
- A very deeply nested JSON body (`[[[...]]]`) returned 500 instead of 422. Fixed in a
  separate commit with a test.
- The escape-sequence problem happened once more, in `AI_LOG.md`, and was fixed the same
  way.
