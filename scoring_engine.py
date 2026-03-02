# scoring_engine.py

def severity_adjusted_proximity(eta, severity):
    adjusted_eta = eta * (1 + severity / 100)
    return max(0, 50 - adjusted_eta * 0.5)


def calculate_facility_score(
    facility,
    required_caps,
    eta,
    triage_color,
    severity_index
):

    caps = facility.get("caps", "")

    if not all(cap in caps for cap in required_caps):
        return 0, {"disqualified": "Missing required capability"}

    if triage_color == "RED" and facility.get("ICU_open", 0) < 1:
        return 0, {"disqualified": "No ICU capacity"}

    proximity_score = severity_adjusted_proximity(eta, severity_index)
    icu_score = min(facility.get("ICU_open", 0) * 5, 15)
    gov_bonus = 20 if facility.get("ownership") == "Government" else 0

    total = proximity_score + icu_score + gov_bonus

    return round(total, 1), {
        "proximity_score": round(proximity_score, 1),
        "icu_score": icu_score,
        "gov_bonus": gov_bonus
    }
