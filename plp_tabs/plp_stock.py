# -*- coding: utf-8 -*-
"""
Created on Wed Sep 10 15:36:43 2025

@author: Esti
"""
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder
from datetime import date, timedelta

TAB_PREFIX = "plp_stock"

def _coerce_date_series(s):
    try:
        return pd.to_datetime(s, errors="coerce").dt.date
    except Exception:
        return s

def render(df1, df2):
    st.title("PLP Stock")

    # ---------- 1) Start from df1 and APPLY COERCION/FILTERS ----------
    filtered = df1.copy()

    # Coerce known date cols if they exist
    for col in [
        "DATE", "Requested Delivery date", "Delivered to FG on",
        "Delivered Partially On", "Delivered Complete on", "Delivery date"
    ]:
        if col in filtered.columns:
            filtered[col] = _coerce_date_series(filtered[col])

    # Filter UI
    col1, col2 = st.columns([2, 3])
    with col1:
        mode1 = st.segmented_control(
            "Choose Date mode:",
            options=["All", "Exact", "Range", "Month", "Week", "Relative"],
            key=f"{TAB_PREFIX}_mode"
        )
    with col2:
        status_options = ["All"]
        if "Status" in filtered.columns:
            status_options += sorted(x for x in filtered["Status"].dropna().unique().tolist())
        status_filter = st.segmented_control(
            "Status:", default="All", options=status_options, key=f"{TAB_PREFIX}_status"
        )

    # Status filter
    if status_filter != "All" and "Status" in filtered.columns:
        filtered = filtered[filtered["Status"] == status_filter]

    # Date filtering on DATE (skip safely if missing)
    if "DATE" in filtered.columns:
        if mode1 == "Exact":
            exact_d = st.date_input("Exact date:", value=None, key=f"{TAB_PREFIX}_exact")
            if exact_d:
                filtered = filtered[filtered["DATE"] == exact_d]

        elif mode1 == "Range":
            c1, c2 = st.columns(2)
            start_d = c1.date_input("Start date", value=None, key=f"{TAB_PREFIX}_start")
            end_d   = c2.date_input("End date",   value=None, key=f"{TAB_PREFIX}_end")
            if start_d and end_d:
                filtered = filtered[(filtered["DATE"] >= start_d) & (filtered["DATE"] <= end_d)]
            elif start_d:
                filtered = filtered[filtered["DATE"] >= start_d]
            elif end_d:
                filtered = filtered[filtered["DATE"] <= end_d]

        elif mode1 == "Month":
            c1, c2 = st.columns(2)
            year = c1.number_input("Year", 2000, 2100, date.today().year, key=f"{TAB_PREFIX}_year")
            month = c2.selectbox("Month", list(range(1, 13)),
                                 format_func=lambda m: f"{m:02d}", key=f"{TAB_PREFIX}_month")
            m_start = date(int(year), int(month), 1)
            nm = (m_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            m_end = nm - timedelta(days=1)
            filtered = filtered[(filtered["DATE"] >= m_start) & (filtered["DATE"] <= m_end)]

        elif mode1 == "Week":
            anchor = st.date_input("Any date in week", value=date.today(), key=f"{TAB_PREFIX}_week_anchor")
            if anchor:
                week_start = anchor - timedelta(days=anchor.weekday())
                week_end   = week_start + timedelta(days=6)
                filtered = filtered[(filtered["DATE"] >= week_start) & (filtered["DATE"] <= week_end)]

        elif mode1 == "Relative":
            choice = st.selectbox(
                "Range", ["Last 7 days", "Last 30 days", "Last 90 days", "This month", "YTD"],
                key=f"{TAB_PREFIX}_rel"
            )
            today = date.today()
            if choice == "Last 7 days":
                start, end = today - timedelta(days=6), today
            elif choice == "Last 30 days":
                start, end = today - timedelta(days=29), today
            elif choice == "Last 90 days":
                start, end = today - timedelta(days=89), today
            elif choice == "This month":
                start = today.replace(day=1)
                nm = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
                end = nm - timedelta(days=1)
            else:  # YTD
                start, end = date(today.year, 1, 1), today
            filtered = filtered[(filtered["DATE"] >= start) & (filtered["DATE"] <= end)]

    # Sort if Order_id exists
    if "Order_id" in filtered.columns:
        filtered = (
            filtered.assign(_Order_id_numeric=pd.to_numeric(filtered["Order_id"], errors="coerce"))
                    .sort_values(by="_Order_id_numeric", na_position="last")
                    .drop(columns="_Order_id_numeric")
                    .reset_index(drop=True)
        )
    else:
        filtered = filtered.reset_index(drop=True)

    # ---------- 2) Build grouped view (two blocks + separator) ----------
    # Block 1
    block1 = [
        "Client", "DATE", "SO", "LI", "SOLI",
        "ITEM CODE", "Category", "Order Qty",
        "Delivery date", "Status"
    ]
    block1_present = [c for c in block1 if c in filtered.columns]
    df_view = filtered[block1_present].copy()
    df_view["Actual Status"] = ""  # extra field at end of block 1

    # Block 2 (use unique field names to avoid duplicate columns)
    block2_original = [
        "DATE", "Client", "SO", "LI", "SOLI",
        "ITEM CODE", "Category", "Order Qty",
        "UOM", "Delivery date", "Status"
    ]
    block2_map = {orig: f"Stock_{orig}" for orig in block2_original}
    for new_col in block2_map.values():
        if new_col not in df_view.columns:
            df_view[new_col] = ""  # blank by default

    # Separator
    SEP_COL = "_sep_"
    df_view[SEP_COL] = ""

    # Column order: block1 -> Actual Status -> sep -> block2
    ordered_cols = block1_present + ["Actual Status"] + [SEP_COL] + list(block2_map.values())
    df_view = df_view[ordered_cols]

    # ---------- 3) Grid options ----------
    gb = GridOptionsBuilder.from_dataframe(df_view)
    gb.configure_default_column(editable=False, filter=True, sortable=True, resizable=True)

    # Separator styling
    gb.configure_column(
        SEP_COL,
        header_name="",
        width=20,
        editable=False,
        filter=False,
        sortable=False,
        resizable=False,
        suppressMenu=True,
    )

    grid_options = gb.build()

    # Retrieve generated column defs
    col_defs = {c["field"]: c for c in grid_options["columnDefs"]}

    block1_defs = [col_defs[c] for c in block1_present + ["Actual Status"] if c in col_defs]
    sep_def     = [col_defs[SEP_COL]]
    block2_defs = [col_defs[c] for c in block2_map.values() if c in col_defs]

    # Pretty headers for block 2 (show original names)
    for orig, new in block2_map.items():
        if new in col_defs:
            col_defs[new]["headerName"] = orig

    # Grouped headers
    grid_options["columnDefs"] = [
        {"headerName": "PLP_Orders", "marryChildren": True, "children": block1_defs},
        *sep_def,
        {"headerName": "STOCK", "marryChildren": True, "children": block2_defs},
    ]

    # ---------- 4) Render ----------
    AgGrid(
        df_view,
        gridOptions=grid_options,
        height=600,
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=True,
        theme="streamlit",
    )
