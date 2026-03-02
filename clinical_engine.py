# clinical_engine.py

def continuous_physiology_score(vitals):

    hr = vitals.get("hr", 80)
    sbp = vitals.get("sbp", 120)
    rr = vitals.get("rr", 18)
    spo2 = vitals.get("spo2", 98)

    # SBP
    if sbp >= 100:
        s_sbp = 0
    elif sbp >= 70:
        s_sbp = (100 - sbp) * 1.2
    else:
        s_sbp = 100

    # SpO2
    if spo2 >= 95:
        s_spo2 = 0
    elif spo2 >= 85:
        s_spo2 = (95 - spo2) * 4
    else:
        s_spo2 = 100

    # RR
    if 12 <= rr <= 24:
        s_rr = 0
    elif rr > 24:
        s_rr = (rr - 24) * 2
    else:
        s_rr = (12 - rr) * 2

    # HR
    if 60 <= hr <= 110:
        s_hr = 0
    elif hr > 110:
        s_hr = (hr - 110) * 1.5
    else:
        s_hr = (60 - hr) * 1.5

    severity = (
        0.35 * s_sbp +
        0.30 * s_spo2 +
        0.20 * s_rr +
        0.15 * s_hr
    )

    severity = max(0, min(100, severity))
    return severity


def validated_triage_decision(vitals, icd_row, context):

    severity = continuous_physiology_score(vitals)

    if icd_row.get("time_critical") == 1:
        return "RED", {
            "primary_driver": "Pathology",
            "severity_index": 100,
            "confidence": 0.95,
            "golden_window": icd_row.get("golden_window_minutes", 60)
        }

    if severity >= 70:
        color = "RED"
    elif severity >= 35:
        color = "YELLOW"
    else:
        color = "GREEN"

    confidence = round(0.6 + abs(severity - 50) / 100, 2)

    return color, {
        "primary_driver": "Physiology",
        "severity_index": round(severity, 1),
        "confidence": confidence,
        "golden_window": icd_row.get("golden_window_minutes", None)
    }


def triage_engine(vitals, icd_row, context):
    return validated_triage_decision(vitals, icd_row, context)
