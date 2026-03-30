from __future__ import annotations

import io
import json
from typing import List

import pandas as pd
import requests
import streamlit as st

API_URL = "http://localhost:8000/validate_batch"

st.set_page_config(page_title="Q-Nexus Prototype", layout="wide")

st.title("Q-NEXUS Prototype – Synthesizability Filter")
st.caption("Prototype pipeline: Z3 rules + RDKit checks + stability proxy")

uploaded = st.file_uploader("Upload CSV (first column used as SMILES)", type=["csv"])

smiles_list: List[str] = []
if uploaded:
    data = pd.read_csv(io.BytesIO(uploaded.read()))
    if data.empty:
        st.error("CSV is empty")
    else:
        first_col = data.columns[0]
        smiles_list = data[first_col].astype(str).tolist()

input_smiles = st.text_area("Or paste SMILES (one per line)")
if input_smiles.strip():
    smiles_list = [s.strip() for s in input_smiles.splitlines() if s.strip()]

if st.button("Run Validation"):
    if not smiles_list:
        st.warning("Provide at least one SMILES string")
    else:
        with st.spinner("Validating..."):
            try:
                response = requests.post(API_URL, json={"smiles_list": smiles_list}, timeout=60)
                response.raise_for_status()
                results = response.json()
            except requests.exceptions.RequestException as exc:
                st.error("Cannot reach API at http://localhost:8000. Start the API server first.")
                st.caption(f"Details: {exc}")
                st.stop()

        df = pd.DataFrame(results)
        st.subheader("Results")
        st.dataframe(df, use_container_width=True)

        pass_rate = (df["verdict"] == "PASS").mean() * 100
        st.metric("Pass Rate", f"{pass_rate:.1f}%")

        st.subheader("Raw JSON")
        st.code(json.dumps(results, indent=2))
