"""
scoring_engine.py
Facility scoring with clinical safety gates + explainable breakdown.

Implements the "Medically Validated Gated Multiplicative Scoring Matrix":
- Gate 1: must have 100% of required capabilities (life-saving)
- Gate 2: for RED / ICU/Vent cases, must have >=1 ICU bed
- After gates, apply survivor-weighting score (max 100)
"""

from __future__ import annotations
from typing import Dict, Any, List, Tuple

def calculate_facility_score(
    facility: Dict[str, Any],
    required_caps: List[str],
    eta: float,
    triage_color: str,
    severity_index: float,
    case_type: str | None = None,
) -> Tuple[int, Dict[str, Any]]:
    scoring_details: Dict[str, Any] = {}

    caps = facility.get("caps", {}) or {}
    icu_beds = int(facility.get("ICU_open", 0) or 0)
    ownership = (facility.get("ownership") or "Private").strip()
    is_gov = ownership.lower() == "government"

    # ---------------------------
    # GATE 1: Capability (100%)
    # ---------------------------
    if required_caps:
        has_all = all(int(caps.get(cap, 0)) == 1 for cap in required_caps)
        if not has_all:
            scoring_details["gate_capability"] = "FAILED"
            scoring_details["capability_required"] = required_caps
            scoring_details["capability_missing"] = [c for c in required_caps if int(caps.get(c, 0)) != 1]
            scoring_details["total_score"] = 0
            return 0, scoring_details
    scoring_details["gate_capability"] = "PASSED"

    # ---------------------------
    # GATE 2: Capacity for critical
    # ---------------------------
    requires_bed = ("ICU" in required_caps) or ("Ventilator" in required_caps) or (triage_color == "RED")
    if requires_bed and icu_beds < 1:
        scoring_details["gate_capacity"] = "FAILED"
        scoring_details["icu_beds"] = icu_beds
        scoring_details["total_score"] = 0
        return 0, scoring_details
    scoring_details["gate_capacity"] = "PASSED"

    # ---------------------------
    # Survivor-weighting (0..100)
    # ---------------------------
    score = 0

    # 1) Time-to-Definitive-Care (50)
    if eta <= 30:
        prox = 50
    elif eta <= 60:
        prox = 35
    elif eta <= 90:
        prox = 15
    else:
        prox = 0
    score += prox
    scoring_details["proximity_score"] = prox
    scoring_details["eta_minutes"] = round(float(eta), 1)

    # 2) Surge buffer (15)
    if icu_beds >= 3:
        icu_score = 15
    elif icu_beds == 2:
        icu_score = 10
    elif icu_beds == 1:
        icu_score = 5
    else:
        icu_score = 0
    score += icu_score
    scoring_details["icu_score"] = icu_score
    scoring_details["icu_beds"] = icu_beds

    # 3) Specialty excellence (15)
    spec = 0
    if case_type:
        specialties = facility.get("specialties", {}) or {}
        if int(specialties.get(case_type, 0)) == 1:
            spec = 15
    score += spec
    scoring_details["specialization_bonus"] = spec

    # 4) Fiscal guardrail (20)
    fiscal = 20 if is_gov else 0
    score += fiscal
    scoring_details["fiscal_score"] = fiscal
    scoring_details["ownership"] = ownership

    # Optional: severity-aware tie-breaker (small nudge, max +5)
    sev_bonus = int(round(min(1.0, max(0.0, float(severity_index))) * 5))
    score = min(100, score + sev_bonus)
    scoring_details["severity_bonus"] = sev_bonus
    scoring_details["severity_index"] = float(severity_index)

    scoring_details["total_score"] = int(score)
    return int(score), scoring_details
