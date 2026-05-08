# TSP — agent instructions

This repository is a small, self-contained example of a Vehicle Routing Problem (VRP) / TSP-style solver.

**Project Summary**

- **Purpose:** example VRP solver that routes packages to drivers while enforcing vehicle capacity and delivery time-window (deadline) constraints.
- **Core approach:** uses Google OR-Tools (routing solver) with integer scaling of distances and times to produce optimized routes.
- **Public entrypoints:** `calculate_route()` (single-vehicle TSP) and `assign_packages_to_drivers()` (multi-vehicle VRP) in `tsp/optimizer.py`.
- **High-level API:** `tsp.solver.Solver` builds a driver pool and delegates routing to the optimizer; `main.py` is a simple demo generator.

**Repo structure (important files)**

- `main.py` — demo runner that generates random `Location` and `Package` instances and prints a solution.
- `tsp/models.py` — domain models: `Location`, `Package`, `Driver`, `Stop`, `Route` and shared constants.
- `tsp/optimizer.py` — OR-Tools integration and core solver implementation (`_DIST_SCALE = 1000`, time in seconds).
- `tsp/solver.py` — convenience `Solver` class that creates drivers and calls the optimizer.
- `tests/` — unit tests (written as `unittest.TestCase` classes and executed via `pytest`).

**Quick commands**

- Install dependencies (requires Python >= 3.13.13):

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install ortools
```

- Run tests:

```sh
uv run pytest tests/ -v   # project alias used in this repo
# or, equivalently
python -m pytest tests/ -v
```

- Run demo:

```sh
uv run python main.py
```

**Non-obvious conventions & notes**

- `from __future__ import annotations` appears in all source files.
- Tests use `unittest.TestCase` classes (run via `pytest`).
- Seeded randomness: `Solver()` and `main.py` accept a `seed` for reproducible runs (demo/CI use `seed=42`).
- OR-Tools scaling: `_DIST_SCALE = 1_000` converts miles to milli-miles (integers); time is expressed in seconds inside the solver.
- Domain constants live in `tsp/models.py` (`AVERAGE_SPEED_MPH`, `CUBIC_INCHES_PER_CUBIC_FOOT`, package/vehicle size bounds).

**Agent guidance**

- The optimizer can be sensitive to slight time-window or distance changes — if tests fail after edits, check delivery `arrive_by` values and travel-time math in `tsp/optimizer.py` and test fixtures.
- Prefer fixing root causes (model or time-window logic) rather than surface patches when tests fail.

## Verify after any code change

```sh
uv run pytest tests/ -v
```

OR-Tools solver tests can be sensitive to time-window changes. If they fail, check deadlines and travel times in test fixtures.
