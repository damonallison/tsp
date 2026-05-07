"""Unit tests for tsp.solver.Solver."""

import contextlib
import io
import unittest
from datetime import datetime, timedelta

from tsp.models import Driver, Location, Package, Route, Stop
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


class TestSolverPrintSolution(unittest.TestCase):
    """Tests for Solver.print_solution() — exercises all output branches."""

    def setUp(self):
        self.depot = Location("Depot", 25, 25)
        self.now = datetime(2024, 6, 1, 8, 0, 0)
        self.solver = Solver(depot=self.depot, num_drivers=2, seed=0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _capture(self, routes, unassigned) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.solver.print_solution(routes, unassigned)
        return buf.getvalue()

    def _make_stop(
        self,
        pkg_id: str,
        deadline_offset_hours: float,
        arrival_offset_hours: float,
        loc_name: str = "Loc",
        loc_x: float = 30.0,
        loc_y: float = 25.0,
        size: float = 500.0,
        dist: float = 5.0,
    ) -> Stop:
        loc = Location(loc_name, loc_x, loc_y)
        pkg = Package(pkg_id, size, self.now + timedelta(hours=deadline_offset_hours), loc)
        return Stop(
            package=pkg,
            arrival_time=self.now + timedelta(hours=arrival_offset_hours),
            distance_from_previous=dist,
        )

    # ------------------------------------------------------------------
    # Header / summary
    # ------------------------------------------------------------------

    def test_header_printed_for_empty_solution(self):
        output = self._capture([], [])
        self.assertIn("TSP Package Routing Solution", output)
        self.assertIn("Drivers dispatched : 0", output)
        self.assertIn("Packages routed    : 0", output)
        self.assertIn("Unassigned packages: 0", output)

    # ------------------------------------------------------------------
    # On-time vs. late stop markers (✓ / ✗)
    # ------------------------------------------------------------------

    def test_on_time_stop_prints_checkmark(self):
        """Arrival before deadline prints ✓ and no deadline-violation line."""
        driver = self.solver.drivers[0]
        stop = self._make_stop("p1", deadline_offset_hours=24, arrival_offset_hours=1)
        route = Route(driver=driver, stops=[stop])

        output = self._capture([route], [])
        self.assertIn("✓", output)
        self.assertNotIn("✗", output)
        self.assertNotIn("Deadline violations", output)

    def test_late_stop_prints_cross_and_violation_list(self):
        """Arrival after deadline prints ✗ and a Deadline violations line."""
        driver = self.solver.drivers[0]
        # Arrives 3 h after the 1 h deadline
        stop = self._make_stop("p2", deadline_offset_hours=1, arrival_offset_hours=3)
        route = Route(driver=driver, stops=[stop])

        output = self._capture([route], [])
        self.assertIn("✗", output)
        self.assertIn("Deadline violations", output)
        self.assertIn("p2", output)

    def test_mixed_stops_print_both_markers(self):
        """One on-time and one late stop → both ✓ and ✗ appear."""
        driver = self.solver.drivers[0]
        on_time = self._make_stop(
            "on", deadline_offset_hours=24, arrival_offset_hours=1,
            loc_name="OnTime", loc_x=29.0,
        )
        late = self._make_stop(
            "late", deadline_offset_hours=1, arrival_offset_hours=3,
            loc_name="Late", loc_x=31.0,
        )
        route = Route(driver=driver, stops=[on_time, late])

        output = self._capture([route], [])
        self.assertIn("✓", output)
        self.assertIn("✗", output)

    # ------------------------------------------------------------------
    # Unassigned packages branch
    # ------------------------------------------------------------------

    def test_unassigned_packages_section_printed(self):
        loc = Location("Unassigned", 35, 25)
        pkg = Package("u1", 500.0, self.now + timedelta(hours=24), loc)

        output = self._capture([], [pkg])
        self.assertIn("Unassigned packages:", output)
        self.assertIn("u1", output)

    def test_no_unassigned_section_when_empty(self):
        output = self._capture([], [])
        # The summary line always reads "Unassigned packages: 0".
        # The *section* header is printed as "\nUnassigned packages:\n" (no trailing number).
        self.assertNotIn("\nUnassigned packages:\n", output)

    # ------------------------------------------------------------------
    # Zero vehicle-size guard  (``if driver.vehicle_size_cubic_feet else 0``)
    # ------------------------------------------------------------------

    def test_zero_vehicle_size_guard_yields_zero_percent(self):
        """
        When vehicle_size_cubic_feet is forced to 0 after construction the
        ``else 0`` branch of the used_pct ternary must execute without
        raising a ZeroDivisionError, and the output must show 0%.
        """
        driver = Driver("d_zero", 50.0, self.depot)
        # Driver is a non-frozen dataclass: we can override the field directly.
        driver.vehicle_size_cubic_feet = 0

        stop = self._make_stop("p3", deadline_offset_hours=24, arrival_offset_hours=1)
        route = Route(driver=driver, stops=[stop])

        output = self._capture([route], [])
        # used_pct is computed as 0 when vehicle_size_cubic_feet is falsy
        self.assertIn(", 0%)", output)
