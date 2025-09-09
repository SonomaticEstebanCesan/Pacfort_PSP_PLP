# -*- coding: utf-8 -*-
"""
Created on Tue Sep  2 13:32:12 2025

@author: Esti
"""

import streamlit as st
from utils.data_bootstrap import ensure_bootstrap, get_dataframes

st.set_page_config(layout="wide", page_title="Germany PLP")

# ---------- shared bootstrap ----------
ensure_bootstrap()
df1, df2 = get_dataframes()

# ---------- define row 2 tabs ----------
row_2_tab_names = [
    "DPS", "S-LP", "P-LP", "DP-LP", "H-LP",
    "PP-LP", "D-Printing", "Summary-LP"
]

# init once
if "active_plp_tab" not in st.session_state:
    st.session_state.active_plp_tab = row_2_tab_names[0]

# one-shot navigation signal
if "pending_plp_tab" in st.session_state:
    st.session_state.active_plp_tab = st.session_state.pop("pending_plp_tab")
    st.rerun()

# drill-down state (optional, mirrors your PSP page style)
st.session_state.setdefault("active_order_id", None)
st.session_state.setdefault("last_navigated_order_id", None)
st.session_state.setdefault("pending_prefill", False)

# render segmented control for PLP row
st.segmented_control(
    "Germany PLP",
    row_2_tab_names,
    key="active_plp_tab",
)

# selected tab
chosen_tab = st.session_state.active_plp_tab

# ---------- placeholder content ----------
st.title("Germany PLP Dashboard")
st.write(f"Currently selected tab: **{chosen_tab}**")

st.info("This page is a placeholder. Add your PLP content here.")