"""Personalized daily health recommendations based on actual user data."""

from .models import UserProfile, DailyRecord


def _bmi_category(bmi: float) -> str:
    if bmi < 18.5:
        return "underweight"
    if bmi < 25:
        return "normal"
    if bmi < 30:
        return "overweight"
    return "obese"


def _sleep_target(age: int) -> tuple[float, float]:
    """Evidence-based sleep targets by age (National Sleep Foundation)."""
    if age < 26:
        return (7.0, 9.0)
    if age < 65:
        return (7.0, 9.0)
    return (7.0, 8.0)


def _step_target(age: int, bmi: float) -> int:
    """Personalized step target based on age and BMI."""
    base = 10000
    if age > 65:
        base = 7000
    elif age > 50:
        base = 8000
    if bmi >= 30:
        base = max(base - 2000, 5000)
    return base


def _weekly_exercise_target(age: int, bmi: float) -> int:
    """Minutes per week (WHO/AHA guidelines)."""
    if bmi >= 30:
        return 200
    if age > 60:
        return 150
    return 150


def generate_personalized_recommendations(
    profile: UserProfile,
    recent_records: list[DailyRecord],
) -> dict:
    """Generate personalized recommendations from profile + recent activity data."""

    bmi = profile.bmi
    bmi_cat = _bmi_category(bmi)
    age = profile.age
    weight_kg = profile.weight_kg
    height_cm = profile.height_cm
    gender = profile.gender.lower()

    sleep_min, sleep_max = _sleep_target(age)
    step_target = _step_target(age, bmi)
    weekly_exercise = _weekly_exercise_target(age, bmi)

    # Analyze recent data
    days_with_data = [r for r in recent_records if r.health_habits or r.workouts]
    num_days = len(days_with_data)

    avg_steps = 0
    avg_sleep = 0.0
    total_workout_min = 0
    workout_days = 0
    workout_types_count: dict[str, int] = {}
    avg_resting_hr = 0
    hr_readings = 0
    total_active_energy = 0.0
    total_flights = 0
    total_distance_km = 0.0

    intensity_count: dict[str, int] = {}
    workout_minutes_by_type: dict[str, int] = {}

    for r in days_with_data:
        if r.health_habits:
            avg_steps += r.health_habits.steps
            avg_sleep += r.health_habits.sleep_hours
            total_active_energy += r.health_habits.active_energy_burned
            total_flights += r.health_habits.flights_climbed
            total_distance_km += r.health_habits.distance_walked_km
        if r.workouts:
            workout_days += 1
            for w in r.workouts:
                total_workout_min += w.duration_minutes
                workout_types_count[w.workout_type] = workout_types_count.get(w.workout_type, 0) + 1
                workout_minutes_by_type[w.workout_type] = workout_minutes_by_type.get(w.workout_type, 0) + w.duration_minutes
                intensity_count[w.intensity] = intensity_count.get(w.intensity, 0) + 1
        for hr in r.heart_rate_readings:
            if hr.context == "resting":
                avg_resting_hr += hr.heart_rate_bpm
                hr_readings += 1

    if num_days > 0:
        avg_steps = round(avg_steps / num_days)
        avg_sleep = round(avg_sleep / num_days, 1)
        avg_active_energy = round(total_active_energy / num_days, 1)
        avg_distance_mi = round((total_distance_km / num_days) * 0.621371, 2)
    else:
        avg_active_energy = 0
        avg_distance_mi = 0

    if hr_readings > 0:
        avg_resting_hr = round(avg_resting_hr / hr_readings)

    weekly_workout_min = round(total_workout_min * 7 / max(num_days, 1))

    # Build personalized insights
    insights = []
    warnings = []
    achievements = []

    # --- BMI Assessment ---
    height_m = height_cm / 100
    if bmi_cat == "underweight":
        ideal_low = round(18.5 * height_m * height_m, 1)
        insights.append(f"Your BMI is {bmi} (underweight). Target weight: {ideal_low}-{round(24.9 * height_m * height_m, 1)} kg. Focus on nutrient-dense meals and strength training to build lean mass.")
    elif bmi_cat == "normal":
        achievements.append(f"BMI of {bmi} is in the healthy range. Maintain with balanced nutrition and regular activity.")
    elif bmi_cat == "overweight":
        ideal_high = round(24.9 * height_m * height_m, 1)
        deficit = round(weight_kg - ideal_high, 1)
        insights.append(f"Your BMI is {bmi} (overweight by ~{deficit} kg / {round(deficit * 2.205, 1)} lbs). A 500 cal/day deficit can help lose ~0.5 kg/week safely. Combine cardio with strength training.")
    elif bmi_cat == "obese":
        ideal_high = round(24.9 * height_m * height_m, 1)
        deficit = round(weight_kg - ideal_high, 1)
        warnings.append(f"BMI of {bmi} indicates obesity. Target: lose {deficit} kg ({round(deficit * 2.205, 1)} lbs) gradually. Consult a healthcare provider for a personalized plan. Start with walking and low-impact exercises.")

    # --- Sleep Analysis ---
    if num_days > 0:
        if avg_sleep < sleep_min:
            gap = round(sleep_min - avg_sleep, 1)
            warnings.append(f"You're averaging {avg_sleep} hrs of sleep — {gap} hrs below the {sleep_min}-{sleep_max} hr recommendation for your age ({age}). Poor sleep increases cortisol, reduces recovery, and raises injury risk. Try a consistent bedtime routine.")
        elif avg_sleep > sleep_max + 1:
            warnings.append(f"Averaging {avg_sleep} hrs of sleep is above the recommended {sleep_max} hrs. Oversleeping can indicate underlying health issues. Monitor energy levels and consult a doctor if fatigued.")
        elif avg_sleep >= sleep_min:
            achievements.append(f"Great sleep averaging {avg_sleep} hrs/night (target: {sleep_min}-{sleep_max} hrs).")

    # --- Steps Analysis ---
    if num_days > 0:
        step_pct = round(avg_steps / step_target * 100)
        if avg_steps < step_target * 0.5:
            warnings.append(f"Averaging {avg_steps:,} steps/day — only {step_pct}% of your {step_target:,} target. Sedentary behavior increases cardiovascular risk. Start with short 10-min walks after meals.")
        elif avg_steps < step_target:
            insights.append(f"Averaging {avg_steps:,} steps/day ({step_pct}% of {step_target:,} target). Add {step_target - avg_steps:,} more daily steps — try parking farther or taking stairs.")
        else:
            achievements.append(f"Excellent step count: {avg_steps:,}/day exceeds your {step_target:,} target.")

    # --- Exercise Analysis ---
    if num_days > 0:
        exercise_pct = round(weekly_workout_min / weekly_exercise * 100)
        if weekly_workout_min < weekly_exercise * 0.5:
            warnings.append(f"Projected {weekly_workout_min} min/week of exercise — well below the {weekly_exercise} min/week guideline (WHO/AHA). Try at least 3 sessions of 20+ minutes.")
        elif weekly_workout_min < weekly_exercise:
            insights.append(f"On track for {weekly_workout_min} min/week ({exercise_pct}% of {weekly_exercise} min target). Add {round((weekly_exercise - weekly_workout_min) / 3)} min to 3 sessions to hit your goal.")
        else:
            achievements.append(f"Meeting exercise goals: ~{weekly_workout_min} min/week (target: {weekly_exercise} min).")

    # --- Workout Balance Analysis ---
    if workout_types_count:
        balance = _analyze_workout_balance(
            age, gender, bmi, weight_kg, workout_types_count,
            total_workout_min, workout_days, num_days,
            intensity_count, workout_minutes_by_type,
        )
        insights.extend(balance["insights"])
        warnings.extend(balance["warnings"])
        achievements.extend(balance["achievements"])

    # --- Heart Rate ---
    if avg_resting_hr > 0:
        resting_target = profile.resting_heart_rate_target
        if avg_resting_hr < resting_target[0]:
            achievements.append(f"Resting HR of {avg_resting_hr} bpm indicates excellent cardiovascular fitness.")
        elif avg_resting_hr > resting_target[1]:
            insights.append(f"Resting HR of {avg_resting_hr} bpm is above the healthy range ({resting_target[0]}-{resting_target[1]} bpm). Regular cardio, stress management, and adequate sleep can lower it over time.")
        else:
            achievements.append(f"Resting heart rate of {avg_resting_hr} bpm is in the healthy range ({resting_target[0]}-{resting_target[1]}).")

    # --- Active Energy ---
    if avg_active_energy > 0:
        calorie_target = _daily_calorie_burn_target(age, gender, weight_kg, bmi)
        if avg_active_energy < calorie_target * 0.5:
            insights.append(f"Averaging {avg_active_energy} active cal/day. Target ~{calorie_target} cal for your profile. Increase activity intensity or duration.")
        elif avg_active_energy >= calorie_target:
            achievements.append(f"Active energy burn of {avg_active_energy} cal/day meets your target of {calorie_target} cal.")

    # --- Age-Specific Tips ---
    age_tips = _age_specific_tips(age, gender, bmi, workout_types_count)
    insights.extend(age_tips)

    # --- Compile daily targets ---
    targets = {
        "steps": step_target,
        "sleep_hours": f"{sleep_min}-{sleep_max}",
        "exercise_min_per_week": weekly_exercise,
        "exercise_days_per_week": max(3, min(5, workout_days + 1)) if workout_days < 5 else 5,
    }

    # --- Compile recommended workouts ---
    recommended = _recommend_workouts(age, gender, bmi, workout_types_count)

    return {
        "targets": targets,
        "recommended_workouts": recommended,
        "achievements": achievements,
        "insights": insights,
        "warnings": warnings,
        "stats": {
            "avg_steps": avg_steps,
            "avg_sleep": avg_sleep,
            "avg_distance_miles": avg_distance_mi,
            "weekly_workout_min": weekly_workout_min,
            "workout_days": workout_days,
            "total_days_analyzed": num_days,
            "bmi": bmi,
            "bmi_category": bmi_cat,
            "avg_resting_hr": avg_resting_hr if avg_resting_hr > 0 else None,
            "avg_active_energy": avg_active_energy,
        },
    }


CARDIO_TYPES = {"running", "cycling", "swimming", "rowing", "elliptical", "jump_rope", "walking", "hiking", "stair_climbing", "dancing"}
STRENGTH_TYPES = {"weightlifting"}
FLEXIBILITY_TYPES = {"yoga", "pilates", "stretching"}
HIIT_TYPES = {"hiit", "boxing", "cross_training"}


def _analyze_workout_balance(
    age: int, gender: str, bmi: float, weight_kg: float,
    type_counts: dict[str, int],
    total_min: int, workout_days: int, num_days: int,
    intensity_counts: dict[str, int],
    minutes_by_type: dict[str, int],
) -> dict:
    insights = []
    warnings = []
    achievements = []

    total_sessions = sum(type_counts.values())
    if total_sessions == 0:
        return {"insights": insights, "warnings": warnings, "achievements": achievements}

    # Categorize workouts
    cardio_sessions = sum(type_counts.get(t, 0) for t in CARDIO_TYPES)
    strength_sessions = sum(type_counts.get(t, 0) for t in STRENGTH_TYPES)
    flexibility_sessions = sum(type_counts.get(t, 0) for t in FLEXIBILITY_TYPES)
    hiit_sessions = sum(type_counts.get(t, 0) for t in HIIT_TYPES)

    cardio_min = sum(minutes_by_type.get(t, 0) for t in CARDIO_TYPES)
    strength_min = sum(minutes_by_type.get(t, 0) for t in STRENGTH_TYPES)
    flexibility_min = sum(minutes_by_type.get(t, 0) for t in FLEXIBILITY_TYPES)

    cardio_pct = round(cardio_sessions / total_sessions * 100)
    strength_pct = round(strength_sessions / total_sessions * 100)

    # --- Dominance detection ---
    top_type = max(type_counts, key=type_counts.get)
    top_count = type_counts[top_type]
    top_pct = round(top_count / total_sessions * 100)
    top_name = top_type.replace("_", " ")

    if top_pct >= 70 and total_sessions >= 4:
        pivot = _get_pivot_suggestion(top_type, age, bmi, weight_kg, gender)
        warnings.append(
            f"{top_pct}% of your workouts are {top_name} ({top_count}/{total_sessions} sessions). "
            f"Over-reliance on one exercise increases overuse injury risk and limits overall fitness gains. "
            f"Pivot suggestion: {pivot}"
        )
    elif top_pct >= 50 and total_sessions >= 4:
        pivot = _get_pivot_suggestion(top_type, age, bmi, weight_kg, gender)
        insights.append(
            f"{top_name} dominates your routine ({top_pct}% of sessions). "
            f"Consider balancing with: {pivot}"
        )

    # --- Category balance ---
    # Ideal split: ~40-50% cardio, 25-30% strength, 15-20% flexibility, rest HIIT
    if total_sessions >= 3:
        if strength_sessions == 0:
            if bmi >= 25:
                warnings.append(
                    f"No strength training detected. With a BMI of {bmi}, adding 2-3 weightlifting sessions/week "
                    f"is critical — it boosts metabolism by building lean muscle, which burns ~50 extra cal/day per "
                    f"kg of muscle gained. This accelerates fat loss more effectively than cardio alone."
                )
            else:
                insights.append(
                    "No strength training in your routine. Adults lose 3-5% muscle mass per decade after 30. "
                    "Add 2 sessions/week to maintain bone density, posture, and metabolic rate."
                )

        if cardio_sessions == 0:
            warnings.append(
                "No cardio workouts detected. The AHA recommends 150 min/week of moderate cardio for heart health. "
                f"{'Start with walking or swimming (low-impact for your joints).' if bmi >= 30 else 'Try running, cycling, or swimming.'}"
            )

        if flexibility_sessions == 0 and total_sessions >= 5:
            insights.append(
                "No flexibility/mobility work. Add 1-2 yoga or stretching sessions per week — "
                "it reduces injury risk, improves range of motion, and speeds recovery between intense workouts."
            )

        if cardio_pct > 70 and strength_pct == 0:
            insights.append(
                f"Your routine is {cardio_pct}% cardio with no strength training. "
                f"This can lead to muscle loss over time. A balanced approach "
                f"(60% cardio / 30% strength / 10% flexibility) is optimal for "
                f"{'weight management' if bmi >= 25 else 'overall fitness'}."
            )

    # --- Intensity balance ---
    total_intensity = sum(intensity_counts.values())
    if total_intensity >= 3:
        vigorous = intensity_counts.get("vigorous", 0)
        light = intensity_counts.get("light", 0)
        vigorous_pct = round(vigorous / total_intensity * 100)
        light_pct = round(light / total_intensity * 100)

        if vigorous_pct > 60:
            warnings.append(
                f"{vigorous_pct}% of your workouts are vigorous intensity. "
                f"Too much high-intensity training without recovery increases cortisol and injury risk. "
                f"Follow the 80/20 rule: 80% low-moderate, 20% high intensity."
            )
        elif light_pct > 80:
            insights.append(
                f"{light_pct}% of your workouts are light intensity. "
                f"Add 1-2 moderate or vigorous sessions/week to improve cardiovascular fitness and calorie burn."
            )

    # --- BMI-specific workout suggestions ---
    if bmi >= 30 and total_sessions >= 2:
        has_hiit = hiit_sessions > 0 or any(t in type_counts for t in HIIT_TYPES)
        if not has_hiit and strength_sessions == 0:
            insights.append(
                f"For your BMI ({bmi}), the most effective routine combines: "
                f"walking/swimming (3x/week for cardiovascular base), "
                f"weightlifting (2x/week to boost resting metabolism), and "
                f"one moderate HIIT session for calorie afterburn. "
                f"This burns more fat long-term than cardio alone."
            )
    elif bmi < 18.5 and total_sessions >= 2:
        if cardio_pct > 50 and strength_sessions == 0:
            warnings.append(
                f"With a BMI of {bmi} (underweight), heavy cardio without strength training "
                f"can lead to further weight loss. Prioritize weightlifting and reduce long cardio sessions. "
                f"Focus on compound lifts (squats, deadlifts, bench press) with progressive overload."
            )

    # --- Good balance achievement ---
    if total_sessions >= 4:
        unique = len(type_counts)
        has_all_three = cardio_sessions > 0 and strength_sessions > 0 and flexibility_sessions > 0
        if has_all_three:
            achievements.append(
                f"Well-balanced routine with cardio ({cardio_sessions}x), strength ({strength_sessions}x), "
                f"and flexibility ({flexibility_sessions}x) — this covers all fitness pillars."
            )
        elif unique >= 3 and top_pct < 50:
            achievements.append(
                f"Good workout variety: {unique} different types across {total_sessions} sessions."
            )

    return {"insights": insights, "warnings": warnings, "achievements": achievements}


def _get_pivot_suggestion(dominant_type: str, age: int, bmi: float, weight_kg: float, gender: str) -> str:
    dominant = dominant_type.lower()
    name = dominant.replace("_", " ")

    if dominant in CARDIO_TYPES:
        if bmi >= 25:
            return (
                f"Replace 2 {name} sessions/week with weightlifting. "
                f"Strength training raises your resting metabolic rate — "
                f"at {weight_kg} kg, adding 2 kg of muscle would burn ~100 extra cal/day at rest."
            )
        return (
            f"Swap 1-2 {name} sessions for weightlifting or yoga. "
            f"Cross-training prevents overuse injuries common with repetitive {name}."
        )

    if dominant in STRENGTH_TYPES:
        if age > 40:
            return (
                "Add 2-3 cardio sessions (cycling or swimming) for heart health, "
                "plus 1 yoga/stretching session for joint mobility and recovery."
            )
        return (
            "Add 2 cardio sessions (running or cycling) to improve cardiovascular endurance, "
            "and 1 flexibility session to maintain range of motion."
        )

    if dominant in HIIT_TYPES:
        return (
            "HIIT is great but hard on the body. Limit to 2-3x/week max. "
            "Add steady-state cardio (walking, cycling) for active recovery days "
            "and strength training for balanced muscle development."
        )

    if dominant in FLEXIBILITY_TYPES:
        return (
            f"{'Yoga and stretching' if dominant == 'yoga' else name.title()} builds flexibility but not strength or cardio fitness. "
            f"Add 2 strength sessions and 2 cardio sessions per week for complete fitness."
        )

    return "Try mixing in cardio, strength, and flexibility work for a balanced routine."


def _daily_calorie_burn_target(age: int, gender: str, weight_kg: float, bmi: float) -> int:
    if gender == "male":
        base = 300 if bmi < 25 else 400
    else:
        base = 250 if bmi < 25 else 350
    if age > 50:
        base = round(base * 0.85)
    return base


def _suggest_missing_workouts(age: int, bmi: float, current: dict) -> list[str]:
    categories = {
        "cardio": {"running", "cycling", "swimming", "rowing", "elliptical", "jump_rope"},
        "strength": {"weightlifting"},
        "flexibility": {"yoga", "pilates", "stretching"},
        "balance": {"yoga", "pilates"},
    }
    has_cardio = any(t in categories["cardio"] for t in current)
    has_strength = any(t in categories["strength"] for t in current)
    has_flexibility = any(t in categories["flexibility"] for t in current)

    suggestions = []
    if not has_cardio:
        suggestions.append("cycling or swimming" if age > 50 else "running or cycling")
    if not has_strength:
        suggestions.append("weightlifting (2-3x/week for bone density and metabolism)")
    if not has_flexibility:
        suggestions.append("yoga or stretching (improves recovery and mobility)")
    return suggestions if suggestions else ["try a new activity like rowing or boxing"]


def _recommend_workouts(age: int, gender: str, bmi: float, current: dict) -> list[str]:
    if age < 30:
        pool = ["running", "hiit", "weightlifting", "swimming", "cycling"]
    elif age < 45:
        pool = ["running", "cycling", "weightlifting", "yoga", "swimming"]
    elif age < 60:
        pool = ["cycling", "swimming", "weightlifting", "yoga", "walking"]
    else:
        pool = ["walking", "swimming", "yoga", "pilates", "stretching"]

    if bmi >= 30:
        pool = [w for w in pool if w not in ("running", "hiit", "jump_rope")]
        if "walking" not in pool:
            pool.insert(0, "walking")
        if "swimming" not in pool:
            pool.insert(1, "swimming")

    return pool[:5]


def _age_specific_tips(age: int, gender: str, bmi: float, workouts: dict) -> list[str]:
    tips = []
    has_strength = "weightlifting" in workouts

    if age >= 30 and not has_strength:
        tips.append("After 30, you lose 3-5% muscle mass per decade. Add strength training 2-3x/week to maintain metabolism and bone density.")

    if age >= 40:
        tips.append("Recovery takes longer after 40. Allow 48 hrs between intense sessions targeting the same muscle groups. Prioritize sleep for recovery.")

    if age >= 50:
        tips.append("Balance training becomes critical after 50. Stand on one foot while brushing teeth, or try tai chi/yoga for fall prevention.")

    if gender == "female" and age >= 45:
        if not has_strength:
            tips.append("Strength training is especially important for women in perimenopause/menopause to maintain bone density and manage weight changes.")

    if bmi >= 25 and "walking" not in workouts and "running" not in workouts:
        tips.append("Walking 30 min after meals can significantly improve blood sugar regulation and aid weight management.")

    return tips
