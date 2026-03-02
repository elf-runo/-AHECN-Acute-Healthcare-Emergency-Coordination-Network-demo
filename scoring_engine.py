# scoring_engine.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional
import math


def _is_nan(x: Any) -> bool:
    try:
        return isinstance(x, float) and math.isnan(x)
    except Exception:
        return False


def _to_int(x: Any, default: int = 0) -> int:
    try:
        if x is None or _is_nan(x):
            return default
        if isinstance(x, bool):
            return int(x)
        s = str(x).strip()
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default


def _normalize_required_caps(required_caps: Any) -> List[str]:
    if required_caps is None:
        return []
    if isinstance(required_caps, (list, tuple, set)):
        return [str(x).strip() for x in required_caps if str(x).strip()]
    if isinstance(required_caps, str):
        return [p.strip() for p in required_caps.replace(",", ";").split(";") if p.strip()]
    s = str(required_caps).strip()
    return [s] if s else []


def _parse_caps_kv_string(caps_str: str) -> Dict[str, int]:
    # Parses: "ICU=1;Ventilator=1;BloodBank=0" -> {"ICU":1, "Ventilator":1, "BloodBank":0}
    out: Dict[str, int] = {}
    if not caps_str:
        return out
    for token in caps_str.split(";"):
        token = token.strip()
        if not token:
            continue
        if "=" in token:
            k, v = token.split("=", 1)
            out[k.strip()] = _to_int(v, 0)
        else:
            out[token] = 1
    return out


def _normalize_caps(facility: Dict[str, Any]) -> Dict[str, int]:
    raw = facility.get("caps", None)
    if isinstance(raw, dict):
        return {str(k).strip(): _to_int(v, 0) for k, v in raw.items()}
    if isinstance(raw, str):
        s = raw.strip()
        if "=" in s:
            return _parse_caps_kv_string(s)
        parts = [p.strip() for p in s.replace(",", ";").split(";") if p.strip()]
        return {p: 1 for p in parts}
    if isinstance(raw, (list, tuple, set)):
        return {str(x).strip(): 1 for x in raw if str(x).strip()}
    return {}


def calculate_facility_score(
    facility: Dict[str, Any],
    required_caps: Any,
    eta: Any,
    triage_color: str,
    severity_index: Any,
    case_type: Optional[str] = None,
    **kwargs: Any,  # IMPORTANT: prevents call-site TypeError forever
) -> Tuple[float, Dict[str, Any]]:
    details: Dict[str, Any] = {}

    req = _normalize_required_caps(required_caps)
    caps = _normalize_caps(facility)

    try:
        eta_min = float(eta)
    except Exception:
        eta_min = 999.0

    triage = (triage_color or "GREEN").upper()
    try:
        sev = float(severity_index or 0.0)  # 0..1 expected
    except Exception:
        sev = 0.0
    sev = max(0.0, min(1.0, sev))

    # Gate 1: 100% capabilities
    if req:
        missing = [c for c in req if _to_int(caps.get(c, 0), 0) != 1]
        if missing:
            details["gate_capability"] = "FAILED"
            details["capability_missing"] = missing
            details["total_score"] = 0
            return 0.0, details
    details["gate_capability"] = "PASSED"

    # Gate 2: ICU for RED / ICU / Vent
    icu_open = _to_int(facility.get("ICU_open", 0), 0)
    requires_bed = ("ICU" in req) or ("Ventilator" in req) or (triage == "RED")
    if requires_bed and icu_open < 1:
        details["gate_capacity"] = "FAILED"
        details["icu_beds"] = icu_open
        details["total_score"] = 0
        return 0.0, details
    details["gate_capacity"] = "PASSED"

    # Severity-adjusted ETA (increases delay penalty for higher acuity)
    adjusted_eta = eta_min * (1.0 + sev)

    # 1) TDC proximity score (0..50)
    if adjusted_eta <= 30:
        prox = 50
    elif adjusted_eta <= 60:
        prox = 35
    elif adjusted_eta <= 90:
        prox = 15
    else:
        prox = 0

    # 2) ICU surge buffer (0..15)
    if icu_open >= 3:
        icu_score = 15
    elif icu_open == 2:
        icu_score = 10
    elif icu_open == 1:
        icu_score = 5
    else:
        icu_score = 0

    # 3) Specialty bonus (0..15) – off until you add specialties dict
    spec_score = 0

    # 4) Fiscal guardrail (0..20)
    ownership = str(facility.get("ownership", "Private") or "Private").strip()
    fiscal_score = 20 if ownership.lower() == "government" else 0

    # Small severity bonus (0..5) for tie-breaking
    severity_bonus = int(round(sev * 5))

    total = prox + icu_score + spec_score + fiscal_score + severity_bonus
    total = min(100, max(0, total))

    details.update({
        "eta_minutes": round(eta_min, 1),
        "adjusted_eta_minutes": round(adjusted_eta, 1),
        "severity_index": sev,
        "proximity_score": prox,
        "icu_score": icu_score,
        "specialization_bonus": spec_score,
        "fiscal_score": fiscal_score,
        "severity_bonus": severity_bonus,
        "icu_beds": icu_open,
        "ownership": ownership,
        "total_score": total,
        "case_type": case_type,
    })

    return float(total), details
