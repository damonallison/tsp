# Copilot Instructions

## Project Overview

TSP is a Vehicle Routing Problem (VRP) solver for package delivery. It assigns packages to drivers and computes optimised routes using Google OR-Tools, enforcing both capacity constraints (vehicle cubic footage) and time-window constraints (package deadlines).

## Commands

**Run all tests:**
```bash
mise run test
# or
uv run pytest tests/ -v
```

**Run a single test:**
```bash
uv run pytest tests/test_models.py::TestLocation::test_distance_pythagorean -v
uv run pytest tests/test_optimizer.py::TestCalculateRoute::test_single_package_route -v
```

**Run the demo:**
```bash
uv run python main.py
```

**Install dependencies:**
```bash
uv sync
```

## Architecture

```
tsp/models.py     — Core dataclasses (Location, Package, Driver, Stop, Route)
tsp/optimizer.py  — OR-Tools VRP solver; internal _solve_routing() wraps pywrapcp
tsp/solver.py     — High-level Solver class (the public API callers use)
main.py           — Demo script; generates random packages and prints a solution
```

The call flow is: `Solver.solve()` → `assign_packages_to_drivers()` → `_solve_routing()` (OR-Tools).

`calculate_route()` in `optimizer.py` is a single-vehicle TSP variant (no drops allowed); `assign_packages_to_drivers()` is the multi-vehicle VRP variant (drops allowed with a high penalty).

## Key Conventions

**Units** – coordinates are miles (float), package sizes are cubic inches, vehicle sizes are cubic feet. The conversion constant `CUBIC_INCHES_PER_CUBIC_FOOT = 1728.0` lives in `models.py` and is imported wherever needed. OR-Tools requires integers, so distances are scaled to milli-miles via `_DIST_SCALE = 1_000`.

**Constants in models.py** – all domain limits (`PACKAGE_MIN_CUBIC_INCHES`, `VEHICLE_MAX_CUBIC_FEET`, `AVERAGE_SPEED_MPH`, etc.) are defined there and re-exported; other modules import them from `.models`, not as local magic numbers.

**Validation in `__post_init__`** – `Package` and `Driver` raise `ValueError` in `__post_init__` when constructed out of range. Tests cover boundary values (e.g. 109.9 fails, 110.0 succeeds).

**Test style** – tests use `unittest.TestCase` classes run via pytest. Each module has a corresponding test file (`tsp/models.py` → `tests/test_models.py`).

**`from __future__ import annotations`** – present in every source file for forward-reference support.

**Seeded randomness** – `Solver` accepts a `seed` parameter for reproducible driver generation; `main.py` uses `seed=42` throughout.

**Fixed cost per vehicle** – `_solve_routing` sets `routing.SetFixedCostOfAllVehicles(100_000 * _DIST_SCALE)` to discourage using more drivers than necessary.
