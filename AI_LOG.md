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
  I also ran the tests myself on my machine (WSL): 4 passed.

## 2026-10-16 - Step 3: validation (422)

- Asked: tests first for table rows 5-30, similar cases grouped with `pytest.mark.parametrize`;
  all checks in one function `validate_reading(body)` that returns an error text or None,
  the POST route only calls it.
- Done: 11 new test functions (54 new cases, 58 in total); `validate_reading` in `app.py`;
  the route parses the body with `request.get_json(force=True, silent=True)`.
- Checked: before the code 45 failed / 13 passed (the 13 are the old tests and the "valid
  input is accepted" cases); after the code 58 passed. Mutation check in a copy of the
  project, one rule broken at a time: removing the bool check fails `true`/`false`; removing
  the OverflowError handler fails the 400-zeros case (500); removing `silent=True` fails
  broken JSON, empty body and the 5000-digit case (400). Changing `fullmatch` to `match` or
  `[0-9]` to `\d` fails nothing, because `datetime.fromisoformat` also rejects a trailing
  newline and non-ASCII digits (checked separately), so these two are a second line of defense.
  First run of the mutation script was wrong (bad path, mutations never applied); fixed and rerun.

## 2026-10-16 - Fix: non-ASCII digits in the test file

- I noticed: the assistant said the Arabic-Indic digits in the test were written as `٢`
  escapes, but the file contained the real characters (the assistant's file-writing tool had
  decoded the escapes, and it had not checked the bytes).
- Done: both `tests/test_app.py` and the comment in `app.py` are now ASCII only; the test
  uses `"٢٠٢٦..."`.
- Checked: byte check that both files are ASCII only; at runtime the test value still starts
  with code points 0x662, 0x660, 0x662, 0x666; 58 passed.

## 2026-10-16 - Fix: deeply nested JSON returned 500

- Found during step 3: a body like `[[[...]]]` nested 100 000 levels deep returned HTTP 500,
  because Python raises `RecursionError` (not `ValueError`) and `get_json(silent=True)` only
  catches `ValueError`.
- Asked: fix it in a separate small commit with a test.
- Done: test case `deeply-nested` (depth 1 000 000, so it also overflows on Linux, where the
  stack is bigger); `parse_json_body()` calls `json.loads` and catches
  `(ValueError, RecursionError)`; the route uses it instead of `request.get_json`.
- Checked: the new case failed first (`assert 500 == 422`), then 59 passed; a direct request
  with depth 100 000 and 1 000 000 returns 422.
- My rule from now on: no more exotic cases beyond the task text.
