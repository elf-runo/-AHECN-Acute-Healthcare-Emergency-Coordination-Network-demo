import streamlit as st
import pandas as pd

from config import *
from clinical_engine import triage_engine
from scoring_engine import calculate_facility_score
from routing_engine import get_eta
from analytics_engine import mortality_risk, compute_dashboard_metrics

st.set_page_config(layout="wide")
st.title(APP_NAME)
st.caption(APP_VERSION)

# ----------------------
# Clinical Input
# ----------------------
st.sidebar.header("Clinical Input")

age = st.sidebar.number_input("Age", 0, 120, 30)
hr = st.sidebar.number_input("Heart Rate", 20, 200, 90)
rr = st.sidebar.number_input("Respiratory Rate", 5, 60, 18)
sbp = st.sidebar.number_input("Systolic BP", 50, 220, 120)
spo2 = st.sidebar.number_input("SpO2", 50, 100, 98)

vitals = {"hr": hr, "rr": rr, "sbp": sbp, "spo2": spo2}

# Demo ICD row example
icd_row = {
    "icd10": "I21.9",
    "label": "Acute MI",
    "time_critical": 1,
    "golden_window_minutes": 90
}

color, meta = triage_engine(vitals, icd_row, {"age": age})

st.subheader(f"Triage Result: {color}")
st.json(meta)

# ----------------------
# Facility Matching
# ----------------------
facilities = pd.read_csv("data/facilities_meghalaya.csv")

src = (25.58, 91.89)
results = []

for _, row in facilities.iterrows():
    facility = row.to_dict()
    eta = get_eta(src, (facility["lat"], facility["lon"]))

    score, details = calculate_facility_score(
        facility=facility,
        required_caps=["ICU"],
        eta=eta,
        triage_color=color,
        severity_index=meta["severity_index"]
    )

    if score > 0:
        risk = mortality_risk(meta["severity_index"], eta)

        results.append({
            "facility": facility["name"],
            "score": score,
            "eta": eta,
            "ownership": facility["ownership"],
            "mortality_risk": round(risk * 100, 1)
        })

results = sorted(results, key=lambda x: x["score"], reverse=True)

st.subheader("Recommended Facilities")
st.table(pd.DataFrame(results))

# ----------------------
# Government Analytics
# ----------------------
st.subheader("System Analytics")

if results:
    avg_risk = sum(r["mortality_risk"] for r in results) / len(results)
    st.metric("Avg Modeled Mortality Risk (%)", round(avg_risk, 1))
