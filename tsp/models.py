"""Core data models for the TSP package routing system."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

# Unit conversion constants
CUBIC_INCHES_PER_CUBIC_FOOT: float = 1728.0

# Default driving speed used when converting distance to travel time
AVERAGE_SPEED_MPH: float = 30.0

# Package size limits (cubic inches)
PACKAGE_MIN_CUBIC_INCHES: float = 110.0
PACKAGE_MAX_CUBIC_INCHES: float = 10_000.0

# Vehicle size limits (cubic feet)
VEHICLE_MIN_CUBIC_FEET: float = 50.0
VEHICLE_MAX_CUBIC_FEET: float = 90.0


@dataclass
class Location:
    """A named point in 2-D space (coordinates are in miles)."""

    name: str
    x: float
    y: float

    def distance_to(self, other: Location) -> float:
        """Return Euclidean distance in miles."""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def travel_time_to(
        self, other: Location, speed_mph: float = AVERAGE_SPEED_MPH
    ) -> float:
        """Return travel time in hours at *speed_mph*."""
        return self.distance_to(other) / speed_mph


@dataclass
class Package:
    """A package that must be delivered by a deadline."""

    id: str
    size_cubic_inches: float
    arrive_by: datetime
    destination: Location

    def __post_init__(self) -> None:
        if not (PACKAGE_MIN_CUBIC_INCHES <= self.size_cubic_inches <= PACKAGE_MAX_CUBIC_INCHES):
            raise ValueError(
                f"Package size must be between {PACKAGE_MIN_CUBIC_INCHES} and "
                f"{PACKAGE_MAX_CUBIC_INCHES} cu in, got {self.size_cubic_inches}"
            )

    @property
    def size_cubic_feet(self) -> float:
        return self.size_cubic_inches / CUBIC_INCHES_PER_CUBIC_FOOT

    def urgency_hours(self, now: datetime) -> float:
        """Hours remaining until the delivery deadline."""
        return (self.arrive_by - now).total_seconds() / 3600.0


@dataclass
class Driver:
    """A delivery driver with a fixed-capacity vehicle."""

    id: str
    vehicle_size_cubic_feet: float
    depot: Location

    def __post_init__(self) -> None:
        if not (VEHICLE_MIN_CUBIC_FEET <= self.vehicle_size_cubic_feet <= VEHICLE_MAX_CUBIC_FEET):
            raise ValueError(
                f"Vehicle size must be between {VEHICLE_MIN_CUBIC_FEET} and "
                f"{VEHICLE_MAX_CUBIC_FEET} cu ft, got {self.vehicle_size_cubic_feet}"
            )

    @property
    def vehicle_size_cubic_inches(self) -> float:
        return self.vehicle_size_cubic_feet * CUBIC_INCHES_PER_CUBIC_FOOT


@dataclass
class Stop:
    """A single delivery stop on a route."""

    package: Package
    arrival_time: datetime
    distance_from_previous: float  # miles


@dataclass
class Route:
    """An ordered sequence of delivery stops assigned to one driver."""

    driver: Driver
    stops: List[Stop] = field(default_factory=list)

    @property
    def total_distance(self) -> float:
        """Total route distance in miles."""
        return sum(stop.distance_from_previous for stop in self.stops)

    @property
    def total_volume_cubic_inches(self) -> float:
        return sum(stop.package.size_cubic_inches for stop in self.stops)

    @property
    def total_volume_cubic_feet(self) -> float:
        return self.total_volume_cubic_inches / CUBIC_INCHES_PER_CUBIC_FOOT

    def is_capacity_valid(self) -> bool:
        """Return True when the total cargo fits inside the vehicle."""
        return self.total_volume_cubic_inches <= self.driver.vehicle_size_cubic_inches

    def deadline_violations(self) -> List[Package]:
        """Return packages whose arrival time exceeds their deadline."""
        return [
            stop.package
            for stop in self.stops
            if stop.arrival_time > stop.package.arrive_by
        ]

    def is_valid(self) -> bool:
        """Return True when the route satisfies all capacity and deadline constraints."""
        return self.is_capacity_valid() and len(self.deadline_violations()) == 0
