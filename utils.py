"""
utils.py
Data loading utilities for the AHECN demo build.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

def load_icd_catalogue() -> pd.DataFrame:
    p = DATA_DIR / "icd_catalogue.csv"
    df = pd.read_csv(p)
    # normalize columns
    df["bundle"] = df["bundle"].astype(str)
    df["icd10"] = df["icd10"].astype(str)
    df["label"] = df["label"].astype(str)
    df["default_caps"] = df["default_caps"].fillna("").astype(str)
    df["default_interventions"] = df["default_interventions"].fillna("").astype(str)
    return df

def load_facilities() -> pd.DataFrame:
    p = DATA_DIR / "meghalaya_facilities.csv"
    df = pd.read_csv(p)
    for c in ["lat","lon"]:
        df[c] = df[c].astype(float)
    df["ownership"] = df["ownership"].fillna("Private")
    return df
