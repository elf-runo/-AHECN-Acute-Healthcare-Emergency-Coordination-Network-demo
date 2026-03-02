# analytics_engine.py

import pandas as pd


def mortality_risk(severity, eta):
    delay_factor = 1 + (eta / 120)
    return min(1.0, (severity / 100) * delay_factor)


def compute_dashboard_metrics(df):
    if df.empty:
        return {}

    total = len(df)
    red = len(df[df["triage_color"] == "RED"])
    yellow = len(df[df["triage_color"] == "YELLOW"])
    green = len(df[df["triage_color"] == "GREEN"])

    avg_severity = df["severity_index"].mean()
    avg_eta = df["eta"].mean()
    avg_risk = df["mortality_risk"].mean()

    gov_cases = len(df[df["ownership"] == "Government"])
    private_cases = len(df[df["ownership"] == "Private"])

    return {
        "total_cases": total,
        "red_rate": round(red / total * 100, 1),
        "yellow_rate": round(yellow / total * 100, 1),
        "green_rate": round(green / total * 100, 1),
        "avg_severity": round(avg_severity, 1),
        "avg_eta": round(avg_eta, 1),
        "avg_risk": round(avg_risk * 100, 1),
        "gov_rate": round(gov_cases / total * 100, 1),
        "private_rate": round(private_cases / total * 100, 1),
    }
