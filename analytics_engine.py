# analytics_engine.py
import pandas as pd


def mortality_risk(severity, eta):
    delay_factor = 1 + (eta / 120)
    return min(1.0, (severity / 100) * delay_factor)


def compute_dashboard_metrics(df):
    total = len(df)
    red = len(df[df["triage_color"] == "RED"])

    return {
        "total_cases": total,
        "red_rate": round(red / total * 100, 1) if total else 0
    }
