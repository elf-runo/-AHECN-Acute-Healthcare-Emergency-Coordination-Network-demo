# analytics_engine.py
import pandas as pd

def compute_dashboard_metrics(df):
    total = len(df)
    red = len(df[df["triage_color"]=="RED"])
    gov = len(df[df["ownership"]=="Government"])
    
    return {
        "total_cases": total,
        "red_rate": round(red/total*100,1) if total else 0,
        "gov_utilization": round(gov/total*100,1) if total else 0
    }
