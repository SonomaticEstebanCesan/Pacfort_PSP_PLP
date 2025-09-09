# -*- coding: utf-8 -*-
"""
Created on Tue Sep  2 13:23:01 2025

@author: Esti
"""

import streamlit as st
import utils.streamlit_postgres_functions as spf

def ensure_bootstrap():
    if "bootstrapped" not in st.session_state:
        st.session_state.df1 = spf.load_table_from_db("LPO_PSPGermany")
        st.session_state.df2 = spf.load_table_from_db("Samples_PSPGermany")
        st.session_state.bootstrapped = True

def get_dataframes():
    return st.session_state.df1, st.session_state.df2