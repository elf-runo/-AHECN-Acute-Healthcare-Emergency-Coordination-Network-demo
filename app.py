import streamlit as st
import pandas as pd
import altair as alt
import inspect, scoring_engine
st.sidebar.write("scoring_engine file:", scoring_engine.__file__)
st.sidebar.write("calculate_facility_score sig:", str(inspect.signature(scoring_engine.calculate_facility_score)))

from utils import load_icd_catalogue, load_facilities
from clinical_engine import validated_triage_decision
from scoring_engine import calculate_facility_score
from routing_engine import get_eta
from analytics_engine import compute_dashboard_metrics, mortality_risk

st.set_page_config(page_title="AHECN – Enterprise Demo Build", layout="wide")

# ----------------------
# Load data
# ----------------------
@st.cache_data(show_spinner=False)
def _icd_df():
    return load_icd_catalogue()

@st.cache_data(show_spinner=False)
def _fac_df():
    return load_facilities()

icd_df = _icd_df()
facilities_df = _fac_df()

st.title("AHECN – Acute Healthcare Emergency Care Network (Enterprise Demo Build)")

# ----------------------
# TRIAGE + REFERRAL PAGE
# ----------------------
st.header("Triage & Referral")

c1, c2, c3 = st.columns(3)
with c1:
    age = st.number_input("Age (years)", 0, 120, 35)
    pregnant = st.checkbox("Pregnant", value=False)
with c2:
    rr = st.number_input("RR", 0, 80, 22)
    spo2 = st.number_input("SpO₂", 50, 100, 92)
    avpu = st.selectbox("AVPU", ["A","V","P","U"], index=0)
with c3:
    hr = st.number_input("HR", 0, 250, 118)
    sbp = st.number_input("SBP", 0, 300, 92)
    temp = st.number_input("Temp °C", 30.0, 43.0, 38.4, step=0.1)

src_lat = st.number_input("Patient latitude", value=25.58, format="%.6f")
src_lon = st.number_input("Patient longitude", value=91.89, format="%.6f")

# ICD selection
st.subheader("Provisional Diagnosis (ICD-10)")
bundle = st.selectbox("Case bundle", sorted(icd_df["bundle"].unique().tolist()))
dfb = icd_df[icd_df["bundle"] == bundle].copy()
dx = st.selectbox("Select diagnosis", dfb["label"].tolist())
icd_row = dfb[dfb["label"] == dx].iloc[0].to_dict()

# Required caps from ICD
required_caps = [x.strip() for x in (icd_row.get("default_caps","") or "").split(";") if x.strip()]

vitals = {"hr": hr, "rr": rr, "sbp": sbp, "temp": temp, "spo2": spo2, "avpu": avpu}
context = {"age": age, "pregnant": pregnant, "o2_device": "Air", "spo2_scale": 1, "behavior": "Normal"}

triage_color, meta = validated_triage_decision(vitals=vitals, icd_row=icd_row, context=context)

st.markdown("### Triage Result")
pill = {"RED":"🟥 RED", "YELLOW":"🟨 YELLOW", "GREEN":"🟩 GREEN"}[triage_color]
st.subheader(pill)
st.caption(f"Primary driver: **{meta['primary_driver']}** • {meta['reason']}")
st.caption(f"Severity index: **{meta['severity_index']:.2f}**")

# ---------------------------------------------------------
# FACILITY MATCHING (Gated Clinical Safety + Topography)
# ---------------------------------------------------------
st.markdown("---")
st.header("Facility Matching (Gated Clinical Safety)")

origin = (float(src_lat), float(src_lon))
results = []

# Safely extract variables for the Golden Hour curve
pathology_bundle = icd_row.get("bundle", "Other")
sev = float((meta or {}).get("severity_index", 0.0) or 0.0)

for _, row in facilities_df.iterrows():
    f_dict = row.to_dict()
    dest = (float(f_dict.get("lat", 0.0)), float(f_dict.get("lon", 0.0)))
    f_dict["ownership"] = str(f_dict.get("ownership", "Private") or "Private")
    
    # 1. ADAPTIVE TOPOGRAPHY ROUTING
    # Gracefully falls back if routing_engine.py hasn't been updated on GitHub yet
    try:
        route_eta = get_eta(origin, dest, speed_kmh=40.0, is_hilly_terrain=True)
    except TypeError:
        route_eta = get_eta(origin, dest, speed_kmh=40.0)

    # 2. RESILIENT SCORING ENGINE CALL
    try:
        score, details = calculate_facility_score(
            facility=f_dict,
            required_caps=required_caps,
            eta=route_eta,
            triage_color=triage_color,
            severity_index=sev,
            case_type=pathology_bundle
        )
    except TypeError as e:
        # Prevents a catastrophic crash during a pitch
        st.error("🚨 **SYSTEM ALERT: ENGINE SYNCHRONIZATION PENDING**")
        st.warning(f"**Backend Diagnostic:** `{e}`")
        st.info("💡 **Resolution:** Your advanced `app.py` UI is live, but Streamlit is still reading an older `scoring_engine.py` from your repository. Please ensure the latest `scoring_engine.py` (containing the new parameters) is committed and pushed to GitHub.")
        st.stop()

    # 3. ABSOLUTE CLINICAL GATE (The "Blind Dispatch" Fix)
    if score > 0 or details.get("gate_capacity") == "WARNING_ED_STABILIZATION_ONLY":
        
        # 4. ADAPTIVE MORTALITY MODELING (Golden Hour Curve)
        try:
            m_risk = mortality_risk(sev, route_eta, pathology=pathology_bundle)
        except TypeError:
            m_risk = mortality_risk(sev, route_eta) # Fallback

        results.append({
            "facility": f_dict["name"],
            "score": score,
            "eta": round(route_eta, 1),
            "ownership": f_dict["ownership"],
            "triage_color": triage_color,
            "severity_index": sev,
            "mortality_risk": m_risk,
            "ICU_open": int(f_dict.get("ICU_open", 0)),
            "scoring_details": details,
        })

# ---------------------------------------------------------
# UI RENDERING & EXPLAINABLE AI
# ---------------------------------------------------------
results = sorted(results, key=lambda x: (-x["score"], x["eta"]))

st.subheader("Recommended Facilities")
if not results:
    st.error("🚨 **CRITICAL ALERT: ZERO STATEWIDE CAPACITY.**")
    st.warning("No facilities meet the absolute minimum clinical safety gates (Capabilities/Capacity) within transit range. Initiate immediate on-site ED stabilization and escalate to State Command for out-of-network airlift.")
else:
    # Render clean dataframe
    st.dataframe(pd.DataFrame([{k:v for k,v in r.items() if k!="scoring_details"} for r in results]), use_container_width=True)

    st.markdown("### Explainable Matching Logic")
    for i, row in enumerate(results[:6], 1):
        st.markdown(f"#### {i}. {row['facility']} — Score {row['score']}/100 — ETA {row['eta']} min")
        
        with st.expander("📊 Why was this facility recommended? (Clinical Logic)"):
            details = row.get("scoring_details", {})

            # Safety Gates
            st.markdown("#### 1. Safety Gates (Absolute Mandates)")
            if details.get('gate_capability') == "PASSED":
                st.markdown("✅ **Infrastructure Gate:** Passed. Facility possesses 100% of the requested life-saving capabilities.")
            else:
                st.markdown(f"❌ **Infrastructure Gate:** Failed. Missing: {', '.join(details.get('capability_missing', []))}")

            if details.get('gate_capacity') == "PASSED":
                st.markdown("✅ **Capacity Gate:** Passed. Minimum required critical care beds are available.")
            elif details.get('gate_capacity') == "WARNING_ED_STABILIZATION_ONLY":
                st.markdown("⚠️ **Capacity Gate Override:** ICU Full. Facility selected for immediate ED Resuscitation only.")
            else:
                st.markdown("❌ **Capacity Gate:** Failed. No ICU capacity available.")

            # Weighted Matrix
            st.markdown("#### 2. Optimization Matrix (Out of 100 pts)")
            st.markdown(f"🚑 **Time-to-Definitive-Care:** {details.get('eta_minutes', 'N/A')} mins. *(Score: {details.get('proximity_score', 0)}/50)*")
            st.markdown(f"🛏️ **Surge Buffer:** {row.get('ICU_open', 0)} open beds. *(Score: {details.get('icu_score', 0)}/15)*")
            
            fiscal_score = details.get('fiscal_score', 0)
            if fiscal_score > 0:
                st.markdown(f"🏛️ **Fiscal Guardrail:** Government facility prioritized to protect public funds. *(Score: {fiscal_score}/20)*")
            else:
                st.markdown(f"🏥 **Fiscal Guardrail:** Private facility utilized. *(Score: {fiscal_score}/20)*")

            st.markdown("---")
            st.markdown(f"<div style='text-align: right; font-size: 1.05rem;'><strong>Algorithm Confidence Score: {row.get('score', 0)} / 100</strong></div>", unsafe_allow_html=True)

# ----------------------
# GOVERNMENT ANALYTICS DASHBOARD
# ----------------------
st.markdown("---")
st.header("Government Analytics Dashboard")

if results:
    df_results = pd.DataFrame(results)
    metrics = compute_dashboard_metrics(df_results)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Referrals", metrics["total_cases"])
    col2.metric("Avg Severity Index", f"{metrics['avg_severity']:.2f}")
    col3.metric("Avg Modeled Mortality Risk (%)", f"{metrics['avg_risk']:.1f}")

    triage_chart = (
        alt.Chart(df_results)
        .mark_bar()
        .encode(x="triage_color:N", y="count():Q", color="triage_color:N")
        .properties(title="Triage Distribution")
    )
    st.altair_chart(triage_chart, use_container_width=True)

    severity_chart = (
        alt.Chart(df_results)
        .mark_bar()
        .encode(alt.X("severity_index:Q", bin=alt.Bin(maxbins=10)), y="count():Q")
        .properties(title="Severity Index Distribution")
    )
    st.altair_chart(severity_chart, use_container_width=True)

    scatter_chart = (
        alt.Chart(df_results)
        .mark_circle(size=100)
        .encode(
            x="eta:Q",
            y="severity_index:Q",
            color="ownership:N",
            tooltip=["facility", "eta", "severity_index", "mortality_risk"]
        )
        .properties(title="ETA vs Severity (Ownership Segmented)")
    )
    st.altair_chart(scatter_chart, use_container_width=True)

else:
    st.info("Run a triage + diagnosis selection to generate analytics.")
