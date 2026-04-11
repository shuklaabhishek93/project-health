"""Daily summary generation with age-based insights."""

from .models import UserProfile, DailyRecord
from .calculator import (
    calculate_calories_burned,
    calculate_steps_calories,
    calculate_bmr,
    analyze_heart_rate,
    get_age_based_recommendations,
)


def generate_daily_summary(profile: UserProfile, record: DailyRecord) -> str:
    """Generate a comprehensive daily health summary."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"  DAILY HEALTH SUMMARY - {record.date}")
    lines.append(f"  {profile.name} | Age: {profile.age} | BMI: {profile.bmi}")
    lines.append("=" * 60)

    # BMR info
    bmr = calculate_bmr(profile)
    lines.append(f"\n  Basal Metabolic Rate (BMR): {bmr} cal/day")

    # Health Habits Section
    lines.append("\n" + "-" * 60)
    lines.append("  HEALTH HABITS")
    lines.append("-" * 60)

    if record.health_habits:
        habits = record.health_habits
        recommendations = get_age_based_recommendations(profile)

        water_target = recommendations["water_liters"]
        water_status = "OK" if habits.water_intake_liters >= water_target else "LOW"
        lines.append(f"  Water Intake:     {habits.water_intake_liters}L / {water_target}L target [{water_status}]")

        sleep_target = recommendations["sleep_hours"]
        lines.append(f"  Sleep:            {habits.sleep_hours} hrs (recommended: {sleep_target} hrs)")

        lines.append(f"  Steps:            {habits.steps:,}")
        step_calories = calculate_steps_calories(profile, habits.steps)
        lines.append(f"  Calories (steps): {step_calories} cal")

        lines.append(f"  Fruits/Veggies:   {habits.fruits_vegetables_servings} servings (target: 5+)")
        lines.append(f"  Meditation:       {habits.meditation_minutes} minutes")

        if habits.alcohol_drinks > 0:
            lines.append(f"  Alcohol:          {habits.alcohol_drinks} drinks (limit: 1-2/day)")
        if habits.smoking:
            lines.append("  Smoking:          Yes (strongly consider quitting)")

        if habits.notes:
            lines.append(f"  Notes:            {habits.notes}")
    else:
        lines.append("  No health habits logged for today.")

    # Workout Section
    lines.append("\n" + "-" * 60)
    lines.append("  WORKOUTS")
    lines.append("-" * 60)

    total_workout_calories = 0.0
    total_workout_minutes = 0

    if record.workouts:
        for i, workout in enumerate(record.workouts, 1):
            calories = calculate_calories_burned(profile, workout)
            total_workout_calories += calories
            total_workout_minutes += workout.duration_minutes

            lines.append(f"\n  Workout #{i}: {workout.workout_type.title()}")
            lines.append(f"    Duration:    {workout.duration_minutes} min")
            lines.append(f"    Intensity:   {workout.intensity.title()}")
            if workout.distance_km:
                lines.append(f"    Distance:    {workout.distance_km} km")
            if workout.sets and workout.reps:
                lines.append(f"    Sets/Reps:   {workout.sets} x {workout.reps}")
            if workout.weight_lifted_kg:
                lines.append(f"    Weight:      {workout.weight_lifted_kg} kg")
            lines.append(f"    Calories:    {calories} cal")

        lines.append(f"\n  Total Workout Time:     {total_workout_minutes} min")
        lines.append(f"  Total Workout Calories: {total_workout_calories} cal")
    else:
        lines.append("  No workouts logged for today.")

    # Heart Rate Section
    lines.append("\n" + "-" * 60)
    lines.append("  HEART RATE")
    lines.append("-" * 60)
    lines.append(f"  Max Heart Rate (estimated): {profile.max_heart_rate} bpm")
    lines.append(f"  Healthy Resting Range:      {profile.resting_heart_rate_target[0]}-{profile.resting_heart_rate_target[1]} bpm")

    if record.heart_rate_readings:
        hr_values = [r.heart_rate_bpm for r in record.heart_rate_readings]
        avg_hr = sum(hr_values) / len(hr_values)
        lines.append(f"\n  Readings Today: {len(hr_values)}")
        lines.append(f"  Average:        {avg_hr:.0f} bpm")
        lines.append(f"  Lowest:         {min(hr_values)} bpm")
        lines.append(f"  Highest:        {max(hr_values)} bpm")

        # Analyze each reading
        lines.append("\n  Detailed Readings:")
        for reading in record.heart_rate_readings:
            analysis = analyze_heart_rate(profile, reading)
            lines.append(f"    {reading.time} ({reading.context}): {reading.heart_rate_bpm} bpm "
                         f"[{analysis['zone'].replace('_', ' ').title()}] "
                         f"({analysis['percentage_of_max']}% of max)")
            if analysis["recommendation"]:
                lines.append(f"      -> {analysis['recommendation']}")
    else:
        lines.append("  No heart rate readings logged for today.")

    # Total Calorie Summary
    lines.append("\n" + "-" * 60)
    lines.append("  CALORIE SUMMARY")
    lines.append("-" * 60)

    step_cal = calculate_steps_calories(profile, record.health_habits.steps) if record.health_habits else 0
    total_active_calories = total_workout_calories + step_cal
    total_calories = bmr + total_active_calories

    lines.append(f"  BMR (resting):        {bmr} cal")
    lines.append(f"  Steps calories:       {step_cal} cal")
    lines.append(f"  Workout calories:     {total_workout_calories} cal")
    lines.append(f"  Total Active Burn:    {total_active_calories} cal")
    lines.append(f"  TOTAL DAILY BURN:     {total_calories} cal")

    # Update record
    record.total_calories_burned = total_calories

    # Age-Based Recommendations
    lines.append("\n" + "-" * 60)
    lines.append(f"  AGE-BASED INSIGHTS (Age: {profile.age})")
    lines.append("-" * 60)

    recommendations = get_age_based_recommendations(profile)
    lines.append(f"  Weekly Exercise Target: {recommendations['exercise_minutes_per_week']} min")
    lines.append(f"  Recommended Workouts:   {', '.join(recommendations['recommended_workouts'])}")
    lines.append(f"  Focus Areas:")
    for area in recommendations["focus_areas"]:
        lines.append(f"    - {area}")
    lines.append(f"  Note: {recommendations['caution']}")

    # Health Score
    lines.append("\n" + "-" * 60)
    lines.append("  DAILY HEALTH SCORE")
    lines.append("-" * 60)

    score = calculate_health_score(profile, record)
    lines.append(f"  Score: {score}/100")
    lines.append(f"  Rating: {get_score_rating(score)}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def calculate_health_score(profile: UserProfile, record: DailyRecord) -> int:
    """Calculate a daily health score out of 100."""
    score = 0
    recommendations = get_age_based_recommendations(profile)

    if record.health_habits:
        habits = record.health_habits

        # Water (15 points)
        water_target = recommendations["water_liters"]
        water_ratio = min(habits.water_intake_liters / water_target, 1.0)
        score += int(water_ratio * 15)

        # Sleep (20 points)
        sleep_range = recommendations["sleep_hours"]
        min_sleep = int(sleep_range.split("-")[0])
        max_sleep = int(sleep_range.split("-")[1])
        if min_sleep <= habits.sleep_hours <= max_sleep:
            score += 20
        elif habits.sleep_hours >= min_sleep - 1:
            score += 10

        # Steps (15 points) - target 10,000 steps
        step_ratio = min(habits.steps / 10000, 1.0)
        score += int(step_ratio * 15)

        # Fruits/Veggies (10 points)
        fv_ratio = min(habits.fruits_vegetables_servings / 5, 1.0)
        score += int(fv_ratio * 10)

        # Meditation (5 points)
        if habits.meditation_minutes >= 10:
            score += 5
        elif habits.meditation_minutes > 0:
            score += 2

        # No smoking bonus (5 points)
        if not habits.smoking:
            score += 5

    # Workouts (25 points)
    if record.workouts:
        total_minutes = sum(w.duration_minutes for w in record.workouts)
        # Target: ~30 min per day (150 min/week / 5 days)
        workout_ratio = min(total_minutes / 30, 1.0)
        score += int(workout_ratio * 25)

    # Heart rate tracking (5 points for logging)
    if record.heart_rate_readings:
        score += 5

    return min(score, 100)


def get_score_rating(score: int) -> str:
    """Convert numeric score to a rating."""
    if score >= 90:
        return "Excellent! Keep up the amazing work!"
    elif score >= 75:
        return "Great! You're doing well."
    elif score >= 60:
        return "Good. Room for improvement in some areas."
    elif score >= 40:
        return "Fair. Try to improve your habits gradually."
    else:
        return "Needs attention. Start with small, consistent changes."
