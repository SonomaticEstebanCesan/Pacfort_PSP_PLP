# -*- coding: utf-8 -*-
"""
Created on Tue Sep  2 13:32:12 2025

@author: Esti
"""

# pages/1_GERMANY_PLP.py
import streamlit as st
from importlib import import_module
from utils.data_bootstrap import ensure_bootstrap, get_dataframes

st.set_page_config(layout="wide", page_title="Germany PLP")

# ---------- shared bootstrap ----------
ensure_bootstrap()
df1, df2 = get_dataframes()

# ---------- tab registry ----------
TAB_LABELS = [
    "PLP_Stock", "PLP_Sample_Stock",
    "DPS", "S-LP", "P-LP", "DP-LP", "H-LP",
    "PP-LP", "D-Printing", "Summary-LP",
]

TAB_MODULES = {
    "PLP_Stock": "plp_tabs.plp_stock",
    "PLP_Sample_Stock": "plp_tabs.plp_sample_stock",
    "DPS": "plp_tabs.dps",
    "S-LP": "plp_tabs.s_lp",
    "P-LP": "plp_tabs.p_lp",
    "DP-LP": "plp_tabs.dp_lp",
    "H-LP": "plp_tabs.h_lp",
    "PP-LP": "plp_tabs.pp_lp",
    "D-Printing": "plp_tabs.d_printing",
    "Summary-LP": "plp_tabs.summary_lp",
}

# ---------- session state ----------
st.session_state.setdefault("active_plp_tab", TAB_LABELS[0])
st.session_state.setdefault("active_order_id", None)
st.session_state.setdefault("last_navigated_order_id", None)
st.session_state.setdefault("pending_prefill", False)

# optional one-shot cross-tab navigation
if "pending_plp_tab" in st.session_state:
    st.session_state.active_plp_tab = st.session_state.pop("pending_plp_tab")
    st.rerun()

# ---------- UI ----------
st.segmented_control("Germany PLP", TAB_LABELS, key="active_plp_tab")
chosen = st.session_state.active_plp_tab

# ---------- dispatch the selected tab ----------
module_path = TAB_MODULES[chosen]
try:
    module = import_module(module_path)
except ModuleNotFoundError as e:
    st.error(
        f"Could not load module '{module_path}'. "
        "Make sure 'plp_tabs/' is a folder (package) at project root with an '__init__.py', "
        f"and contains the file for this tab. Details: {e}"
    )
else:
    # Each tab module must implement: render(df1, df2)
    if hasattr(module, "render"):
        module.render(df1=df1, df2=df2)
    else:
        st.error(f"Module '{module_path}' is missing a `render(df1, df2)` function.")

# Optional: page header / helper info (can be removed)
st.caption(
    "Tip: Run from the project root (where `app.py` lives) so imports like `plp_tabs.dps` work."
)
