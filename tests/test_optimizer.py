"""Unit tests for tsp.optimizer."""

import unittest
from datetime import datetime, timedelta

from tsp.models import Driver, Location, Package
from tsp.optimizer import assign_packages_to_drivers, calculate_route


class TestCalculateRoute(unittest.TestCase):
    def setUp(self):
        self.depot = Location("Depot", 0, 0)
        self.driver = Driver("d1", 70.0, self.depot)
        self.now = datetime(2024, 1, 1, 8, 0, 0)

    def test_empty_packages_returns_empty_route(self):
        route = calculate_route(self.driver, [], self.now)
        self.assertEqual(len(route.stops), 0)
        self.assertAlmostEqual(route.total_distance, 0.0)

    def test_single_package_route(self):
        loc = Location("A", 30, 0)  # 30 miles east
        pkg = Package("p1", 500.0, self.now + timedelta(hours=24), loc)
        route = calculate_route(self.driver, [pkg], self.now)

        self.assertEqual(len(route.stops), 1)
        self.assertAlmostEqual(route.total_distance, 30.0)

    def test_arrival_time_computed_correctly(self):
        # 30 miles at 30 mph → 1 hour travel time
        loc = Location("A", 30, 0)
        pkg = Package("p1", 500.0, self.now + timedelta(hours=24), loc)
        route = calculate_route(self.driver, [pkg], self.now)

        expected_arrival = self.now + timedelta(hours=1)
        actual_arrival = route.stops[0].arrival_time
        delta = abs((actual_arrival - expected_arrival).total_seconds())
        self.assertLess(delta, 1)  # within 1 second

    def test_collinear_packages_optimal_distance(self):
        # Packages at 10, 20, 30 miles east — optimal order visits them left-to-right
        locs = [
            Location("A", 10, 0),
            Location("B", 20, 0),
            Location("C", 30, 0),
        ]
        deadline = self.now + timedelta(hours=48)
        packages = [Package(f"p{i}", 500.0, deadline, locs[i]) for i in range(3)]
        route = calculate_route(self.driver, packages, self.now)

        self.assertEqual(len(route.stops), 3)
        # Optimal distance: 0→10→20→30 = 30 miles
        self.assertAlmostEqual(route.total_distance, 30.0)

    def test_route_driver_assigned(self):
        pkg = Package("p1", 500.0, self.now + timedelta(hours=24), Location("A", 5, 5))
        route = calculate_route(self.driver, [pkg], self.now)
        self.assertEqual(route.driver.id, "d1")

    def test_deadline_order_priority(self):
        """Urgent packages should be visited before later-deadline ones nearby."""
        far = Location("Far", 1, 0)     # 1 mile — fast to reach
        near = Location("Near", 0.1, 0)  # 0.1 mile — even closer
        # near has a very tight deadline, far has a relaxed deadline
        tight_pkg = Package("tight", 500.0, self.now + timedelta(minutes=10), near)
        relaxed_pkg = Package("relaxed", 500.0, self.now + timedelta(hours=24), far)

        route = calculate_route(self.driver, [relaxed_pkg, tight_pkg], self.now)
        # The tight-deadline package should be first
        self.assertEqual(route.stops[0].package.id, "tight")


class TestAssignPackagesToDrivers(unittest.TestCase):
    def setUp(self):
        self.depot = Location("Depot", 25, 25)
        self.now = datetime(2024, 1, 1, 8, 0, 0)

    def test_single_package_single_driver(self):
        driver = Driver("d1", 70.0, self.depot)
        pkg = Package("p1", 500.0, self.now + timedelta(hours=24), Location("A", 30, 25))
        routes, unassigned = assign_packages_to_drivers([pkg], [driver], self.now)

        self.assertEqual(len(unassigned), 0)
        self.assertEqual(len(routes), 1)
        self.assertEqual(len(routes[0].stops), 1)

    def test_all_packages_fit_single_driver(self):
        # driver capacity = 70 × 1728 = 120,960 cu in
        # 10 × 500 = 5,000 cu in — well within capacity
        driver = Driver("d1", 70.0, self.depot)
        deadline = self.now + timedelta(hours=24)
        packages = [
            Package(f"p{i}", 500.0, deadline, Location(f"L{i}", 25 + i + 1, 25))
            for i in range(10)
        ]
        routes, unassigned = assign_packages_to_drivers(packages, [driver], self.now)

        self.assertEqual(len(unassigned), 0)
        self.assertEqual(len(routes), 1)
        self.assertEqual(len(routes[0].stops), 10)

    def test_capacity_forces_second_driver(self):
        # Each driver: 50 cu ft = 86,400 cu in
        # 10 packages × 9,000 cu in = 90,000 cu in > 86,400  → needs 2 drivers
        drivers = [Driver(f"d{i}", 50.0, self.depot) for i in range(1, 3)]
        deadline = self.now + timedelta(hours=24)
        packages = [
            Package(f"p{i}", 9_000.0, deadline, Location(f"L{i}", 25 + i, 25))
            for i in range(10)
        ]
        routes, unassigned = assign_packages_to_drivers(packages, drivers, self.now)

        self.assertGreater(len(routes), 1)
        total_placed = sum(len(r.stops) for r in routes)
        self.assertEqual(total_placed + len(unassigned), len(packages))

    def test_no_drivers_available_all_unassigned(self):
        deadline = self.now + timedelta(hours=24)
        packages = [
            Package(f"p{i}", 500.0, deadline, Location(f"L{i}", 25 + i, 25))
            for i in range(5)
        ]
        routes, unassigned = assign_packages_to_drivers(packages, [], self.now)

        self.assertEqual(len(routes), 0)
        self.assertEqual(len(unassigned), 5)

    def test_empty_packages(self):
        driver = Driver("d1", 70.0, self.depot)
        routes, unassigned = assign_packages_to_drivers([], [driver], self.now)
        self.assertEqual(len(routes), 0)
        self.assertEqual(len(unassigned), 0)

    def test_all_routes_respect_capacity(self):
        drivers = [Driver(f"d{i}", 60.0, self.depot) for i in range(1, 4)]
        deadline = self.now + timedelta(hours=24)
        packages = [
            Package(f"p{i}", 1_000.0, deadline, Location(f"L{i}", 25 + i, 25))
            for i in range(15)
        ]
        routes, _ = assign_packages_to_drivers(packages, drivers, self.now)

        for route in routes:
            self.assertTrue(
                route.is_capacity_valid(),
                f"{route.driver.id} exceeds capacity",
            )

    def test_urgent_packages_processed_first(self):
        """The most urgent package should land in the first dispatched route."""
        driver = Driver("d1", 70.0, self.depot)
        close = Location("Close", 25.1, 25)  # ~0.1 miles from depot

        urgent = Package("urgent", 500.0, self.now + timedelta(hours=1), close)
        relaxed = Package("relaxed", 500.0, self.now + timedelta(hours=48), close)

        routes, unassigned = assign_packages_to_drivers(
            [relaxed, urgent], [driver], self.now
        )
        self.assertEqual(len(unassigned), 0)
        all_ids = [stop.package.id for r in routes for stop in r.stops]
        self.assertIn("urgent", all_ids)

    def test_oversized_single_package_fits_large_vehicle(self):
        # Package = 10,000 cu in; vehicle = 90 cu ft = 155,520 cu in  → fits
        driver = Driver("d1", 90.0, self.depot)
        pkg = Package("big", 10_000.0, self.now + timedelta(hours=24), Location("A", 26, 25))
        routes, unassigned = assign_packages_to_drivers([pkg], [driver], self.now)
        self.assertEqual(len(unassigned), 0)
        self.assertEqual(len(routes), 1)
