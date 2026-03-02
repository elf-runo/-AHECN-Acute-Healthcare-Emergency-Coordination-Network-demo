# scoring_engine.py
def calculate_facility_score(facility, required_caps, eta, triage_color):
    
    if not all(cap in facility["caps"] for cap in required_caps):
        return 0, {"disqualified": "Missing required capability"}

    if triage_color == "RED" and facility["ICU_open"] < 1:
        return 0, {"disqualified": "No ICU capacity"}

    proximity_score = max(0, 50 - eta * 0.5)
    icu_score = min(facility["ICU_open"] * 5, 15)
    gov_bonus = 20 if facility["ownership"] == "Government" else 0

    total = proximity_score + icu_score + gov_bonus

    return round(total,1), {
        "proximity_score": proximity_score,
        "icu_score": icu_score,
        "gov_bonus": gov_bonus
    }
