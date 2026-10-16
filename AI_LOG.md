# AI usage log

Short log of how an AI assistant (Claude Code, model Claude Opus 5.5) was used.
Each entry: what I asked for, what the assistant did, how the result was checked.

## 2026-10-16 - Planning

- Asked: read the task, propose a step-by-step plan and list ambiguous points. No code yet.
- Done: plan of 10 steps (setup, edge-case table, 4 test-first feature steps, manual check,
  interview practice, README). 7 questions about ambiguous points, each with a recommendation.
- My decisions: strict `observed_at` format (`YYYY-MM-DDTHH:MM:SS[.fraction]Z`), at most
  6 fractional digits, "non-empty string" read literally (only `""` is rejected),
  any invalid body (bad JSON, not an object) returns 422, GET returns the reading as it was
  sent, a lock around "check + write", `path` converter so any `sensor_id` can be read back.
- I added an edge case myself: a very large integer `value` (1 followed by 400 zeros).
- Checked: ran small Python snippets to confirm the traps before writing code:
  `isinstance(True, int)` is `True`; `json.loads` accepts `NaN`, `Infinity` and turns `1e400`
  into `inf`; `datetime.fromisoformat` accepts formats without `Z` (`+00:00`, date only) and
  silently drops fractional digits after the 6th; `math.isfinite(10**400)` raises
  `OverflowError`; `json.loads` refuses integers longer than 4300 digits (`ValueError`).

## 2026-10-16 - Step 0: project setup

- Asked: set up the repository.
- Done: git repo, `.gitignore`, virtual environment, `requirements.txt` with pinned
  Flask 3.1.3 and pytest 9.1.1.
- Checked: installed `requirements.txt` into a second, clean virtual environment (exit 0,
  same versions); `import flask` works; `pytest` starts and reports "no tests ran" as expected.

## 2026-10-16 - Step 1: edge-case table

- Asked: a table of all edge cases from the task with the expected response, before any tests.
- Done: 45 cases grouped by step. The assistant added a few traps I did not list: trailing
  newline in `observed_at` (`$` in a regex matches before `\n`), non-ASCII digits (`\d`
  matches any Unicode digit), comparing `10:00:00Z` and `10:00:00.5Z` as strings gives the
  wrong order, validation must run before the duplicate check (422, not 409).
- My decisions: `23:59:60Z` (leap second) returns 422 and goes to README limitations;
  a 4300+ digit integer must be tested through `POST /readings`, not only `json.loads`.
- Checked: reviewed the table against the task text myself.

## 2026-10-16 - Step 2: accept a reading, read the latest one

- Asked: tests first for cases 1-4, then the minimal code.
- Done: `pytest.ini` (so `tests/` can import `app.py`), 3 tests (4 cases with parametrize),
  `app.py` with `create_app()`, `POST /readings`, `GET /sensors/<path:sensor_id>/latest`.
- Checked: tests failed before `app.py` existed (`ModuleNotFoundError`), 4 passed after.
  Both `pytest` and `python -m pytest` work. A separate experiment showed that with the
  default `<sensor_id>` converter `/sensors/room/01/latest` and `/sensors/room%2F01/latest`
  return 404, with `<path:sensor_id>` both return 200.
