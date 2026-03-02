import streamlit as st
import pandas as pd

from config import *
from clinical_engine import triage_engine
from scoring_engine import calculate_facility_score
from routing_engine import get_eta
from analytics_engine import compute_dashboard_metrics
from synthetic_data import generate_case

st.set_page_config(layout="wide")
st.title(APP_NAME)
st.caption(APP_VERSION)

# ----------------------
# Triage Input
# ----------------------
st.sidebar.header("Clinical Input")

age = st.sidebar.number_input("Age",0,120,30)
hr = st.sidebar.number_input("HR",20,200,90)
rr = st.sidebar.number_input("RR",5,60,18)
sbp = st.sidebar.number_input("SBP",50,220,120)
spo2 = st.sidebar.number_input("SpO2",50,100,98)

vitals = {"hr":hr,"rr":rr,"sbp":sbp,"spo2":spo2}
icd_row = {"icd10":"I21.9","label":"Acute MI"}

color, meta = triage_engine(vitals, icd_row, {"age":age})

st.subheader(f"Triage Result: {color}")
st.json(meta)

# ----------------------
# Facility Matching
# ----------------------
facilities = [
    {"name":"Shillong Civil Hospital","lat":25.57,"lon":91.89,"ICU_open":3,"ownership":"Government","caps":["ICU","CathLab"]},
    {"name":"Private Care Hospital","lat":25.60,"lon":91.92,"ICU_open":2,"ownership":"Private","caps":["ICU","CathLab"]}
]

src = (25.58,91.89)
results = []

for f in facilities:
    eta = get_eta(src,(f["lat"],f["lon"]))
    score, details = calculate_facility_score(f,["ICU"],eta,color)
    if score > 0:
        results.append({"facility":f["name"],"score":score,"eta":eta,"ownership":f["ownership"]})

results = sorted(results,key=lambda x:x["score"],reverse=True)

st.subheader("Recommended Facilities")
st.table(pd.DataFrame(results))

# ----------------------
# Analytics
# ----------------------
demo_records = []
for _ in range(200):
    bundle,v = generate_case()
    c,_ = triage_engine(v,{"icd10":"A41.9","label":"Sepsis"}, {})
    demo_records.append({"bundle":bundle,"triage_color":c,"ownership":"Government"})

df = pd.DataFrame(demo_records)
metrics = compute_dashboard_metrics(df)

st.subheader("Government Analytics")
st.metric("Total Cases",metrics["total_cases"])
st.metric("RED Rate %",metrics["red_rate"])
st.metric("Gov Utilization %",metrics["gov_utilization"])
