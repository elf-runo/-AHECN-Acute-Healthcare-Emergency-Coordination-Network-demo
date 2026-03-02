"""
analytics_engine.py
Lightweight govt analytics helpers for AHECN demo.
"""

from __future__ import annotations
from typing import Dict, Any
import pandas as pd

def compute_dashboard_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or df.empty:
        return {
            "total_cases": 0,
            "avg_severity": 0.0,
            "avg_risk": 0.0,
        }

    return {
        "total_cases": int(len(df)),
        "avg_severity": float(df["severity_index"].mean()) if "severity_index" in df.columns else 0.0,
        "avg_risk": float(df["mortality_risk"].mean()) if "mortality_risk" in df.columns else 0.0,
    }

def mortality_risk(severity_index: float, eta_min: float) -> float:
    """
    Simple demo model: risk increases with physiologic severity and delay.
    Returns percent (0..100).
    """
    sev = max(0.0, min(1.0, float(severity_index)))
    eta = max(0.0, float(eta_min))
    # logistic-ish
    base = sev * 60.0
    delay = min(40.0, (eta / 90.0) * 40.0)
    return round(min(100.0, base + delay), 1)
