# -*- coding: utf-8 -*-
"""
Created on Tue Sep  2 13:21:52 2025

@author: Esti
"""

import streamlit as st

st.set_page_config(layout="wide", page_title="Dashboard Home")

st.title("Operations Dashboard")

cols = st.columns([1, 1])
with cols[0]:
    st.page_link("pages/1_GERMANY_PSP_postgres.py", label="Germany PSP", icon="🗂️")
with cols[1]:
    st.page_link("pages/2_GERMANY_PLP.py", label="Germany PLP", icon="🏭")

st.write("Pick a page from above or the sidebar.")