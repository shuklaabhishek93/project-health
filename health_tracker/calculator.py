"""Calorie burn and heart rate calculations."""

from .models import UserProfile, Workout, HeartRateEntry

# MET values (Metabolic Equivalent of Task) for different activities and intensities
MET_VALUES = {
    "running": {"light": 7.0, "moderate": 9.8, "vigorous": 12.8},
    "cycling": {"light": 4.0, "moderate": 6.8, "vigorous": 10.0},
    "swimming": {"light": 5.0, "moderate": 7.0, "vigorous": 10.0},
    "weightlifting": {"light": 3.0, "moderate": 5.0, "vigorous": 6.0},
    "yoga": {"light": 2.5, "moderate": 3.0, "vigorous": 4.0},
    "walking": {"light": 2.5, "moderate": 3.5, "vigorous": 5.0},
    "hiit": {"light": 6.0, "moderate": 8.0, "vigorous": 12.0},
    "dancing": {"light": 3.5, "moderate": 5.5, "vigorous": 7.5},
    "jump_rope": {"light": 8.0, "moderate": 10.0, "vigorous": 12.3},
    "rowing": {"light": 4.8, "moderate": 7.0, "vigorous": 8.5},
    "elliptical": {"light": 4.5, "moderate": 6.0, "vigorous": 7.5},
    "stair_climbing": {"light": 4.0, "moderate": 6.0, "vigorous": 8.0},
    "boxing": {"light": 5.0, "moderate": 7.8, "vigorous": 9.5},
    "pilates": {"light": 3.0, "moderate": 4.0, "vigorous": 5.0},
    "stretching": {"light": 2.0, "moderate": 2.5, "vigorous": 3.0},
}


def calculate_calories_burned(profile: UserProfile, workout: Workout) -> float:
    """
    Calculate calories burned using the MET formula:
    Calories = MET * weight_kg * duration_hours
    """
    workout_type = workout.workout_type.lower()
    intensity = workout.intensity.lower()

    if workout_type in MET_VALUES:
        met = MET_VALUES[workout_type].get(intensity, MET_VALUES[workout_type]["moderate"])
    else:
        # Default MET values for unknown activities
        default_met = {"light": 3.0, "moderate": 5.0, "vigorous": 8.0}
        met = default_met.get(intensity, 5.0)

    duration_hours = workout.duration_minutes / 60.0
    calories = met * profile.weight_kg * duration_hours

    # Age adjustment factor (metabolism slows with age)
    if profile.age > 40:
        age_factor = 1 - ((profile.age - 40) * 0.005)
        calories *= max(age_factor, 0.8)

    return round(calories, 1)


def calculate_steps_calories(profile: UserProfile, steps: int) -> float:
    """Estimate calories burned from steps."""
    # Average: ~0.04 calories per step per kg of body weight, adjusted for stride
    calories_per_step = 0.04 * (profile.weight_kg / 70)
    return round(steps * calories_per_step, 1)


def calculate_bmr(profile: UserProfile) -> float:
    """
    Calculate Basal Metabolic Rate using Mifflin-St Jeor equation.
    This is the calories burned at rest per day.
    """
    if profile.gender.lower() == "male":
        bmr = (10 * profile.weight_kg) + (6.25 * profile.height_cm) - (5 * profile.age) + 5
    else:
        bmr = (10 * profile.weight_kg) + (6.25 * profile.height_cm) - (5 * profile.age) - 161
    return round(bmr, 1)


def analyze_heart_rate(profile: UserProfile, reading: HeartRateEntry) -> dict:
    """Analyze a heart rate reading and provide context."""
    hr = reading.heart_rate_bpm
    zones = profile.heart_rate_zones
    max_hr = profile.max_heart_rate
    resting_range = profile.resting_heart_rate_target

    # Determine which zone the heart rate falls in
    current_zone = "unknown"
    for zone_name, (low, high) in zones.items():
        if low <= hr <= high:
            current_zone = zone_name
            break

    # Assess health status based on context
    status = "normal"
    recommendation = ""

    if reading.context == "resting":
        if hr < resting_range[0]:
            status = "low"
            recommendation = "Your resting heart rate is below normal. This may indicate excellent fitness or a medical condition. Consult a doctor if you feel dizzy or fatigued."
        elif hr > resting_range[1]:
            status = "elevated"
            recommendation = "Your resting heart rate is elevated. Consider stress reduction, better sleep, and regular cardio exercise."
        else:
            status = "healthy"
            recommendation = "Your resting heart rate is within a healthy range for your age."
    elif reading.context == "during_workout":
        if hr > max_hr * 0.95:
            status = "very_high"
            recommendation = "You are near your maximum heart rate. Consider reducing intensity to avoid overexertion."
        elif hr > max_hr * 0.85:
            status = "high_intensity"
            recommendation = "You are in the anaerobic zone. Good for short bursts but avoid prolonged exercise at this level."

    return {
        "heart_rate": hr,
        "zone": current_zone,
        "max_heart_rate": max_hr,
        "percentage_of_max": round((hr / max_hr) * 100, 1),
        "status": status,
        "recommendation": recommendation,
    }


def get_age_based_recommendations(profile: UserProfile) -> dict:
    """Provide health recommendations based on age group."""
    age = profile.age

    if age < 25:
        return {
            "exercise_minutes_per_week": 150,
            "recommended_workouts": ["running", "swimming", "hiit", "weightlifting", "sports"],
            "sleep_hours": "7-9",
            "water_liters": 2.5,
            "focus_areas": [
                "Build cardiovascular endurance",
                "Develop strength foundation",
                "Maintain flexibility",
            ],
            "caution": "Avoid overtraining. Allow adequate recovery between intense sessions.",
        }
    elif age < 35:
        return {
            "exercise_minutes_per_week": 150,
            "recommended_workouts": ["running", "cycling", "weightlifting", "hiit", "yoga"],
            "sleep_hours": "7-9",
            "water_liters": 2.5,
            "focus_areas": [
                "Maintain muscle mass",
                "Prioritize recovery",
                "Include mobility work",
            ],
            "caution": "Metabolism begins to slow. Focus on consistent training over intensity.",
        }
    elif age < 45:
        return {
            "exercise_minutes_per_week": 150,
            "recommended_workouts": ["cycling", "swimming", "weightlifting", "yoga", "walking"],
            "sleep_hours": "7-8",
            "water_liters": 2.5,
            "focus_areas": [
                "Joint health and mobility",
                "Maintain bone density with weight-bearing exercise",
                "Stress management",
            ],
            "caution": "Warm up thoroughly. Recovery takes longer. Monitor heart rate during exercise.",
        }
    elif age < 55:
        return {
            "exercise_minutes_per_week": 150,
            "recommended_workouts": ["walking", "cycling", "swimming", "yoga", "pilates"],
            "sleep_hours": "7-8",
            "water_liters": 2.0,
            "focus_areas": [
                "Cardiovascular health",
                "Balance and stability",
                "Maintain muscle mass to prevent sarcopenia",
            ],
            "caution": "Get regular health checkups. Watch for signs of overexertion. Prioritize low-impact activities.",
        }
    else:
        return {
            "exercise_minutes_per_week": 150,
            "recommended_workouts": ["walking", "swimming", "yoga", "stretching", "pilates"],
            "sleep_hours": "7-8",
            "water_liters": 2.0,
            "focus_areas": [
                "Fall prevention through balance training",
                "Maintain independence and mobility",
                "Social physical activities",
            ],
            "caution": "Consult your physician before new exercise programs. Focus on consistency over intensity.",
        }
