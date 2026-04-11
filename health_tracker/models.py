"""Data models for health tracking."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class UserProfile:
    name: str
    age: int
    weight_kg: float
    height_cm: float
    gender: str  # "male" or "female"

    @property
    def bmi(self) -> float:
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m ** 2), 1)

    @property
    def max_heart_rate(self) -> int:
        """Estimated max heart rate using Tanaka formula."""
        return int(208 - (0.7 * self.age))

    @property
    def resting_heart_rate_target(self) -> tuple[int, int]:
        """Healthy resting heart rate range based on age."""
        if self.age < 30:
            return (60, 80)
        elif self.age < 50:
            return (60, 85)
        else:
            return (60, 90)

    @property
    def heart_rate_zones(self) -> dict[str, tuple[int, int]]:
        """Heart rate training zones based on max heart rate."""
        mhr = self.max_heart_rate
        return {
            "rest": (50, int(mhr * 0.5)),
            "fat_burn": (int(mhr * 0.5), int(mhr * 0.6)),
            "cardio": (int(mhr * 0.6), int(mhr * 0.7)),
            "aerobic": (int(mhr * 0.7), int(mhr * 0.8)),
            "anaerobic": (int(mhr * 0.8), int(mhr * 0.9)),
            "max_effort": (int(mhr * 0.9), mhr),
        }


@dataclass
class HealthHabit:
    date: str
    water_intake_liters: float = 0.0
    sleep_hours: float = 0.0
    steps: int = 0
    fruits_vegetables_servings: int = 0
    meditation_minutes: int = 0
    alcohol_drinks: int = 0
    smoking: bool = False
    notes: str = ""


@dataclass
class Workout:
    date: str
    workout_type: str  # e.g., "running", "cycling", "weightlifting", "swimming", "yoga"
    duration_minutes: int = 0
    intensity: str = "moderate"  # "light", "moderate", "vigorous"
    distance_km: Optional[float] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight_lifted_kg: Optional[float] = None
    notes: str = ""


@dataclass
class HeartRateEntry:
    date: str
    time: str
    heart_rate_bpm: int
    context: str = "resting"  # "resting", "during_workout", "post_workout", "morning", "evening"


@dataclass
class DailyRecord:
    date: str
    health_habits: Optional[HealthHabit] = None
    workouts: list[Workout] = field(default_factory=list)
    heart_rate_readings: list[HeartRateEntry] = field(default_factory=list)
    total_calories_burned: float = 0.0
