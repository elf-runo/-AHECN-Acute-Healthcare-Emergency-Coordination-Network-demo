import streamlit as st
import pandas as pd
import altair as alt

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
            "triage_color": color,
            "severity_index": meta["severity_index"],
            "mortality_risk": risk
        })

results = sorted(results, key=lambda x: x["score"], reverse=True)

st.subheader("Recommended Facilities")
st.table(pd.DataFrame(results))

# ----------------------
# GOVERNMENT ANALYTICS DASHBOARD
# ----------------------

st.subheader("Government Analytics Dashboard")

if results:

    df_results = pd.DataFrame(results)

    metrics = compute_dashboard_metrics(df_results)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Referrals", metrics["total_cases"])
    col2.metric("Avg Severity Index", metrics["avg_severity"])
    col3.metric("Avg Modeled Mortality Risk (%)", metrics["avg_risk"])

    st.markdown("---")

    # --------------------
    # TRIAGE DISTRIBUTION
    # --------------------

    triage_chart = (
        alt.Chart(df_results)
        .mark_bar()
        .encode(
            x="triage_color:N",
            y="count():Q",
            color="triage_color:N"
        )
        .properties(title="Triage Distribution")
    )

    st.altair_chart(triage_chart, use_container_width=True)

    # --------------------
    # SEVERITY DISTRIBUTION
    # --------------------

    severity_chart = (
        alt.Chart(df_results)
        .mark_bar()
        .encode(
            alt.X("severity_index:Q", bin=alt.Bin(maxbins=10)),
            y="count():Q"
        )
        .properties(title="Severity Index Distribution")
    )

    st.altair_chart(severity_chart, use_container_width=True)

    # --------------------
    # ETA vs Severity SCATTER
    # --------------------

    scatter_chart = (
        alt.Chart(df_results)
        .mark_circle(size=100)
        .encode(
            x="eta:Q",
            y="severity_index:Q",
            color="ownership:N",
            tooltip=["facility", "eta", "severity_index", "mortality_risk"]
        )
        .properties(title="ETA vs Severity (Facility Risk Surface)")
    )

    st.altair_chart(scatter_chart, use_container_width=True)

    # --------------------
    # GOVERNMENT vs PRIVATE PIE
    # --------------------

    ownership_counts = df_results["ownership"].value_counts().reset_index()
    ownership_counts.columns = ["ownership", "count"]

    pie_chart = (
        alt.Chart(ownership_counts)
        .mark_arc()
        .encode(
            theta="count:Q",
            color="ownership:N",
            tooltip=["ownership", "count"]
        )
        .properties(title="Public vs Private Utilization")
    )

    st.altair_chart(pie_chart, use_container_width=True)
