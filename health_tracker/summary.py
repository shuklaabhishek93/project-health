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

    # Data sources
    sources = set()
    for w in record.workouts:
        sources.add(w.source)
    for hr in record.heart_rate_readings:
        sources.add(hr.source)
    if not sources:
        sources.add("manual")
    lines.append(f"  Data Sources: {', '.join(sorted(sources))}")

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

        sleep_target = recommendations["sleep_hours"]
        lines.append(f"  Sleep:            {habits.sleep_hours} hrs (recommended: {sleep_target} hrs)")

        lines.append(f"  Steps:            {habits.steps:,}")
        step_calories = calculate_steps_calories(profile, habits.steps)
        lines.append(f"  Calories (steps): {step_calories} cal")

        if habits.distance_walked_km > 0:
            lines.append(f"  Walk/Run Dist:    {round(habits.distance_walked_km * 0.621371, 2)} mi")
        if habits.flights_climbed > 0:
            lines.append(f"  Flights Climbed:  {habits.flights_climbed}")

        lines.append(f"  Fruits/Veggies:   {habits.fruits_vegetables_servings} servings (target: 5+)")
        lines.append(f"  Meditation:       {habits.meditation_minutes} minutes")

        if habits.alcohol_drinks > 0:
            lines.append(f"  Alcohol:          {habits.alcohol_drinks} drinks (limit: 1-2/day)")
        if habits.smoking:
            lines.append("  Smoking:          Yes (strongly consider quitting)")

        # Show device-reported energy if available
        if habits.active_energy_burned > 0 or habits.resting_energy_burned > 0:
            lines.append(f"\n  Device-Reported Energy (Apple Health/Fitness):")
            if habits.active_energy_burned > 0:
                lines.append(f"    Active Energy:  {habits.active_energy_burned} cal")
            if habits.resting_energy_burned > 0:
                lines.append(f"    Resting Energy: {habits.resting_energy_burned} cal")

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
            # Use device-reported calories if available, otherwise calculate
            if workout.calories_reported and workout.calories_reported > 0:
                calories = workout.calories_reported
            else:
                calories = calculate_calories_burned(profile, workout)
            total_workout_calories += calories
            total_workout_minutes += workout.duration_minutes

            source_tag = f" [{workout.source}]" if workout.source != "manual" else ""
            lines.append(f"\n  Workout #{i}: {workout.workout_type.replace('_', ' ').title()}{source_tag}")
            lines.append(f"    Duration:    {workout.duration_minutes} min")
            lines.append(f"    Intensity:   {workout.intensity.title()}")
            if workout.distance_km:
                lines.append(f"    Distance:    {round(workout.distance_km * 0.621371, 2)} mi")
            if workout.sets and workout.reps:
                lines.append(f"    Sets/Reps:   {workout.sets} x {workout.reps}")
            if workout.weight_lifted_kg:
                lines.append(f"    Weight:      {workout.weight_lifted_kg} kg")
            if workout.avg_heart_rate:
                lines.append(f"    Avg HR:      {workout.avg_heart_rate} bpm")
            lines.append(f"    Calories:    {calories} cal"
                         f"{' (device)' if workout.calories_reported else ' (estimated)'}")
            if workout.notes:
                lines.append(f"    Note:        {workout.notes}")

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

        # Show source breakdown
        hr_sources = set(r.source for r in record.heart_rate_readings)
        if len(hr_sources) > 1 or "manual" not in hr_sources:
            lines.append(f"  Sources:        {', '.join(sorted(hr_sources))}")

        # Analyze each reading
        lines.append("\n  Detailed Readings:")
        for reading in record.heart_rate_readings:
            analysis = analyze_heart_rate(profile, reading)
            src = f" [{reading.source}]" if reading.source != "manual" else ""
            lines.append(f"    {reading.time} ({reading.context}): {reading.heart_rate_bpm} bpm "
                         f"[{analysis['zone'].replace('_', ' ').title()}] "
                         f"({analysis['percentage_of_max']}% of max){src}")
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
