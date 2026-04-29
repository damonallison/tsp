"""Demo: generate random packages and route them using the TSP solver."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from tsp.models import Location, Package
from tsp.solver import Solver


def generate_locations(n: int = 15, seed: int = 42) -> list:
    rng = random.Random(seed)
    names = [
        "Downtown", "Airport", "Mall", "University", "Hospital",
        "Stadium", "Harbor", "Park", "Library", "Museum",
        "Factory", "Hotel", "School", "Church", "Market",
    ]
    return [
        Location(name=names[i % len(names)], x=rng.uniform(0, 50), y=rng.uniform(0, 50))
        for i in range(n)
    ]


def generate_packages(locations: list, n: int = 20, seed: int = 42) -> list:
    rng = random.Random(seed)
    now = datetime.now()
    return [
        Package(
            id=f"pkg_{i + 1:03d}",
            size_cubic_inches=rng.uniform(110, 10_000),
            arrive_by=now + timedelta(hours=rng.uniform(1, 48)),
            destination=rng.choice(locations),
        )
        for i in range(n)
    ]


def main() -> None:
    depot = Location(name="Depot", x=25.0, y=25.0)
    locations = generate_locations(n=15, seed=42)
    packages = generate_packages(locations, n=20, seed=42)

    print(f"Packages to deliver : {len(packages)}")
    sizes = [p.size_cubic_inches for p in packages]
    print(f"Package size range  : {min(sizes):.0f} – {max(sizes):.0f} cu in")

    solver = Solver(depot=depot, num_drivers=5, seed=42)
    print(f"\nDrivers available   : {len(solver.drivers)}")
    for driver in solver.drivers:
        print(f"  {driver.id}: {driver.vehicle_size_cubic_feet:.1f} cu ft")

    routes, unassigned = solver.solve(packages)
    solver.print_solution(routes, unassigned)


if __name__ == "__main__":
    main()
