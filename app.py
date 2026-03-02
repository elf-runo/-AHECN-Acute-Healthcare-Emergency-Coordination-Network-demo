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
# Bootstrap: data + session state (Step B)3
# ----------------------
@st.cache_data(show_spinner=False)
def _load_icd_df(path: str = "data/icd_catalogue.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    # Normalize expected column names (defensive)
    df.columns = [c.strip() for c in df.columns]
    return df

@st.cache_data(show_spinner=False)
def _load_facilities_df(path: str = "data/facilities_meghalaya.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    return df

# Required shared datasets (single load)
icd_df = _load_icd_df()
facilities_df = _load_facilities_df()

# Session state primitives (single source of truth)
if "referrals" not in st.session_state:
    st.session_state.referrals = []

if "facilities" not in st.session_state:
    # keep both df + list-of-dicts patterns available
    st.session_state.facilities = facilities_df.to_dict(orient="records")

# Optional: keep last triage output (avoids None crashes downstream)
if "last_triage" not in st.session_state:
    st.session_state.last_triage = {"color": "GREEN", "meta": {"severity_index": 0}}

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

st.markdown("### 🧪 Synthetic Seeding v2 (Severity-Weighted)")

cA, cB, cC = st.columns(3)
with cA:
    n_v2 = st.number_input("Generate v2 referrals", 100, 5000, 1000, step=100, key="seed_v2_n")
with cB:
    seed_v2 = st.number_input("Seed", 1, 999999, 42, step=1, key="seed_v2_seed")
with cC:
    append_v2 = st.checkbox("Append (don’t wipe existing)", value=True, key="seed_v2_append")

if st.button("⚙️ Generate v2 dataset", key="seed_v2_run"):
    try:
        # icd_df must exist in your app already (from icd_catalogue.csv loader)
        # validated_triage_decision must exist (your new hardened triage function)
        new_refs = seed_synthetic_referrals_v2(
            n=int(n_v2),
            facilities=st.session_state.get("facilities", []),
            icd_df=icd_df,  # <- ensure your ICD df variable is named icd_df
            validated_triage_decision_fn=triage_engine,
            now_ts_fn=now_ts,
            rand_geo_fn=rand_geo,
            dist_km_fn=dist_km,
            interpolate_route_fn=interpolate_route,
            traffic_factor_fn=traffic_factor_for_hour,
            rng_seed=int(seed_v2),
            append=bool(append_v2),
        )

        if not append_v2:
            st.session_state.referrals = []

        st.session_state.referrals = new_refs + st.session_state.referrals
        st.success(f"Generated {len(new_refs)} v2 synthetic referrals. Total now: {len(st.session_state.referrals)}")
        st.rerun()
    except Exception as e:
        st.error(f"v2 seeding failed: {e}")

# ----------------------
# Facility Matching
# ----------------------
facilities = facilities_df

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
# ---- Referral-derived analytics (2C integration) ----
ref_rows = []
for ref in st.session_state.get("referrals", []):
    severity_index = (
        (ref.get("triage", {}).get("decision", {}).get("score_details", {}) or {})
        .get("severity_index", None)
    )
    triage_color = ref.get("triage", {}).get("decision", {}).get("color", "GREEN")
    eta = ref.get("transport", {}).get("eta_min", None)
    ownership = ref.get("facility_ownership", "Private")  # if you store it per referral

    ref_rows.append({
        "id": ref.get("id"),
        "triage_color": triage_color,
        "severity_index": severity_index,
        "eta": eta,
        "ownership": ownership,
    })

ref_df = pd.DataFrame(ref_rows)

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
