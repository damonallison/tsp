"""Route optimisation: deadline-aware nearest-neighbour + 2-opt TSP/VRP solver."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Tuple

from .models import AVERAGE_SPEED_MPH, Driver, Package, Route, Stop


# ---------------------------------------------------------------------------
# Low-level route-building helpers
# ---------------------------------------------------------------------------


def _route_distance(start_x: float, start_y: float, packages: List[Package]) -> float:
    """Total Euclidean distance of a route starting at *(start_x, start_y)*."""
    if not packages:
        return 0.0
    import math

    def dist(ax: float, ay: float, bx: float, by: float) -> float:
        return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)

    total = dist(start_x, start_y, packages[0].destination.x, packages[0].destination.y)
    for i in range(len(packages) - 1):
        a = packages[i].destination
        b = packages[i + 1].destination
        total += dist(a.x, a.y, b.x, b.y)
    return total


def _deadline_aware_nearest_neighbor(
    start_x: float,
    start_y: float,
    packages: List[Package],
    start_time: datetime,
    speed_mph: float = AVERAGE_SPEED_MPH,
) -> List[Package]:
    """
    Build an initial route using a deadline-aware nearest-neighbour heuristic.

    At every step the algorithm picks the *most urgent* package that can still
    be reached on time.  When no feasible package exists it falls back to the
    geographically nearest remaining package.
    """
    import math

    remaining = list(packages)
    order: List[Package] = []
    cx, cy = start_x, start_y
    current_time = start_time

    while remaining:
        feasible = []
        for pkg in remaining:
            dx = cx - pkg.destination.x
            dy = cy - pkg.destination.y
            travel_h = math.sqrt(dx * dx + dy * dy) / speed_mph
            if current_time + timedelta(hours=travel_h) <= pkg.arrive_by:
                feasible.append(pkg)

        candidates = feasible if feasible else remaining
        # Primary key: deadline (most urgent first);  tie-break: distance
        next_pkg = min(
            candidates,
            key=lambda p: (
                p.arrive_by,
                math.sqrt((cx - p.destination.x) ** 2 + (cy - p.destination.y) ** 2),
            ),
        )

        order.append(next_pkg)
        dx = cx - next_pkg.destination.x
        dy = cy - next_pkg.destination.y
        travel_h = math.sqrt(dx * dx + dy * dy) / speed_mph
        current_time += timedelta(hours=travel_h)
        cx, cy = next_pkg.destination.x, next_pkg.destination.y
        remaining.remove(next_pkg)

    return order


def _two_opt(
    start_x: float,
    start_y: float,
    packages: List[Package],
    start_time: datetime,
    speed_mph: float = AVERAGE_SPEED_MPH,
) -> List[Package]:
    """
    Improve a route using 2-opt swaps.

    A swap is accepted only when it *reduces total distance* **and** the
    resulting route still satisfies every delivery deadline.
    """
    if len(packages) <= 2:
        return packages

    best = list(packages)
    best_dist = _route_distance(start_x, start_y, best)
    improved = True

    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 2, len(best)):
                candidate = best[: i + 1] + best[i + 1 : j + 1][::-1] + best[j + 1 :]
                cand_dist = _route_distance(start_x, start_y, candidate)
                if cand_dist < best_dist - 1e-10:
                    # Validate deadlines before accepting the swap
                    if _deadlines_satisfied(start_x, start_y, candidate, start_time, speed_mph):
                        best = candidate
                        best_dist = cand_dist
                        improved = True
    return best


def _deadlines_satisfied(
    start_x: float,
    start_y: float,
    packages: List[Package],
    start_time: datetime,
    speed_mph: float = AVERAGE_SPEED_MPH,
) -> bool:
    """Return True when every package in the ordered list can be delivered on time."""
    import math

    cx, cy = start_x, start_y
    current_time = start_time
    for pkg in packages:
        dx = cx - pkg.destination.x
        dy = cy - pkg.destination.y
        travel_h = math.sqrt(dx * dx + dy * dy) / speed_mph
        current_time += timedelta(hours=travel_h)
        if current_time > pkg.arrive_by:
            return False
        cx, cy = pkg.destination.x, pkg.destination.y
    return True


def _build_route(
    driver: Driver,
    packages: List[Package],
    start_time: datetime,
    speed_mph: float = AVERAGE_SPEED_MPH,
) -> Route:
    """Construct a :class:`Route` object with computed arrival times."""
    import math

    route = Route(driver=driver)
    cx, cy = driver.depot.x, driver.depot.y
    current_time = start_time

    for pkg in packages:
        dx = cx - pkg.destination.x
        dy = cy - pkg.destination.y
        distance = math.sqrt(dx * dx + dy * dy)
        travel_h = distance / speed_mph
        arrival_time = current_time + timedelta(hours=travel_h)

        route.stops.append(
            Stop(
                package=pkg,
                arrival_time=arrival_time,
                distance_from_previous=distance,
            )
        )

        cx, cy = pkg.destination.x, pkg.destination.y
        current_time = arrival_time

    return route


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_route(
    driver: Driver,
    packages: List[Package],
    start_time: datetime,
    speed_mph: float = AVERAGE_SPEED_MPH,
) -> Route:
    """
    Return an optimised :class:`Route` for *driver* to deliver *packages*
    starting at *start_time*.

    The algorithm:

    1. Deadline-aware nearest-neighbour for an initial ordering.
    2. 2-opt improvement (deadline-safe swaps only).
    3. Build and return the :class:`Route` with exact arrival times.
    """
    if not packages:
        return Route(driver=driver)

    order = _deadline_aware_nearest_neighbor(
        driver.depot.x, driver.depot.y, packages, start_time, speed_mph
    )
    order = _two_opt(driver.depot.x, driver.depot.y, order, start_time, speed_mph)
    return _build_route(driver, order, start_time, speed_mph)


def assign_packages_to_drivers(
    packages: List[Package],
    drivers: List[Driver],
    start_time: datetime,
    speed_mph: float = AVERAGE_SPEED_MPH,
) -> Tuple[List[Route], List[Package]]:
    """
    Assign packages to drivers and compute optimised routes.

    **Optimisation goals** (in priority order):

    1. Earliest deliveries — urgent packages are assigned first so that they
       reach their destination as early as possible.
    2. Minimal drivers — a new driver is only enlisted when no existing driver's
       route can accommodate the package (capacity **and** deadline constraints).

    Returns
    -------
    routes : list of :class:`Route`
        One route per driver that was dispatched.
    unassigned : list of :class:`Package`
        Packages that could not be routed within any constraint.
    """
    # Sort by deadline ascending — most urgent packages are processed first.
    sorted_packages = sorted(packages, key=lambda p: p.arrive_by)

    # Use a list of (driver, packages) pairs to avoid dict-key hashing issues.
    assignments: List[Tuple[Driver, List[Package]]] = []
    available_drivers = list(drivers)
    unassigned: List[Package] = []

    for package in sorted_packages:
        placed = False

        # Try existing drivers first (minimise driver count).
        for i, (driver, current_pkgs) in enumerate(assignments):
            candidate_pkgs = current_pkgs + [package]

            # Capacity check (fast, no route calculation needed).
            total_volume = sum(p.size_cubic_inches for p in candidate_pkgs)
            if total_volume > driver.vehicle_size_cubic_inches:
                continue

            # Full validity check (recompute route with the new package).
            test_route = calculate_route(driver, candidate_pkgs, start_time, speed_mph)
            if test_route.is_valid():
                assignments[i] = (driver, candidate_pkgs)
                placed = True
                break

        if placed:
            continue

        # Enlist a new driver.
        while available_drivers:
            new_driver = available_drivers.pop(0)

            # Can the package physically fit in this vehicle?
            if package.size_cubic_inches > new_driver.vehicle_size_cubic_inches:
                continue  # try next driver

            # Can this single package be delivered on time?
            test_route = calculate_route(new_driver, [package], start_time, speed_mph)
            if test_route.is_valid():
                assignments.append((new_driver, [package]))
                placed = True
                break
            # Package cannot be delivered on time even by a fresh driver —
            # skip this driver and put it back since it might still be
            # useful for other packages.
            available_drivers.insert(0, new_driver)
            break

        if not placed:
            unassigned.append(package)

    # Build final optimised routes.
    final_routes: List[Route] = [
        calculate_route(driver, pkgs, start_time, speed_mph)
        for driver, pkgs in assignments
    ]
    return final_routes, unassigned
