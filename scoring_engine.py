# scoring_engine.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set, Tuple


def _parse_caps_from_any_shape(facility: Dict[str, Any]) -> Set[str]:
    """
    Supports facility capability storage in multiple shapes:
    1) Nested dict: facility["caps"] = {"ICU":1, "CT":0, ...}
    2) String list: facility["caps"] = "ICU;CT;OR" or "ICU, CT, OR"
    3) Flat CSV booleans: cap_ICU=1, cap_CT=0, ...
    4) Fallback: default_caps field like "ICU;CT" (if present)
    """
    caps_set: Set[str] = set()

    # (1) nested dict
    caps_obj = facility.get("caps", None)
    if isinstance(caps_obj, dict):
        for k, v in caps_obj.items():
            try:
                if int(v) == 1:
                    caps_set.add(str(k).strip())
            except Exception:
                # tolerate non-int values
                if bool(v):
                    caps_set.add(str(k).strip())
        return caps_set

    # (2) string encoded
    if isinstance(caps_obj, str) and caps_obj.strip():
        raw = caps_obj.replace(",", ";")
        for token in raw.split(";"):
            t = token.strip()
            if t:
                caps_set.add(t)
        return caps_set

    # (3) flat CSV-style: cap_ICU, cap_CT...
    for k, v in facility.items():
        if not isinstance(k, str):
            continue
        if k.startswith("cap_"):
            cap_name = k.replace("cap_", "").strip()
            try:
                if int(v) == 1:
                    caps_set.add(cap_name)
            except Exception:
                if bool(v):
                    caps_set.add(cap_name)

    if caps_set:
        return caps_set

    # (4) fallback: default_caps if present
    default_caps = facility.get("default_caps", "")
    if isinstance(default_caps, str) and default_caps.strip():
        raw = default_caps.replace(",", ";")
        for token in raw.split(";"):
            t = token.strip()
            if t:
                caps_set.add(t)

    return caps_set


def severity_adjusted_proximity(eta_min: float, severity_index: float) -> float:
    """
    Simple demo-safe nonlinear penalty:
    higher severity => ETA penalized more.
    """
    try:
        eta = float(eta_min)
    except Exception:
        eta = 999.0

    try:
        sev = float(severity_index)
    except Exception:
        sev = 0.0

    adjusted_eta = eta * (1.0 + (sev / 100.0))
    # 0..50 points, falling with adjusted ETA
    return max(0.0, 50.0 - adjusted_eta * 0.5)


def calculate_facility_score(
    facility: Dict[str, Any],
    required_caps: List[str] | Tuple[str, ...] | Set[str],
    eta: float,
    triage_color: str,
    severity_index: float,
    **_ignored_kwargs: Any,  # IMPORTANT: lets you pass case_type/bundle/etc without TypeError
) -> Tuple[float, Dict[str, Any]]:
    """
    Demo-safe scoring (0..100):
    - Gate 1: Must satisfy ALL required caps (if provided)
    - Gate 2: If RED => ICU_open >= 1
    - Score:
        proximity_score (0..50)  [severity adjusted]
        icu_score      (0..15)
        gov_bonus      (0 or 20)
    """

    # Normalize required_caps input
    req = [str(x).strip() for x in (required_caps or []) if str(x).strip()]

    caps_set = _parse_caps_from_any_shape(facility)

    # ---- Gate 1: required capabilities ----
    if req:
        has_all = all(cap in caps_set for cap in req)
        if not has_all:
            return 0.0, {
                "disqualified": "Missing required capability",
                "required_caps": req,
                "facility_caps": sorted(list(caps_set))[:50],  # keep payload small
            }

    # ---- Gate 2: RED requires ICU bed ----
    icu_open = 0
    try:
        icu_open = int(facility.get("ICU_open", 0) or 0)
    except Exception:
        icu_open = 0

    if str(triage_color).upper() == "RED" and icu_open < 1:
        return 0.0, {"disqualified": "No ICU capacity", "ICU_open": icu_open}

    # ---- Score components ----
    proximity_score = severity_adjusted_proximity(eta, severity_index)  # 0..50
    icu_score = min(max(icu_open, 0) * 5, 15)  # 0..15
    ownership = str(facility.get("ownership", "Private")).strip()
    gov_bonus = 20 if ownership.lower() == "government" else 0

    total = float(proximity_score + icu_score + gov_bonus)
    total = round(max(0.0, min(100.0, total)), 1)

    return total, {
        "proximity_score": round(float(proximity_score), 1),
        "icu_score": int(icu_score),
        "gov_bonus": int(gov_bonus),
        "eta": float(eta) if eta is not None else None,
        "severity_index": float(severity_index) if severity_index is not None else None,
        "ownership": ownership,
        "required_caps": req,
        "caps_detected_count": len(caps_set),
    }
