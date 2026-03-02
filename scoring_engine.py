# scoring_engine.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple
import json
import math
import re


def severity_adjusted_proximity(eta_min: float, severity_index: float) -> float:
    """
    Returns a proximity score out of 50, adjusted by clinical severity.
    Higher severity -> penalize time more (i.e., effective ETA increases).
    """
    try:
        eta = float(eta_min)
    except Exception:
        eta = 999.0

    try:
        sev = float(severity_index)
    except Exception:
        sev = 0.0

    # Severity index assumed 0-100; scale impacts ETA moderately
    adjusted_eta = eta * (1.0 + (sev / 100.0))
    # Simple linear decay: 0.5 points per minute (capped)
    return max(0.0, 50.0 - adjusted_eta * 0.5)


def _to_caps_set(caps_raw: Any) -> set[str]:
    """
    Normalize facility caps into a set of capability names.
    Supports dict, list/tuple/set, semicolon/comma separated strings, JSON strings, None/NaN.
    """
    if caps_raw is None:
        return set()

    # handle pandas NaN
    try:
        if isinstance(caps_raw, float) and math.isnan(caps_raw):
            return set()
    except Exception:
        pass

    # dict -> include keys where value truthy/1
    if isinstance(caps_raw, dict):
        out = set()
        for k, v in caps_raw.items():
            try:
                ok = int(v) == 1
            except Exception:
                ok = bool(v)
            if ok:
                out.add(str(k).strip())
        return {x for x in out if x}

    # iterable -> treat elements as caps
    if isinstance(caps_raw, (list, tuple, set)):
        return {str(x).strip() for x in caps_raw if str(x).strip()}

    # string -> try JSON dict/list, else split by delimiters
    if isinstance(caps_raw, str):
        s = caps_raw.strip()
        if not s:
            return set()

        # try JSON
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                parsed = json.loads(s)
                return _to_caps_set(parsed)
            except Exception:
                pass

        # split by common delimiters
        parts = re.split(r"[;,|/]+", s)
        return {p.strip() for p in parts if p.strip()}

    # fallback: unknown type
    return set()


def _to_required_caps(req_raw: Any) -> List[str]:
    """
    Normalize required_caps into a list[str].
    Supports list, set, tuple, semicolon string, None.
    """
    if req_raw is None:
        return []
    if isinstance(req_raw, (list, tuple, set)):
        return [str(x).strip() for x in req_raw if str(x).strip()]
    if isinstance(req_raw, str):
        return [x.strip() for x in re.split(r"[;,|/]+", req_raw) if x.strip()]
    return [str(req_raw).strip()] if str(req_raw).strip() else []


def calculate_facility_score(
    facility: Dict[str, Any],
    required_caps: Any,
    eta: float,
    triage_color: str,
    severity_index: float,
) -> Tuple[float, Dict[str, Any]]:
    """
    Gated facility scoring:
    - Gate 1: must have all required capabilities
    - Gate 2: if RED -> must have ICU_open >= 1
    Then weighted scoring:
    - proximity (0-50), ICU beds (0-15), govt bonus (0-20)
    """

    req_caps = _to_required_caps(required_caps)
    caps_set = _to_caps_set(facility.get("caps", None))

    # ---------- Gate 1: capability completeness ----------
    missing = [cap for cap in req_caps if cap not in caps_set]
    if missing:
        return 0.0, {"disqualified": "Missing required capability", "missing_caps": missing}

    # ---------- Gate 2: critical capacity ----------
    icu_open = 0
    try:
        icu_open = int(facility.get("ICU_open", 0) or 0)
    except Exception:
        icu_open = 0

    if str(triage_color).upper() == "RED" and icu_open < 1:
        return 0.0, {"disqualified": "No ICU capacity", "ICU_open": icu_open}

    # ---------- Weighted scoring ----------
    proximity_score = severity_adjusted_proximity(eta, severity_index)  # /50
    icu_score = min(max(icu_open, 0) * 5.0, 15.0)  # /15

    ownership = str(facility.get("ownership", "") or "").strip().lower()
    gov_bonus = 20.0 if ownership == "government" else 0.0  # /20

    total = float(proximity_score + icu_score + gov_bonus)

    details = {
        "proximity_score": round(proximity_score, 1),
        "icu_score": round(icu_score, 1),
        "gov_bonus": round(gov_bonus, 1),
        "ICU_open": icu_open,
        "ownership": facility.get("ownership", "Unknown"),
        "caps_count": len(caps_set),
        "required_caps": req_caps,
    }
    return round(total, 1), details
