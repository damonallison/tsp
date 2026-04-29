"""High-level solver interface for the TSP package routing problem."""

from __future__ import annotations

import random
from datetime import datetime
from typing import List, Optional, Tuple

from .models import (
    AVERAGE_SPEED_MPH,
    VEHICLE_MAX_CUBIC_FEET,
    VEHICLE_MIN_CUBIC_FEET,
    Driver,
    Location,
    Package,
    Route,
)
from .optimizer import assign_packages_to_drivers


class Solver:
    """
    High-level solver that manages a pool of drivers and routes packages.

    Parameters
    ----------
    depot:
        The location where all drivers start (and return to).
    num_drivers:
        Maximum number of drivers available.  Actual drivers used may be
        fewer depending on the package load.
    seed:
        Optional random seed for reproducible vehicle-size generation.
    speed_mph:
        Average driving speed used for travel-time calculations.
    """

    def __init__(
        self,
        depot: Location,
        num_drivers: int = 5,
        seed: Optional[int] = None,
        speed_mph: float = AVERAGE_SPEED_MPH,
    ) -> None:
        self.depot = depot
        self.speed_mph = speed_mph
        self.drivers: List[Driver] = self._create_drivers(num_drivers, seed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_drivers(self, num_drivers: int, seed: Optional[int]) -> List[Driver]:
        """Create *num_drivers* drivers with random vehicle sizes (50-90 cu ft)."""
        rng = random.Random(seed)
        return [
            Driver(
                id=f"driver_{i + 1}",
                vehicle_size_cubic_feet=rng.uniform(
                    VEHICLE_MIN_CUBIC_FEET, VEHICLE_MAX_CUBIC_FEET
                ),
                depot=self.depot,
            )
            for i in range(num_drivers)
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(
        self,
        packages: List[Package],
        start_time: Optional[datetime] = None,
    ) -> Tuple[List[Route], List[Package]]:
        """
        Route all *packages* using the available driver pool.

        Parameters
        ----------
        packages:
            Packages to be delivered.
        start_time:
            Departure time for all drivers (defaults to *now*).

        Returns
        -------
        routes : list of :class:`~tsp.models.Route`
            One entry per driver dispatched (drivers with no packages are
            excluded).
        unassigned : list of :class:`~tsp.models.Package`
            Packages that could not be delivered within all constraints.
        """
        if start_time is None:
            start_time = datetime.now()
        return assign_packages_to_drivers(
            packages=packages,
            drivers=self.drivers,
            start_time=start_time,
            speed_mph=self.speed_mph,
        )

    def print_solution(
        self, routes: List[Route], unassigned: List[Package]
    ) -> None:
        """Print a human-readable routing solution to *stdout*."""
        sep = "=" * 62
        print(f"\n{sep}")
        print("TSP Package Routing Solution")
        print(sep)
        print(f"Drivers dispatched : {len(routes)}")
        print(f"Packages routed    : {sum(len(r.stops) for r in routes)}")
        print(f"Unassigned packages: {len(unassigned)}")

        for route in routes:
            driver = route.driver
            used_pct = (
                route.total_volume_cubic_feet / driver.vehicle_size_cubic_feet * 100
                if driver.vehicle_size_cubic_feet
                else 0
            )
            violations = route.deadline_violations()
            print(f"\n  Driver {driver.id}")
            print(
                f"    Vehicle : {driver.vehicle_size_cubic_feet:.1f} cu ft  "
                f"({route.total_volume_cubic_feet:.2f} used, {used_pct:.0f}%)"
            )
            print(f"    Distance: {route.total_distance:.1f} miles")
            print(f"    Valid   : {'yes' if route.is_valid() else 'NO — see violations below'}")

            for i, stop in enumerate(route.stops, start=1):
                on_time = "✓" if stop.arrival_time <= stop.package.arrive_by else "✗"
                print(
                    f"    {i:2}. [{on_time}] {stop.package.destination.name:12s} "
                    f"arrive {stop.arrival_time.strftime('%m/%d %H:%M')}  "
                    f"deadline {stop.package.arrive_by.strftime('%m/%d %H:%M')}  "
                    f"({stop.package.size_cubic_inches:.0f} cu in)"
                )

            if violations:
                print(f"    Deadline violations: {[p.id for p in violations]}")

        if unassigned:
            print("\nUnassigned packages:")
            for pkg in unassigned:
                print(
                    f"  {pkg.id}: {pkg.size_cubic_inches:.0f} cu in, "
                    f"deadline {pkg.arrive_by.strftime('%Y-%m-%d %H:%M')}"
                )
