# clinical_engine.py
import math

AUTO_RED_CODES = {
    "O72.0","O72.1","O14.1","O15.0","O71.1","O85","O44.1","O00.1","O88.2",
    "S06.5","S06.4","S36.1","S36.0","I21.9","I46.9","I63.9",
    "A41.9","R57.1","P07.3","J96.0","E10.1","K92.2"
}

def validated_triage_decision(vitals, icd_row, context):
    icd10 = icd_row.get("icd10","")
    
    # --- VECTOR 1: Pathology Override ---
    if icd10 in AUTO_RED_CODES:
        return "RED", {
            "primary_driver": "Pathology",
            "reason": f"Auto-RED Critical ICD: {icd_row.get('label')}",
            "confidence": 0.95
        }

    # --- VECTOR 2: Physiological ---
    hr = vitals.get("hr", 80)
    sbp = vitals.get("sbp", 120)
    rr = vitals.get("rr", 18)
    spo2 = vitals.get("spo2", 98)

    rule_hits = []
    score = 0

    if sbp < 90:
        rule_hits.append("SBP < 90")
        score += 3
    if spo2 < 92:
        rule_hits.append("SpO2 < 92")
        score += 3
    if rr > 30:
        rule_hits.append("RR > 30")
        score += 2
    if hr > 130:
        rule_hits.append("HR > 130")
        score += 2

    if score >= 5:
        color = "RED"
    elif score >= 2:
        color = "YELLOW"
    else:
        color = "GREEN"

    return color, {
        "primary_driver": "Physiology",
        "rule_hits": rule_hits,
        "score": score,
        "confidence": 0.85
    }

def triage_engine(vitals, icd_row, context):
    color, meta = validated_triage_decision(vitals, icd_row, context)
    return color, meta
