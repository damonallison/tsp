"""Unit tests for tsp.solver.Solver."""

import unittest
from datetime import datetime, timedelta

from tsp.models import Location, Package
from tsp.solver import Solver


class TestSolverInit(unittest.TestCase):
    def setUp(self):
        self.depot = Location("Depot", 25, 25)

    def test_correct_driver_count(self):
        solver = Solver(depot=self.depot, num_drivers=4, seed=0)
        self.assertEqual(len(solver.drivers), 4)

    def test_vehicle_sizes_within_bounds(self):
        solver = Solver(depot=self.depot, num_drivers=20, seed=99)
        for driver in solver.drivers:
            self.assertGreaterEqual(driver.vehicle_size_cubic_feet, 50.0)
            self.assertLessEqual(driver.vehicle_size_cubic_feet, 90.0)

    def test_reproducible_with_same_seed(self):
        s1 = Solver(depot=self.depot, num_drivers=5, seed=42)
        s2 = Solver(depot=self.depot, num_drivers=5, seed=42)
        for d1, d2 in zip(s1.drivers, s2.drivers):
            self.assertAlmostEqual(
                d1.vehicle_size_cubic_feet, d2.vehicle_size_cubic_feet
            )

    def test_different_seeds_differ(self):
        s1 = Solver(depot=self.depot, num_drivers=5, seed=1)
        s2 = Solver(depot=self.depot, num_drivers=5, seed=2)
        sizes_1 = [d.vehicle_size_cubic_feet for d in s1.drivers]
        sizes_2 = [d.vehicle_size_cubic_feet for d in s2.drivers]
        self.assertNotEqual(sizes_1, sizes_2)

    def test_drivers_start_at_depot(self):
        solver = Solver(depot=self.depot, num_drivers=3, seed=0)
        for driver in solver.drivers:
            self.assertEqual(driver.depot.name, "Depot")


class TestSolverSolve(unittest.TestCase):
    def setUp(self):
        self.depot = Location("Depot", 25, 25)
        self.now = datetime(2024, 6, 1, 8, 0, 0)

    def test_empty_packages(self):
        solver = Solver(depot=self.depot, num_drivers=3, seed=0)
        routes, unassigned = solver.solve([], self.now)
        self.assertEqual(len(routes), 0)
        self.assertEqual(len(unassigned), 0)

    def test_single_package_is_assigned(self):
        solver = Solver(depot=self.depot, num_drivers=3, seed=0)
        pkg = Package("p1", 500.0, self.now + timedelta(hours=24), Location("A", 30, 25))
        routes, unassigned = solver.solve([pkg], self.now)

        self.assertEqual(len(unassigned), 0)
        total_stops = sum(len(r.stops) for r in routes)
        self.assertEqual(total_stops, 1)

    def test_all_packages_assigned_within_capacity(self):
        solver = Solver(depot=self.depot, num_drivers=5, seed=42)
        deadline = self.now + timedelta(hours=24)
        packages = [
            Package(f"p{i}", 1_000.0, deadline, Location(f"L{i}", 25 + (i % 5) + 1, 25))
            for i in range(10)
        ]
        routes, _ = solver.solve(packages, self.now)
        for route in routes:
            self.assertTrue(
                route.is_capacity_valid(),
                f"{route.driver.id} exceeds vehicle capacity",
            )

    def test_minimal_drivers_used(self):
        """When packages fit in one driver's vehicle, only one driver should be used."""
        # 70 cu ft ≈ 120,960 cu in;  5 × 1,000 = 5,000 — fits easily in one driver
        solver = Solver(depot=self.depot, num_drivers=5, seed=42)
        deadline = self.now + timedelta(hours=24)
        packages = [
            Package(f"p{i}", 1_000.0, deadline, Location(f"L{i}", 26 + i, 25))
            for i in range(5)
        ]
        routes, unassigned = solver.solve(packages, self.now)
        self.assertEqual(len(unassigned), 0)
        self.assertEqual(len(routes), 1)

    def test_default_start_time_is_now(self):
        """Calling solve without start_time should still return a valid result."""
        solver = Solver(depot=self.depot, num_drivers=2, seed=0)
        pkg = Package("p1", 500.0, datetime.now() + timedelta(hours=24), Location("A", 26, 25))
        routes, unassigned = solver.solve([pkg])
        # Should produce some valid output
        total = sum(len(r.stops) for r in routes)
        self.assertEqual(total + len(unassigned), 1)

    def test_no_deadline_violations_in_tight_scenario(self):
        """Packages close to depot with generous deadlines must all be on time."""
        solver = Solver(depot=self.depot, num_drivers=5, seed=7)
        deadline = self.now + timedelta(hours=48)
        packages = [
            Package(f"p{i}", 500.0, deadline, Location(f"L{i}", 25 + (i + 1) * 0.5, 25))
            for i in range(8)
        ]
        routes, _ = solver.solve(packages, self.now)
        for route in routes:
            self.assertEqual(
                route.deadline_violations(),
                [],
                f"{route.driver.id} has deadline violations",
            )
