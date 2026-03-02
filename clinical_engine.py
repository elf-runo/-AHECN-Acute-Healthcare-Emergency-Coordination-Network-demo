"""
clinical_engine.py
Production-ready clinical scoring + triage decisioning for AHECN MVP.

Design goals:
- Deterministic, explainable triage (no AI dependency)
- Dual-vector logic: Pathology (ICD) override + Physiology (EWS) safety-net
- Returns a severity_index (0..1) that downstream analytics + facility matching can use
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional, List

# ----------------------------
# Helpers
# ----------------------------

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def _is_missing(x) -> bool:
    return x is None or (isinstance(x, str) and not x.strip())

# ----------------------------
# qSOFA (adult sepsis context)
# ----------------------------

def calc_qsofa(rr: Optional[int], sbp: Optional[int], avpu: str = "A") -> Dict[str, Any]:
    """
    qSOFA: RR >= 22, SBP <= 100, altered mentation (AVPU != A).
    Returns dict with score and high_risk flag.
    """
    score = 0
    if rr is not None and rr >= 22: score += 1
    if sbp is not None and sbp <= 100: score += 1
    if (avpu or "A").upper() != "A": score += 1
    return {"score": score, "high_risk": score >= 2}

# ----------------------------
# NEWS2 (adult non-pregnant)
# ----------------------------

def calc_news2(rr: Optional[int], spo2: Optional[int], sbp: Optional[int], hr: Optional[int],
               temp_c: Optional[float], avpu: str = "A",
               o2_device: str = "Air", spo2_scale: int = 1) -> Dict[str, Any]:
    """
    Simplified NEWS2 scoring (scale 1 default). This is appropriate for demo/triage routing,
    not a replacement for clinical judgement.

    Returns: {"score": int, "emergency": bool, "review": bool}
    """
    score = 0

    # RR
    if rr is not None:
        if rr <= 8: score += 3
        elif 9 <= rr <= 11: score += 1
        elif 12 <= rr <= 20: score += 0
        elif 21 <= rr <= 24: score += 2
        else: score += 3

    # SpO2 (Scale 1)
    if spo2 is not None:
        if spo2_scale == 2:
            # conservative: treat scale 2 as scale1 for demo unless you implement COPD scale explicitly
            pass
        if spo2 <= 91: score += 3
        elif 92 <= spo2 <= 93: score += 2
        elif 94 <= spo2 <= 95: score += 1
        else: score += 0

    # Supplemental oxygen
    if (o2_device or "Air").lower() != "air":
        score += 2

    # Temp
    if temp_c is not None:
        if temp_c <= 35.0: score += 3
        elif 35.1 <= temp_c <= 36.0: score += 1
        elif 36.1 <= temp_c <= 38.0: score += 0
        elif 38.1 <= temp_c <= 39.0: score += 1
        else: score += 2

    # SBP
    if sbp is not None:
        if sbp <= 90: score += 3
        elif 91 <= sbp <= 100: score += 2
        elif 101 <= sbp <= 110: score += 1
        elif 111 <= sbp <= 219: score += 0
        else: score += 3

    # HR
    if hr is not None:
        if hr <= 40: score += 3
        elif 41 <= hr <= 50: score += 1
        elif 51 <= hr <= 90: score += 0
        elif 91 <= hr <= 110: score += 1
        elif 111 <= hr <= 130: score += 2
        else: score += 3

    # Consciousness (AVPU)
    if (avpu or "A").upper() != "A":
        score += 3

    emergency = score >= 7
    review = (score >= 5) or (score == 3)  # simplified trigger
    return {"score": int(score), "emergency": emergency, "review": review}

# ----------------------------
# MEOWS (maternal)
# ----------------------------

def calc_meows(hr: Optional[int], rr: Optional[int], sbp: Optional[int], temp_c: Optional[float], spo2: Optional[int]) -> Dict[str, Any]:
    """
    Very lightweight MEOWS-style triggers for demo.
    Returns dict with red/yellow trigger lists.
    """
    red: List[str] = []
    yellow: List[str] = []

    if hr is not None:
        if hr >= 130 or hr <= 40: red.append("HR extreme")
        elif hr >= 120 or hr <= 50: yellow.append("HR abnormal")

    if sbp is not None:
        if sbp <= 80 or sbp >= 200: red.append("SBP extreme")
        elif sbp <= 90 or sbp >= 160: yellow.append("SBP abnormal")

    if rr is not None:
        if rr >= 30 or rr <= 8: red.append("RR extreme")
        elif rr >= 24 or rr <= 10: yellow.append("RR abnormal")

    if temp_c is not None:
        if temp_c >= 39.0 or temp_c <= 35.0: red.append("Temp extreme")
        elif temp_c >= 38.0 or temp_c <= 36.0: yellow.append("Temp abnormal")

    if spo2 is not None:
        if spo2 < 90: red.append("SpO2 critical")
        elif spo2 < 94: yellow.append("SpO2 low")

    return {"red": red, "yellow": yellow}

# ----------------------------
# PEWS (peds)
# ----------------------------

def calc_pews(age_years: float, rr: Optional[int], hr: Optional[int], spo2: Optional[int],
              behavior: str = "Normal") -> Dict[str, Any]:
    """
    Simplified PEWS for demo (not a full validated implementation).
    Returns {"score": int, "urgent": bool}
    """
    score = 0

    # Resp
    if rr is not None:
        if rr >= 40: score += 2
        elif rr >= 30: score += 1

    # HR
    if hr is not None:
        if hr >= 160: score += 2
        elif hr >= 130: score += 1

    # SpO2
    if spo2 is not None:
        if spo2 < 90: score += 3
        elif spo2 < 94: score += 1

    # Behavior
    b = (behavior or "Normal").lower()
    if b in ["lethargic"]:
        score += 2
    elif b in ["irritable"]:
        score += 1

    urgent = score >= 6
    return {"score": int(score), "urgent": urgent}

# ----------------------------
# Dual-vector validated triage
# ----------------------------

# Curated "Auto-RED" ICD10 set (time-critical / life-threatening). Extend as needed.
COMPLETE_AUTO_RED_CODES = {
    # Maternal
    'O72.0','O72.1','O14.1','O15.0','O71.1','O85','O44.1','O00.1','O88.2',
    # Trauma
    'S06.5','S06.4','S36.1','S36.0','S27.3','S12.9','S32.1','S02.1','T07','T31.2','T17.9',
    # Cardiac
    'I21.9','I46.9','I44.2','I47.2','I26.9','I33.0',
    # Stroke/Neuro
    'I63.9','I61.9','I60.9','G46.3','I62.9','G00.9','G04.9','G06.0',
    # Sepsis/Shock
    'A41.9','R57.1','A41.0','A41.5','A39.2','R57.2','K65.0',
    # Pediatric/Neonatal
    'P07.3','P22.0','P36.9','P21.9','P10.2','P52.9',
    # Other critical
    'J96.0','T65.9','T63.0','N17.9','E10.1','K56.6','K92.2','A82.9',
}

CRITICAL_INTERVENTION_KEYWORDS = [
    "Defibrillation", "Thrombolysis", "Cardioversion", "Chest tube",
    "Crossmatch", "Massive transfusion", "C-section", "Intubation"
]

def validated_triage_decision(
    vitals: Dict[str, Any],
    icd_row: Dict[str, Any],
    context: Dict[str, Any]
) -> Tuple[str, Dict[str, Any]]:
    """
    Returns (triage_color, meta).

    meta includes:
      - primary_driver: "Pathology" | "Physiology"
      - reason: str
      - ews_type: str
      - ews_score: int | str
      - severity_index: float in [0,1]
      - score_details: dict for explainability
    """
    icd10 = (icd_row.get("icd10") or icd_row.get("code") or "").strip()
    label = icd_row.get("label", "Unknown diagnosis")
    bundle = icd_row.get("bundle", icd_row.get("case_type", ""))

    default_interventions = icd_row.get("default_interventions", "")
    if isinstance(default_interventions, list):
        default_interventions_text = " ".join(default_interventions)
    else:
        default_interventions_text = str(default_interventions or "")

    is_time_critical = any(k.lower() in default_interventions_text.lower() for k in CRITICAL_INTERVENTION_KEYWORDS)

    # -------- Vector 1: Pathology override --------
    if icd10 in COMPLETE_AUTO_RED_CODES or is_time_critical:
        meta = {
            "primary_driver": "Pathology",
            "reason": f"Time-critical diagnosis: {label}",
            "ews_type": "Bypassed",
            "ews_score": "Bypassed",
            "severity_index": 1.0,
            "score_details": {"auto_red": True, "icd10": icd10, "bundle": bundle},
        }
        return "RED", meta

    # -------- Vector 2: Physiology safety net --------
    age = float(context.get("age", 30) or 30)
    pregnant = bool(context.get("pregnant", False) or (bundle == "Maternal"))

    rr = vitals.get("rr")
    hr = vitals.get("hr")
    sbp = vitals.get("sbp")
    spo2 = vitals.get("spo2")
    temp = vitals.get("temp")
    avpu = vitals.get("avpu", "A")
    o2_device = context.get("o2_device", "Air")
    spo2_scale = int(context.get("spo2_scale", 1) or 1)
    behavior = context.get("behavior", "Normal")

    if age < 18:
        pews = calc_pews(age, rr, hr, spo2, behavior=behavior)
        ews_type = "PEWS"
        score = pews["score"]
        urgent = pews["urgent"]
        # normalize (0..10) -> (0..1)
        severity_index = clamp(score / 10.0, 0.0, 1.0)
        score_details = {"PEWS": pews}
    elif pregnant:
        meows = calc_meows(hr, rr, sbp, temp, spo2)
        ews_type = "MEOWS"
        urgent = len(meows["red"]) > 0
        score = len(meows["red"]) * 2 + len(meows["yellow"])
        severity_index = clamp(score / 8.0, 0.0, 1.0)
        score_details = {"MEOWS": meows}
    else:
        news = calc_news2(rr, spo2, sbp, hr, temp, avpu=avpu, o2_device=o2_device, spo2_scale=spo2_scale)
        ews_type = "NEWS2"
        score = news["score"]
        urgent = news["emergency"] or news["review"]
        severity_index = clamp(score / 12.0, 0.0, 1.0)
        score_details = {"NEWS2": news}

    # qSOFA is additive insight (does not override EWS color in demo)
    qsofa = calc_qsofa(rr, sbp, avpu=avpu)
    score_details["qSOFA"] = qsofa

    if urgent and (ews_type in ["NEWS2", "PEWS"] and score >= 7):
        color = "RED"
        reason = f"Clinical instability ({ews_type} emergency threshold)"
    elif urgent:
        color = "YELLOW"
        reason = f"Clinical risk detected ({ews_type} trigger)"
    elif score >= 5:
        color = "YELLOW"
        reason = f"Elevated risk ({ews_type} score {score})"
    else:
        color = "GREEN"
        reason = f"Stable physiology ({ews_type} score {score})"

    meta = {
        "primary_driver": "Physiology",
        "reason": reason,
        "ews_type": ews_type,
        "ews_score": int(score),
        "severity_index": float(severity_index),
        "score_details": score_details | {"severity_index": float(severity_index)},
    }
    return color, meta
