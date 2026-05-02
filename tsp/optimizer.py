"""Route optimisation using Google OR-Tools constraint solver (VRP with time windows)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import List, Tuple

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .models import AVERAGE_SPEED_MPH, Driver, Package, Route, Stop

# Scale factor: convert float miles to integer distance units (milli-miles).
_DIST_SCALE = 1_000


def _build_route(
    driver: Driver,
    packages: List[Package],
    start_time: datetime,
    speed_mph: float = AVERAGE_SPEED_MPH,
) -> Route:
    """Construct a :class:`Route` object with computed arrival times."""
    route = Route(driver=driver)
    cx, cy = driver.depot.x, driver.depot.y
    current_time = start_time

    for pkg in packages:
        distance = math.sqrt(
            (cx - pkg.destination.x) ** 2 + (cy - pkg.destination.y) ** 2
        )
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


def _solve_routing(
    packages: List[Package],
    drivers: List[Driver],
    start_time: datetime,
    speed_mph: float,
    allow_drops: bool,
    time_limit_seconds: int,
) -> Tuple[List[Route], List[Package]]:
    """
    Core OR-Tools VRP solver.

    Node 0 is the shared depot; nodes 1..n map to *packages* in order.
    When *allow_drops* is True each package node gets a high-penalty disjunction
    so it can be left unserved rather than making the problem infeasible.
    """
    if not packages or not drivers:
        return [], list(packages)

    depot = drivers[0].depot
    locs: List[Tuple[float, float]] = [(depot.x, depot.y)] + [
        (p.destination.x, p.destination.y) for p in packages
    ]
    n = len(locs)
    num_vehicles = len(drivers)

    # Integer distance matrix (milli-miles).
    dist_matrix = [
        [
            round(
                math.sqrt(
                    (locs[i][0] - locs[j][0]) ** 2 + (locs[i][1] - locs[j][1]) ** 2
                )
                * _DIST_SCALE
            )
            for j in range(n)
        ]
        for i in range(n)
    ]

    # Integer time matrix (seconds).
    time_matrix = [
        [
            round(
                math.sqrt(
                    (locs[i][0] - locs[j][0]) ** 2 + (locs[i][1] - locs[j][1]) ** 2
                )
                / speed_mph
                * 3600
            )
            for j in range(n)
        ]
        for i in range(n)
    ]

    # Time windows [earliest, latest] in seconds from start_time.
    horizon = 10 * 24 * 3600  # 10-day fallback horizon
    time_windows: List[Tuple[int, int]] = [(0, horizon)]  # depot
    for pkg in packages:
        deadline_s = int((pkg.arrive_by - start_time).total_seconds())
        time_windows.append((0, max(1, deadline_s)))

    # Capacity in cubic inches (integer).
    demands = [0] + [int(round(p.size_cubic_inches)) for p in packages]
    vehicle_capacities = [int(round(d.vehicle_size_cubic_inches)) for d in drivers]

    manager = pywrapcp.RoutingIndexManager(n, num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    # Arc-cost callback (distance objective).
    def dist_cb(from_idx: int, to_idx: int) -> int:
        return dist_matrix[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

    dist_cb_idx = routing.RegisterTransitCallback(dist_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(dist_cb_idx)

    # Fixed cost per active vehicle to encourage using fewer drivers.
    routing.SetFixedCostOfAllVehicles(100_000 * _DIST_SCALE)

    # Time dimension (enforces delivery deadlines).
    def time_cb(from_idx: int, to_idx: int) -> int:
        return time_matrix[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

    time_cb_idx = routing.RegisterTransitCallback(time_cb)
    routing.AddDimension(time_cb_idx, horizon, horizon, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")
    for node_i, (tw_start, tw_end) in enumerate(time_windows):
        time_dim.CumulVar(manager.NodeToIndex(node_i)).SetRange(tw_start, tw_end)
    for v in range(num_vehicles):
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(routing.Start(v)))
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(routing.End(v)))

    # Capacity dimension.
    def demand_cb(from_idx: int) -> int:
        return demands[manager.IndexToNode(from_idx)]

    demand_cb_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb_idx, 0, vehicle_capacities, True, "Capacity"
    )

    # Optional: allow unserved packages (VRP mode with penalty).
    if allow_drops:
        drop_penalty = 1_000_000_000
        for node in range(1, n):
            routing.AddDisjunction([manager.NodeToIndex(node)], drop_penalty)

    # Search parameters.
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    if time_limit_seconds > 0:
        params.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        params.time_limit.seconds = time_limit_seconds

    solution = routing.SolveWithParameters(params)
    if solution is None:
        return [], list(packages)

    # Extract routes from the solution.
    routes: List[Route] = []
    assigned_ids: set = set()
    for v, driver in enumerate(drivers):
        idx = routing.Start(v)
        sequence: List[Package] = []
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            if node != 0:
                sequence.append(packages[node - 1])
                assigned_ids.add(packages[node - 1].id)
            idx = solution.Value(routing.NextVar(idx))
        if sequence:
            routes.append(_build_route(driver, sequence, start_time, speed_mph))

    unassigned = [p for p in packages if p.id not in assigned_ids]
    return routes, unassigned


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
    Return an OR-Tools optimised :class:`Route` for *driver* to deliver
    *packages* starting at *start_time*.

    Uses a single-vehicle TSP with time-window constraints.  If the solver
    cannot find a feasible ordering the packages are delivered in their
    original order.
    """
    if not packages:
        return Route(driver=driver)

    routes, _ = _solve_routing(
        packages,
        [driver],
        start_time,
        speed_mph,
        allow_drops=False,
        time_limit_seconds=0,
    )
    return (
        routes[0] if routes else _build_route(driver, packages, start_time, speed_mph)
    )


def assign_packages_to_drivers(
    packages: List[Package],
    drivers: List[Driver],
    start_time: datetime,
    speed_mph: float = AVERAGE_SPEED_MPH,
) -> Tuple[List[Route], List[Package]]:
    """
    Assign packages to drivers and compute optimised routes using OR-Tools VRP.

    Enforces capacity and time-window (deadline) constraints across all
    vehicles simultaneously.  Packages that cannot be served within any
    constraint are returned as *unassigned*.

    Returns
    -------
    routes : list of :class:`Route`
        One route per driver that was dispatched.
    unassigned : list of :class:`Package`
        Packages that could not be routed within any constraint.
    """
    return _solve_routing(
        packages, drivers, start_time, speed_mph, allow_drops=True, time_limit_seconds=5
    )
