"""Personalized daily health recommendations based on actual user data.

Analyzes trends, recovery needs, workout balance, and provides
specific actionable recommendations tailored to user profile and history.
"""

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
    if age < 26:
        return (7.0, 9.0)
    if age < 65:
        return (7.0, 9.0)
    return (7.0, 8.0)


def _step_target(age: int, bmi: float) -> int:
    base = 10000
    if age > 65:
        base = 7000
    elif age > 50:
        base = 8000
    if bmi >= 30:
        base = max(base - 2000, 5000)
    return base


def _weekly_exercise_target(age: int, bmi: float) -> int:
    if bmi >= 30:
        return 200
    if age > 60:
        return 150
    return 150


CARDIO_TYPES = {"running", "cycling", "swimming", "rowing", "elliptical", "jump_rope", "walking", "hiking", "stair_climbing", "dancing"}
STRENGTH_TYPES = {"weightlifting"}
FLEXIBILITY_TYPES = {"yoga", "pilates", "stretching"}
HIIT_TYPES = {"hiit", "boxing", "cross_training"}


def generate_personalized_recommendations(
    profile: UserProfile,
    recent_records: list[DailyRecord],
) -> dict:
    bmi = profile.bmi
    bmi_cat = _bmi_category(bmi)
    age = profile.age
    weight_kg = profile.weight_kg
    height_cm = profile.height_cm
    gender = profile.gender.lower()

    sleep_min, sleep_max = _sleep_target(age)
    step_target = _step_target(age, bmi)
    weekly_exercise = _weekly_exercise_target(age, bmi)

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

    # Per-day tracking for trends
    daily_steps: list[int] = []
    daily_sleep: list[float] = []
    daily_workout_min: list[int] = []
    daily_active_energy: list[float] = []
    rest_days = 0
    consecutive_workout_days = 0
    max_consecutive_workouts = 0
    consecutive_rest_days = 0
    max_consecutive_rest = 0

    for r in days_with_data:
        day_workout_min = 0
        if r.health_habits:
            avg_steps += r.health_habits.steps
            avg_sleep += r.health_habits.sleep_hours
            total_active_energy += r.health_habits.active_energy_burned
            total_flights += r.health_habits.flights_climbed
            total_distance_km += r.health_habits.distance_walked_km
            daily_steps.append(r.health_habits.steps)
            daily_sleep.append(r.health_habits.sleep_hours)
            daily_active_energy.append(r.health_habits.active_energy_burned)
        if r.workouts:
            workout_days += 1
            consecutive_workout_days += 1
            max_consecutive_workouts = max(max_consecutive_workouts, consecutive_workout_days)
            consecutive_rest_days = 0
            for w in r.workouts:
                total_workout_min += w.duration_minutes
                day_workout_min += w.duration_minutes
                workout_types_count[w.workout_type] = workout_types_count.get(w.workout_type, 0) + 1
                workout_minutes_by_type[w.workout_type] = workout_minutes_by_type.get(w.workout_type, 0) + w.duration_minutes
                intensity_count[w.intensity] = intensity_count.get(w.intensity, 0) + 1
        else:
            rest_days += 1
            consecutive_rest_days += 1
            max_consecutive_rest = max(max_consecutive_rest, consecutive_rest_days)
            consecutive_workout_days = 0
        daily_workout_min.append(day_workout_min)
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

    insights = []
    warnings = []
    achievements = []

    # --- BMI Assessment ---
    height_m = height_cm / 100
    if bmi_cat == "underweight":
        ideal_low = round(18.5 * height_m * height_m, 1)
        ideal_high = round(24.9 * height_m * height_m, 1)
        gain_needed = round(ideal_low - weight_kg, 1)
        insights.append(f"BMI {bmi} (underweight). You need to gain ~{gain_needed} kg ({round(gain_needed * 2.205, 1)} lbs) to reach healthy range. Focus on calorie surplus (+300-500 cal/day), protein-rich meals, and progressive strength training.")
    elif bmi_cat == "normal":
        achievements.append(f"BMI of {bmi} is in the healthy range — maintain with balanced nutrition and regular activity.")
    elif bmi_cat == "overweight":
        ideal_high = round(24.9 * height_m * height_m, 1)
        deficit = round(weight_kg - ideal_high, 1)
        weeks_to_goal = round(deficit / 0.5)
        insights.append(f"BMI {bmi} (overweight by ~{deficit} kg / {round(deficit * 2.205, 1)} lbs). At a 500 cal/day deficit, you can reach your target in ~{weeks_to_goal} weeks. Combine strength training (preserves muscle) with moderate cardio.")
    elif bmi_cat == "obese":
        ideal_high = round(24.9 * height_m * height_m, 1)
        deficit = round(weight_kg - ideal_high, 1)
        first_milestone = round(weight_kg * 0.95, 1)
        warnings.append(f"BMI {bmi} — focus on losing 5% bodyweight first (target: {first_milestone} kg). Even a 5% loss reduces heart disease risk by 20%. Start with walking and low-impact exercises, then build up gradually.")

    # --- Sleep Analysis with Trends ---
    if num_days > 0:
        if avg_sleep < sleep_min:
            gap = round(sleep_min - avg_sleep, 1)
            warnings.append(f"Averaging {avg_sleep} hrs sleep — {gap} hrs below the {sleep_min}-{sleep_max} hr target. Poor sleep raises cortisol (+15-20%), slows recovery, and increases injury risk. Try a consistent bedtime within a 30-min window.")
        elif avg_sleep > sleep_max + 1:
            warnings.append(f"Averaging {avg_sleep} hrs — above the recommended {sleep_max} hrs. Oversleeping can indicate low sleep quality or health issues. Track energy levels and consider a sleep study.")
        elif avg_sleep >= sleep_min:
            achievements.append(f"Sleep averaging {avg_sleep} hrs/night — within the {sleep_min}-{sleep_max} hr target.")

        # Sleep consistency check
        if len(daily_sleep) >= 3:
            sleep_std = _std_dev(daily_sleep)
            if sleep_std > 1.5:
                insights.append(f"Your sleep varies by ±{round(sleep_std, 1)} hrs/night. Irregular sleep disrupts circadian rhythm and reduces sleep quality. Aim for consistent bed/wake times, even on weekends.")
            elif sleep_std < 0.5 and avg_sleep >= sleep_min:
                achievements.append(f"Excellent sleep consistency (±{round(sleep_std, 1)} hrs variation) — this is key for recovery and hormonal balance.")

        # Low sleep days count
        low_sleep_days = sum(1 for s in daily_sleep if s < 6)
        if low_sleep_days >= 2 and num_days >= 5:
            warnings.append(f"{low_sleep_days} out of {num_days} days with less than 6 hrs sleep. Chronic sleep debt compounds — even 2 poor nights can reduce reaction time by 30% and workout performance by 20%.")

    # --- Steps Analysis with Trends ---
    if num_days > 0:
        step_pct = round(avg_steps / step_target * 100)
        if avg_steps < step_target * 0.5:
            warnings.append(f"Averaging {avg_steps:,} steps/day ({step_pct}% of {step_target:,} target). Prolonged sitting increases cardiovascular risk even with exercise. Start with 10-min walks after each meal — that alone adds ~3,000 steps.")
        elif avg_steps < step_target:
            gap = step_target - avg_steps
            insights.append(f"Averaging {avg_steps:,} steps/day ({step_pct}%). You need ~{gap:,} more daily — try parking farther, taking stairs, or a 15-min walk break at lunch.")
        else:
            achievements.append(f"Averaging {avg_steps:,} steps/day — exceeding your {step_target:,} target.")

        # Step trend (improving or declining?)
        if len(daily_steps) >= 5:
            first_half = daily_steps[:len(daily_steps)//2]
            second_half = daily_steps[len(daily_steps)//2:]
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)
            if second_avg > first_avg * 1.15:
                achievements.append(f"Step count trending up — averaging {round(second_avg):,} recently vs {round(first_avg):,} earlier. Keep it up!")
            elif second_avg < first_avg * 0.75 and first_avg > 3000:
                insights.append(f"Step count declining — {round(second_avg):,} recently vs {round(first_avg):,} earlier. Try setting a daily walk reminder.")

    # --- Exercise Analysis ---
    if num_days > 0:
        exercise_pct = round(weekly_workout_min / weekly_exercise * 100)
        if weekly_workout_min < weekly_exercise * 0.5:
            warnings.append(f"Projected {weekly_workout_min} min/week exercise — well below the {weekly_exercise} min WHO/AHA guideline. Start with 3 × 20-min sessions of brisk walking or cycling.")
        elif weekly_workout_min < weekly_exercise:
            extra_needed = weekly_exercise - weekly_workout_min
            insights.append(f"On track for {weekly_workout_min} min/week ({exercise_pct}%). Add {round(extra_needed / 3)} min across 3 sessions to hit your {weekly_exercise} min target.")
        else:
            achievements.append(f"Exceeding exercise goal: ~{weekly_workout_min} min/week vs {weekly_exercise} min target.")

    # --- Recovery & Overtraining Analysis ---
    if num_days >= 5:
        if max_consecutive_workouts >= 5:
            warnings.append(f"You've worked out {max_consecutive_workouts} days in a row without rest. Rest days are when adaptation happens — muscle fibers repair and grow stronger. Take 1-2 rest days per week to prevent burnout and overuse injuries.")
        elif max_consecutive_workouts >= 4:
            insights.append(f"{max_consecutive_workouts} consecutive workout days — consider adding an active recovery day (light walking or stretching) to improve performance on your next intense session.")

        if rest_days == 0 and workout_days >= 5:
            warnings.append("No rest days in your recent history. Without recovery, you risk overtraining syndrome (fatigue, decreased performance, mood changes). Schedule at least 1 full rest day per week.")
        elif max_consecutive_rest >= 4 and workout_days > 0:
            insights.append(f"{max_consecutive_rest} consecutive rest days — extended breaks can reduce fitness gains. Try to keep rest periods to 1-2 days between workouts.")

        # Workout frequency
        workout_freq = round(workout_days / num_days * 7, 1)
        if 3 <= workout_freq <= 5:
            achievements.append(f"Working out ~{workout_freq} days/week — ideal frequency for consistent progress with adequate recovery.")

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
            achievements.append(f"Resting HR {avg_resting_hr} bpm — excellent cardiovascular fitness (athlete level).")
        elif avg_resting_hr > resting_target[1]:
            insights.append(f"Resting HR {avg_resting_hr} bpm — above healthy range ({resting_target[0]}-{resting_target[1]}). Regular cardio, stress management, and better sleep can lower it 5-10 bpm over 8-12 weeks.")
        else:
            achievements.append(f"Resting HR {avg_resting_hr} bpm — within healthy range ({resting_target[0]}-{resting_target[1]}).")

    # --- Active Energy ---
    if avg_active_energy > 0:
        calorie_target = _daily_calorie_burn_target(age, gender, weight_kg, bmi)
        if avg_active_energy < calorie_target * 0.5:
            insights.append(f"Burning {avg_active_energy} active cal/day (target: ~{calorie_target}). Increase workout intensity or add a second short session — even a 15-min walk adds ~80-100 cal.")
        elif avg_active_energy >= calorie_target:
            achievements.append(f"Active energy burn {avg_active_energy} cal/day meets your ~{calorie_target} cal target.")

    # --- Today's Action Plan ---
    today_plan = _generate_today_plan(
        age, gender, bmi, weight_kg, avg_sleep, avg_steps, step_target,
        workout_types_count, workout_days, num_days,
        consecutive_workout_days, intensity_count
    )

    # --- Age-Specific Tips ---
    age_tips = _age_specific_tips(age, gender, bmi, workout_types_count)
    insights.extend(age_tips)

    targets = {
        "steps": step_target,
        "sleep_hours": f"{sleep_min}-{sleep_max}",
        "exercise_min_per_week": weekly_exercise,
        "exercise_days_per_week": max(3, min(5, workout_days + 1)) if workout_days < 5 else 5,
    }

    recommended = _recommend_workouts(age, gender, bmi, workout_types_count)

    return {
        "targets": targets,
        "recommended_workouts": recommended,
        "achievements": achievements,
        "insights": insights,
        "warnings": warnings,
        "today_plan": today_plan,
        "stats": {
            "avg_steps": avg_steps,
            "avg_sleep": avg_sleep,
            "avg_distance_miles": avg_distance_mi,
            "weekly_workout_min": weekly_workout_min,
            "workout_days": workout_days,
            "rest_days": rest_days,
            "total_days_analyzed": num_days,
            "bmi": bmi,
            "bmi_category": bmi_cat,
            "avg_resting_hr": avg_resting_hr if avg_resting_hr > 0 else None,
            "avg_active_energy": avg_active_energy,
            "workout_frequency": round(workout_days / max(num_days, 1) * 7, 1),
            "total_flights": total_flights,
            "sleep_consistency": round(_std_dev(daily_sleep), 1) if len(daily_sleep) >= 3 else None,
        },
    }


def _std_dev(values: list) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5


def _generate_today_plan(
    age, gender, bmi, weight_kg, avg_sleep, avg_steps, step_target,
    workout_types, workout_days, num_days,
    consecutive_workout_days, intensity_counts
) -> list[str]:
    plan = []

    # Recovery check
    vigorous_recent = intensity_counts.get("vigorous", 0)
    total_intensity = sum(intensity_counts.values())

    if consecutive_workout_days >= 3:
        plan.append("Active recovery day: light walking (20-30 min) or gentle stretching. Your muscles need repair time after 3+ consecutive days.")
    elif consecutive_workout_days >= 2 and vigorous_recent > 0:
        plan.append("Consider a moderate-intensity session today — yoga, cycling, or swimming to give overworked muscles a break while staying active.")
    else:
        # Suggest based on what's missing
        has_strength = "weightlifting" in workout_types
        has_cardio = any(t in CARDIO_TYPES for t in workout_types)
        has_flex = any(t in FLEXIBILITY_TYPES for t in workout_types)

        if not has_strength and bmi >= 25:
            plan.append("Today: strength training session (30-45 min). Focus on compound movements — squats, deadlifts, rows, bench press. These burn the most calories and build functional muscle.")
        elif not has_cardio:
            if bmi >= 30:
                plan.append("Today: 30-min brisk walk or swimming session. Low-impact cardio is safest for your joints while building cardiovascular fitness.")
            else:
                plan.append("Today: 30-45 min cardio — running, cycling, or rowing. Aim for moderate intensity where you can talk but not sing.")
        elif not has_flex and total_intensity >= 3:
            plan.append("Today: yoga or stretching session (20-30 min). This improves recovery, range of motion, and reduces injury risk from your strength/cardio work.")
        elif has_strength and has_cardio:
            plan.append("Good workout variety! Today: mix it up with HIIT (20-30 min) or try a new activity to challenge different muscle groups.")

    # Sleep-based recommendation
    if avg_sleep < 6 and avg_sleep > 0:
        plan.append("Sleep priority: aim for bed 30 min earlier tonight. Dim screens 1 hr before bed, keep room cool (65-68°F). Sleep is your #1 recovery tool.")

    # Steps reminder
    if avg_steps < step_target and avg_steps > 0:
        plan.append(f"Step goal: {step_target:,} steps. Walk after meals (10 min each = ~3,000 extra steps), take stairs, or schedule a mid-day walk break.")

    return plan


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
            f"{top_pct}% of workouts are {top_name} ({top_count}/{total_sessions} sessions). "
            f"Over-reliance increases overuse injury risk. Pivot: {pivot}"
        )
    elif top_pct >= 50 and total_sessions >= 4:
        pivot = _get_pivot_suggestion(top_type, age, bmi, weight_kg, gender)
        insights.append(f"{top_name} dominates ({top_pct}%). Balance with: {pivot}")

    # --- Category balance ---
    if total_sessions >= 3:
        if strength_sessions == 0:
            if bmi >= 25:
                warnings.append(
                    f"No strength training detected. With BMI {bmi}, weightlifting 2-3x/week is critical — "
                    f"it boosts resting metabolism (~50 extra cal/day per kg of muscle gained) and accelerates fat loss better than cardio alone."
                )
            else:
                insights.append(
                    "No strength training. Adults lose 3-5% muscle per decade after 30. "
                    "Add 2 sessions/week for bone density, posture, and metabolic rate."
                )

        if cardio_sessions == 0:
            warnings.append(
                "No cardio detected. AHA recommends 150 min/week moderate cardio for heart health. "
                f"{'Start with walking or swimming (low-impact).' if bmi >= 30 else 'Try running, cycling, or swimming.'}"
            )

        if flexibility_sessions == 0 and total_sessions >= 5:
            insights.append(
                "No flexibility/mobility work. Add 1-2 yoga or stretching sessions — "
                "reduces injury risk, improves range of motion, and speeds recovery."
            )

        if cardio_pct > 70 and strength_pct == 0:
            insights.append(
                f"Routine is {cardio_pct}% cardio with no strength training — this can lead to muscle loss. "
                f"Target: 60% cardio / 30% strength / 10% flexibility for {'weight management' if bmi >= 25 else 'overall fitness'}."
            )

    # --- Intensity balance ---
    total_intensity = sum(intensity_counts.values())
    if total_intensity >= 3:
        vigorous = intensity_counts.get("vigorous", 0)
        light = intensity_counts.get("light", 0)
        moderate = intensity_counts.get("moderate", 0)
        vigorous_pct = round(vigorous / total_intensity * 100)
        light_pct = round(light / total_intensity * 100)

        if vigorous_pct > 60:
            warnings.append(
                f"{vigorous_pct}% vigorous intensity — too much high-intensity raises cortisol and injury risk. "
                f"Follow the 80/20 rule: 80% low-moderate, 20% high intensity."
            )
        elif light_pct > 80:
            insights.append(
                f"{light_pct}% of workouts are light intensity. Add 1-2 moderate/vigorous sessions weekly to improve fitness and calorie burn."
            )
        elif 15 <= vigorous_pct <= 25:
            achievements.append(f"Good intensity balance: {vigorous_pct}% vigorous, following the recommended 80/20 polarized training model.")

    # --- BMI-specific ---
    if bmi >= 30 and total_sessions >= 2:
        has_hiit = hiit_sessions > 0
        if not has_hiit and strength_sessions == 0:
            insights.append(
                f"For BMI {bmi}, combine: walking/swimming 3x/week (cardio base), "
                f"weightlifting 2x/week (boost metabolism), and 1 moderate HIIT session for afterburn effect."
            )
    elif bmi < 18.5 and total_sessions >= 2:
        if cardio_pct > 50 and strength_sessions == 0:
            warnings.append(
                f"BMI {bmi} (underweight) + heavy cardio without strength training = further weight loss risk. "
                f"Prioritize compound lifts (squats, deadlifts, bench) with progressive overload and calorie surplus."
            )

    # --- Duration insights ---
    if total_sessions >= 3:
        avg_duration = round(total_min / total_sessions)
        if avg_duration < 20:
            insights.append(f"Average workout is {avg_duration} min — aim for 30-45 min per session for meaningful cardiovascular and strength adaptations.")
        elif avg_duration > 75:
            insights.append(f"Average workout is {avg_duration} min. Workouts over 60-75 min can increase cortisol. Consider shorter, more intense sessions for efficiency.")

    # --- Good balance achievement ---
    if total_sessions >= 4:
        unique = len(type_counts)
        has_all_three = cardio_sessions > 0 and strength_sessions > 0 and flexibility_sessions > 0
        if has_all_three:
            achievements.append(
                f"Balanced routine: cardio ({cardio_sessions}x), strength ({strength_sessions}x), flexibility ({flexibility_sessions}x) — covers all fitness pillars."
            )
        elif unique >= 3 and top_pct < 50:
            achievements.append(f"Good variety: {unique} workout types across {total_sessions} sessions.")

    return {"insights": insights, "warnings": warnings, "achievements": achievements}


def _get_pivot_suggestion(dominant_type: str, age: int, bmi: float, weight_kg: float, gender: str) -> str:
    dominant = dominant_type.lower()
    name = dominant.replace("_", " ")

    if dominant in CARDIO_TYPES:
        if bmi >= 25:
            return (
                f"Replace 2 {name} sessions with weightlifting. "
                f"At {weight_kg} kg, adding 2 kg muscle burns ~100 extra cal/day at rest."
            )
        return f"Swap 1-2 {name} sessions for weightlifting or yoga to prevent overuse injuries."

    if dominant in STRENGTH_TYPES:
        if age > 40:
            return "Add 2-3 cardio sessions (cycling/swimming) for heart health + 1 yoga for mobility."
        return "Add 2 cardio sessions (running/cycling) + 1 flexibility session for range of motion."

    if dominant in HIIT_TYPES:
        return "Limit HIIT to 2-3x/week. Add steady-state cardio for recovery and strength training for muscle balance."

    if dominant in FLEXIBILITY_TYPES:
        return "Add 2 strength sessions and 2 cardio sessions weekly for complete fitness."

    return "Mix in cardio, strength, and flexibility for balance."


def _daily_calorie_burn_target(age: int, gender: str, weight_kg: float, bmi: float) -> int:
    if gender == "male":
        base = 300 if bmi < 25 else 400
    else:
        base = 250 if bmi < 25 else 350
    if age > 50:
        base = round(base * 0.85)
    return base


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

    # Prioritize missing categories
    has_strength = any(t in STRENGTH_TYPES for t in current)
    has_cardio = any(t in CARDIO_TYPES for t in current)
    has_flex = any(t in FLEXIBILITY_TYPES for t in current)

    prioritized = []
    if not has_strength and "weightlifting" in pool:
        prioritized.append("weightlifting")
    if not has_cardio:
        for w in pool:
            if w in CARDIO_TYPES and w not in prioritized:
                prioritized.append(w)
                break
    if not has_flex:
        for w in pool:
            if w in FLEXIBILITY_TYPES and w not in prioritized:
                prioritized.append(w)
                break
    for w in pool:
        if w not in prioritized:
            prioritized.append(w)

    return prioritized[:5]


def _age_specific_tips(age: int, gender: str, bmi: float, workouts: dict) -> list[str]:
    tips = []
    has_strength = "weightlifting" in workouts

    if age >= 30 and not has_strength:
        tips.append("After 30, muscle loss is 3-5%/decade. Strength training 2-3x/week maintains metabolism and bone density.")

    if age >= 40:
        tips.append("Recovery takes longer after 40 — allow 48 hrs between intense sessions on the same muscles. Prioritize sleep for recovery.")

    if age >= 50:
        tips.append("Balance training is critical after 50. Try single-leg stands or tai chi/yoga for fall prevention.")

    if gender == "female" and age >= 45 and not has_strength:
        tips.append("Strength training is especially important during perimenopause/menopause for bone density and managing weight changes.")

    if bmi >= 25 and "walking" not in workouts and "running" not in workouts:
        tips.append("Walking 30 min after meals significantly improves blood sugar regulation and aids weight management.")

    return tips
