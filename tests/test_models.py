"""Unit tests for tsp.models."""

import unittest
from datetime import datetime, timedelta

from tsp.models import (
    CUBIC_INCHES_PER_CUBIC_FOOT,
    Driver,
    Location,
    Package,
    Route,
    Stop,
)


class TestLocation(unittest.TestCase):
    def test_distance_pythagorean(self):
        a = Location("A", 0, 0)
        b = Location("B", 3, 4)
        self.assertAlmostEqual(a.distance_to(b), 5.0)

    def test_distance_symmetric(self):
        a = Location("A", 1, 2)
        b = Location("B", 5, 9)
        self.assertAlmostEqual(a.distance_to(b), b.distance_to(a))

    def test_distance_same_point(self):
        loc = Location("A", 10, 20)
        self.assertAlmostEqual(loc.distance_to(loc), 0.0)

    def test_travel_time(self):
        a = Location("A", 0, 0)
        b = Location("B", 30, 0)  # 30 miles away
        # At 30 mph → 1 hour
        self.assertAlmostEqual(a.travel_time_to(b, speed_mph=30), 1.0)


class TestPackage(unittest.TestCase):
    def setUp(self):
        self.loc = Location("Dest", 10, 10)
        self.deadline = datetime.now() + timedelta(hours=24)

    def test_valid_package_minimum_size(self):
        pkg = Package("p1", 110.0, self.deadline, self.loc)
        self.assertAlmostEqual(pkg.size_cubic_inches, 110.0)

    def test_valid_package_maximum_size(self):
        pkg = Package("p1", 10_000.0, self.deadline, self.loc)
        self.assertAlmostEqual(pkg.size_cubic_inches, 10_000.0)

    def test_valid_package_midrange(self):
        pkg = Package("p1", 5_000.0, self.deadline, self.loc)
        self.assertAlmostEqual(pkg.size_cubic_feet, 5_000.0 / CUBIC_INCHES_PER_CUBIC_FOOT)

    def test_invalid_package_too_small(self):
        with self.assertRaises(ValueError):
            Package("p1", 109.9, self.deadline, self.loc)

    def test_invalid_package_too_large(self):
        with self.assertRaises(ValueError):
            Package("p1", 10_000.1, self.deadline, self.loc)

    def test_size_cubic_feet_conversion(self):
        pkg = Package("p1", CUBIC_INCHES_PER_CUBIC_FOOT, self.deadline, self.loc)
        self.assertAlmostEqual(pkg.size_cubic_feet, 1.0)

    def test_urgency_hours(self):
        now = datetime(2024, 1, 1, 8, 0, 0)
        deadline = now + timedelta(hours=10)
        pkg = Package("p1", 500, deadline, self.loc)
        self.assertAlmostEqual(pkg.urgency_hours(now), 10.0, delta=0.01)


class TestDriver(unittest.TestCase):
    def setUp(self):
        self.depot = Location("Depot", 0, 0)

    def test_valid_driver_minimum_vehicle(self):
        driver = Driver("d1", 50.0, self.depot)
        self.assertAlmostEqual(driver.vehicle_size_cubic_feet, 50.0)

    def test_valid_driver_maximum_vehicle(self):
        driver = Driver("d1", 90.0, self.depot)
        self.assertAlmostEqual(driver.vehicle_size_cubic_feet, 90.0)

    def test_invalid_driver_vehicle_too_small(self):
        with self.assertRaises(ValueError):
            Driver("d1", 49.9, self.depot)

    def test_invalid_driver_vehicle_too_large(self):
        with self.assertRaises(ValueError):
            Driver("d1", 90.1, self.depot)

    def test_vehicle_size_cubic_inches_conversion(self):
        driver = Driver("d1", 50.0, self.depot)
        self.assertAlmostEqual(
            driver.vehicle_size_cubic_inches, 50.0 * CUBIC_INCHES_PER_CUBIC_FOOT
        )


class TestRoute(unittest.TestCase):
    def setUp(self):
        self.depot = Location("Depot", 0, 0)
        self.driver = Driver("d1", 70.0, self.depot)
        self.now = datetime(2024, 1, 1, 8, 0, 0)

    def test_empty_route_is_valid(self):
        route = Route(driver=self.driver)
        self.assertEqual(route.total_distance, 0.0)
        self.assertEqual(route.total_volume_cubic_inches, 0.0)
        self.assertTrue(route.is_capacity_valid())
        self.assertEqual(route.deadline_violations(), [])
        self.assertTrue(route.is_valid())

    def test_route_totals(self):
        loc = Location("A", 3, 4)  # 5 miles from depot
        pkg = Package("p1", 500.0, self.now + timedelta(hours=24), loc)
        stop = Stop(
            package=pkg,
            arrival_time=self.now + timedelta(hours=1),
            distance_from_previous=5.0,
        )
        route = Route(driver=self.driver, stops=[stop])
        self.assertAlmostEqual(route.total_distance, 5.0)
        self.assertAlmostEqual(route.total_volume_cubic_inches, 500.0)
        self.assertTrue(route.is_valid())

    def test_capacity_violation(self):
        loc = Location("A", 5, 5)
        deadline = self.now + timedelta(hours=24)
        # driver capacity = 70 * 1728 = 120,960 cu in
        # 13 × 10,000 = 130,000 > 120,960
        stops = [
            Stop(
                package=Package(f"p{i}", 10_000.0, deadline, loc),
                arrival_time=deadline - timedelta(hours=1),
                distance_from_previous=1.0,
            )
            for i in range(13)
        ]
        route = Route(driver=self.driver, stops=stops)
        self.assertFalse(route.is_capacity_valid())
        self.assertFalse(route.is_valid())

    def test_deadline_violation(self):
        loc = Location("A", 5, 5)
        deadline = self.now + timedelta(hours=1)
        pkg = Package("p1", 500.0, deadline, loc)
        # Arrives two hours after deadline
        stop = Stop(
            package=pkg,
            arrival_time=self.now + timedelta(hours=3),
            distance_from_previous=1.0,
        )
        route = Route(driver=self.driver, stops=[stop])
        violations = route.deadline_violations()
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].id, "p1")
        self.assertFalse(route.is_valid())

    def test_multiple_stops_accumulate_distance(self):
        deadline = self.now + timedelta(hours=24)
        stops = [
            Stop(
                package=Package(f"p{i}", 200.0, deadline, Location(f"L{i}", i, 0)),
                arrival_time=self.now + timedelta(minutes=10 * (i + 1)),
                distance_from_previous=1.0,
            )
            for i in range(5)
        ]
        route = Route(driver=self.driver, stops=stops)
        self.assertAlmostEqual(route.total_distance, 5.0)
        self.assertAlmostEqual(route.total_volume_cubic_inches, 1000.0)
