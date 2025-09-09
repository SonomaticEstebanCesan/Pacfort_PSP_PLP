# -*- coding: utf-8 -*-
"""
Created on Tue Aug  5 10:34:55 2025

@author: Esti
"""

# cd C:\Users\Esti\OneDrive - Sonomatic Ltd\Python Scripts\Pacfort
# streamlit run GERMANY_PSP_postgres.py


import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder
from datetime import datetime
from datetime import date, timedelta
import utils.streamlit_postgres_functions as spf
from utils.data_bootstrap import ensure_bootstrap, get_dataframes

st.set_page_config(layout="wide")

# Use session copies for filtering etc. (no DB hits on widget changes)
ensure_bootstrap()
df1, df2 = get_dataframes()

# # Optional: session-only manual refresh button
# if st.button("🔄 Refresh data for this session"):
#     spf.load_table_from_db.clear()  # <-- invalidate cache
#     st.session_state.df1 = spf.load_table_from_db("LPO_PSPGermany")
#     st.session_state.df2 = spf.load_table_from_db("Samples_PSPGermany")
#     df1, df2 = st.session_state.df1, st.session_state.df2
#     st.rerun()


# Define tab names
tab_names = [
    "LPO",
    "SAMPLES",
    "Edit Existing Order",
    "Add New Order",
    "Today Delivery Schedule",
    "Next Day Delivery Schedule",
    "Today Delivery Schedule - Sample",
    "Next Day Delivery Schedule - Sample"
]

# Initialize once
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "LPO"

# one-shot navigation signal set from other parts of the app
if "pending_tab" in st.session_state:
    st.session_state.active_tab = st.session_state.pop("pending_tab")
    st.rerun()  # apply the change before the widget is created
    
# drill-down state
st.session_state.setdefault("active_order_id", None)
st.session_state.setdefault("last_navigated_order_id", None)
st.session_state.setdefault("pending_prefill", False)

# Segmented control, bound to session_state directly
st.segmented_control(
    "Germany PSP",
    tab_names,
    key="active_tab"   # <-- key ties it to session_state
)

# Use value from session_state everywhere
chosen_tab = st.session_state.active_tab

 
#### TAB 1
if chosen_tab == "LPO":

    # ---------- Filters header ----------
    col1, col2 = st.columns([2, 3])
    with col1:
        mode1 = st.segmented_control(
            "Choose Date mode:",
            options=["All", "Exact", "Range", "Month", "Week", "Relative"],
            key="orders_LPO_mode"
        )
    with col2:
        STATUS_VALUES = ["", "Cancelled", "Delivered", "FG Full", "Held by Finance", "In Progress", "Partialy Delivered", "Voided"]
        status_options = ["All"] + [v for v in STATUS_VALUES if v != ""]
        status_filter = st.segmented_control(
            "Status:",
            default="All",
            options=status_options,
            key="orders_LPO_status"
        )

    base_df1 = df1.copy()

    # Apply status filter
    if status_filter != "All":
        base_df1 = base_df1[base_df1["Status"] == status_filter]

    # ---------- Date filtering ----------
    if mode1 == "Exact":
        exact_d = st.date_input("Exact date:", value=None, key="orders_exact")
        if exact_d:
            base_df1 = base_df1[base_df1["DATE"] == exact_d]

    elif mode1 == "Range":
        c1, c2 = st.columns(2)
        start_d = c1.date_input("Start date", value=None, key="orders_start")
        end_d = c2.date_input("End date", value=None, key="orders_end")
        if start_d and end_d:
            base_df1 = base_df1[(base_df1["DATE"] >= start_d) & (base_df1["DATE"] <= end_d)]
        elif start_d:
            base_df1 = base_df1[base_df1["DATE"] >= start_d]
        elif end_d:
            base_df1 = base_df1[base_df1["DATE"] <= end_d]

    elif mode1 == "Month":
        c1, c2 = st.columns(2)
        year = c1.number_input(
            "Year",
            min_value=2000,
            max_value=2100,
            value=date.today().year,
            step=1,
            key="orders_year"
        )
        month = c2.selectbox(
            "Month",
            list(range(1, 13)),
            format_func=lambda m: f"{m:02d}",
            key="orders_month"
        )
        m_start = date(int(year), int(month), 1)
        nm = (m_start.replace(day=28) + timedelta(days=4)).replace(day=1)  # first day next month
        m_end = nm - timedelta(days=1)
        base_df1 = base_df1[(base_df1["DATE"] >= m_start) & (base_df1["DATE"] <= m_end)]

    elif mode1 == "Week":
        anchor = st.date_input("Any date in week", value=date.today(), key="orders_week_anchor")
        if anchor:
            week_start = anchor - timedelta(days=anchor.weekday())  # Monday
            week_end = week_start + timedelta(days=6)               # Sunday
            base_df1 = base_df1[(base_df1["DATE"] >= week_start) & (base_df1["DATE"] <= week_end)]

    elif mode1 == "Relative":
        choice = st.selectbox(
            "Range",
            ["Last 7 days", "Last 30 days", "Last 90 days", "This month", "YTD"],
            key="orders_rel"
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
        base_df1 = base_df1[(base_df1["DATE"] >= start) & (base_df1["DATE"] <= end)]

    # ---------- Grid setup ----------
    base_df1 = (
        base_df1.assign(_Order_id_numeric=pd.to_numeric(base_df1["Order_id"], errors="coerce"))
                 .sort_values(by="_Order_id_numeric", na_position="last")
                 .drop(columns="_Order_id_numeric")
                 .reset_index(drop=True)
    )    
    filtered_df = base_df1
    gb1 = GridOptionsBuilder.from_dataframe(filtered_df)

    date_columns = [
        "DATE",
        "Requested Delivery date",
        "Delivered to FG on",
        "Delivered Partially On",
        "Delivered Complete on"
    ]

    for col in date_columns:
        if col in filtered_df.columns:  # avoid errors if some don’t exist
            gb1.configure_column(
                col,
                type=["dateColumnFilter", "customDateTimeFormat"],
                custom_format_string="yyyy-MM-dd"  # optional display format
            )

    gb1.configure_default_column(editable=False, filter=True)
    gb1.configure_selection(selection_mode="single", use_checkbox=False)
    
    # Enable clipboard and range selection
    gb1.configure_grid_options(
        enableRangeSelection=True,
        enableClipboard=True,
        enableCellTextSelection=True
    )


    # ---------- Column widths ----------
    column_widths = {
        "Order_id": 10,
        'CLIENT': 120,
        'DATE': 110,
        'SALES MAN': 140,
        'SO': 90,
        'LI': 70,
        'LPO': 120,
        'ITEM CODE': 130,
        'Category': 120,
        'Order Qty': 90,
        'UOM': 70,
        'Requested Delivery date': 130,
        'Incoterms': 100,
        'Location': 120,
        'Lead Time days': 110,
        'Lead Time Acceptance': 150,
        'Status': 100,
        'Delivered Qty': 110,
        'Balance': 90,
        'Delivered to FG on': 130,
        'Delivered Partially On': 140,
        'Delivered Complete on': 140,
        'PIFOT': 80,
        'Reason': 150,
        'Remarks': 180
    }

    for col, width in column_widths.items():
        gb1.configure_column(col, width=width)

    # ---------- Build grid ----------
    grid_options1 = gb1.build()

    response1 = AgGrid(
        filtered_df,
        gridOptions=grid_options1,
        editable=False,
        height=600,
        fit_columns_on_grid_load=False,  # disables autofit so fixed widths work
        allow_unsafe_jscode=True,
        theme="streamlit",
        enable_enterprise_modules=True  # Needed for Excel export, clipboard, etc
    )
    edited_df1 = response1['data']
    
    selected = response1.get("selected_rows", [])
    
    # Normalize and check emptiness safely
    if isinstance(selected, pd.DataFrame):
        has_sel = not selected.empty
    elif isinstance(selected, list):
        has_sel = len(selected) > 0
    else:
        has_sel = False
    
    if has_sel:
        # Extract the first selected Order_id regardless of shape
        if isinstance(selected, pd.DataFrame):
            sel_id = selected.iloc[0]["Order_id"]
        else:  # list of dicts
            sel_id = selected[0].get("Order_id")
    
        if st.session_state.get("last_navigated_order_id") != sel_id:
            st.session_state["active_order_id"] = sel_id
            st.session_state["last_navigated_order_id"] = sel_id
            st.session_state["pending_prefill"] = True
            st.session_state["active_dataset"] = "LPO" 
            st.session_state["pending_tab"] = "Edit Existing Order"
            st.rerun()

    
    # st.write(edited_df1)


#### TAB 2
elif chosen_tab == "SAMPLES":
    # Two controls in a row
    col1, col2 = st.columns([2,3])
    
    with col1:
        mode2 = st.segmented_control(
            "Choose Date mode:",
            options=["All", "Exact", "Range", "Month", "Week", "Relative"],
            key="orders_Sample_mode"
        )
    
    with col2:
        STATUS_VALUES = ["", "Cancelled", "Delivered", "FG Full", "Held by Finance", "In Progress", "Partialy Delivered", "Voided"]
        status_options = ["All"] + [v for v in STATUS_VALUES if v != ""]
        status_filter = st.segmented_control(
            "Status:",
            default="All",
            options=status_options,
            key="orders_Sample_status"
        )

    
    base_df2 = df2.copy()

    if status_filter != "All":
        base_df2 = base_df2[base_df2["Status"] == status_filter] 
        
    if mode2 == "Exact":
        exact_d = st.date_input("Exact date:", value=None, key="samples_exact")
        if exact_d:
            base_df2 = base_df2[base_df2["DATE"] == exact_d]
    
    elif mode2 == "Range":
        c1, c2 = st.columns(2)
        start_d = c1.date_input("Start date", value=None, key="samples_start")
        end_d   = c2.date_input("End date", value=None, key="samples_end")
        if start_d and end_d:
            base_df2 = base_df2[(base_df2["DATE"] >= start_d) & (base_df2["DATE"] <= end_d)]
        elif start_d:
            base_df2 = base_df2[base_df2["DATE"] >= start_d]
        elif end_d:
            base_df2 = base_df2[base_df2["DATE"] <= end_d]
    
    elif mode2 == "Month":
        c1, c2 = st.columns(2)
        year  = c1.number_input("Year", min_value=2000, max_value=2100, value=date.today().year, step=1, key="samples_year")
        month = c2.selectbox("Month", list(range(1, 13)), format_func=lambda m: f"{m:02d}", key="samples_month")
        # compute month start/end
        m_start = date(int(year), int(month), 1)
        m_end = (date(int(year) + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1) - timedelta(days=1))
        base_df2 = base_df2[(base_df2["DATE"] >= m_start) & (base_df2["DATE"] <= m_end)]
    
    elif mode2 == "Week":
        # pick any date in the target week; we normalize to Mon-Sun
        anchor = st.date_input("Any date in week", value=date.today(), key="samples_week_anchor")
        if anchor:
            week_start = anchor - timedelta(days=anchor.weekday())         # Monday
            week_end   = week_start + timedelta(days=6)                    # Sunday
            base_df2 = base_df2[(base_df2["DATE"] >= week_start) & (base_df2["DATE"] <= week_end)]
    
    elif mode2 == "Relative":
        choice = st.selectbox("Range", ["Last 7 days", "Last 30 days", "Last 90 days", "This month", "YTD"], key="samples_rel")
        today = date.today()
        if choice == "Last 7 days":
            start = today - timedelta(days=6)
            end = today
        elif choice == "Last 30 days":
            start = today - timedelta(days=29)
            end = today
        elif choice == "Last 90 days":
            start = today - timedelta(days=89)
            end = today
        elif choice == "This month":
            start = today.replace(day=1)
            # next month first day
            nm = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
            end = nm - timedelta(days=1)
        else:  # YTD
            start = date(today.year, 1, 1)
            end = today
        base_df2 = base_df2[(base_df2["DATE"] >= start) & (base_df2["DATE"] <= end)]
    
    
    # Use base_df2 downstream instead of df2
    # --- ALWAYS sort by Order_id before showing ---
    ID_COL_SAMPLES = "Sample_id"  # <-- adjust if your column is named differently
    
    if ID_COL_SAMPLES in base_df2.columns:
        base_df2 = (
            base_df2.assign(_id_num=pd.to_numeric(base_df2[ID_COL_SAMPLES], errors="coerce"))
                    .sort_values("_id_num", kind="mergesort")
                    .drop(columns="_id_num")
                    .reset_index(drop=True)
        )
    
    filtered_df2 = base_df2

    gb2 = GridOptionsBuilder.from_dataframe(filtered_df2)

    # Apply date filter UI + format to all date columns (same set used in tab1)
    date_columns_2 = [
        "DATE",
        "Requested Delivery date",
        "Delivered to FG on",
        "Delivered Partially On",
        "Delivered Complete on",
    ]
    for col in date_columns_2:
        if col in filtered_df2.columns:
            gb2.configure_column(
                col,
                type=["dateColumnFilter", "customDateTimeFormat"],
                custom_format_string="yyyy-MM-dd"
            )

    # ---------- READ-ONLY: disable all editing ----------
    gb2.configure_default_column(editable=False, filter=True)

    # Selection: single row, no checkbox
    gb2.configure_selection(selection_mode="single", use_checkbox=False)

    # (Optional) allow selection/copy, but block any click-to-edit or paste edits
    gb2.configure_grid_options(
        enableRangeSelection=True,
        enableClipboard=True,
        enableCellTextSelection=True,
        suppressClickEdit=True,
        readOnlyEdit=True,
        suppressRowClickSelection=False,   # <- make sure row clicks select
    )

    # Column widths (your map for Samples)
    column_widths_2 = {
        'CLIENT': 300,
        'DATE': 110,
        'SALES MAN': 140,
        'SO': 90,
        'LI': 70,
        'ITEM CODE': 130,
        'Category': 120,
        'Order Qty': 90,
        'UOM': 70,
        'Incoterm': 100,  # note: 'Incoterm' (singular) in Samples schema
        'Requested Delivery date': 130,
        'Location': 120,
        'Status': 100,
        'Delivered Qty': 110,
        'Balance': 90,
        'Delivered to FG on': 130,
        'Delivered Partially On': 140,
        'Delivered Complete on': 140,
        'SOLI': 100,
        'Remarks': 180
    }
    for col, width in column_widths_2.items():
        if col in filtered_df2.columns:
            gb2.configure_column(col, width=width)

    grid_options2 = gb2.build()
    
    response2 = AgGrid(
        filtered_df2,
        gridOptions=grid_options2,
        editable=False,
        height=600,
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=True,
        theme="streamlit",
        enable_enterprise_modules=True
    )

    edited_df2 = response2["data"]
    
    selected2 = response2.get("selected_rows", [])
    
    # Normalize selection and read the correct ID column for Samples
    if isinstance(selected2, pd.DataFrame):
        has_sel = not selected2.empty
        sel_id = selected2.iloc[0].get(ID_COL_SAMPLES) if has_sel else None
    elif isinstance(selected2, list):
        has_sel = len(selected2) > 0
        sel_id = selected2[0].get(ID_COL_SAMPLES) if has_sel else None
    else:
        has_sel, sel_id = False, None
    
    if has_sel and sel_id is not None:
        if st.session_state.get("last_navigated_order_id_samples") != sel_id:
            st.session_state["active_order_id"] = sel_id
            st.session_state["active_dataset"] = "Samples"
            st.session_state["pending_prefill"] = True
            st.session_state["pending_tab"] = "Edit Existing Order"
            st.session_state["last_navigated_order_id_samples"] = sel_id
            st.rerun()

#### TAB 3A
elif chosen_tab == "Edit Existing Order":
    # one-time toast
    flash = st.session_state.pop("flash_toast", None)
    if flash:
        st.toast(flash)
    
    dataset_default = st.session_state.get("active_dataset", "LPO")
    active_id = st.session_state.get("active_order_id")
    
    # consume one-shot prefill flag (optional)
    if st.session_state.get("pending_prefill"):
        st.session_state.pending_prefill = False
    
    # --- Dataset dropdown (LPO / Samples) ---
    dataset_choice = st.selectbox(
        "Choose dataset:",
        ["LPO", "Samples"],
        index=(0 if dataset_default == "LPO" else 1),
        key="edit_dataset_selector"
    )
    
    # pick df + id column per dataset
    id_col = "Order_id" if dataset_choice == "LPO" else "Sample_id"
    df = df1 if dataset_choice == "LPO" else df2
    
    if not df.empty:
        # sort by the correct id column (numeric-safe)
        if id_col in df.columns:
            df = (
                df.assign(_id_num=pd.to_numeric(df[id_col], errors="coerce"))
                  .sort_values("_id_num", kind="mergesort")
                  .drop(columns="_id_num")
                  .reset_index(drop=True)
            )
    
        # build display strings using the correct id column
        display_cols = [id_col, "CLIENT", "ITEM CODE"]
        options = [
            " | ".join(str(row[col]) for col in display_cols if col in df.columns)
            for _, row in df.iterrows()
        ]
        option_map = {disp: row for disp, (_, row) in zip(options, df.iterrows())}
    
        # compute default index from active_id
        default_index = 0
        if active_id is not None and id_col in df.columns:
            hits = df.index[df[id_col] == active_id].tolist()
            if hits:
                default_index = hits[0]
    
        # persistent key so Streamlit doesn't lose selection across reruns
        selected_display = st.selectbox(
            "Choose order:",
            options,
            index=default_index,
            key="edit_order_selector"
        )
        selected_row = option_map[selected_display]
    
        # keep session in sync with current selection
        try:
            st.session_state["active_order_id"] = int(selected_row[id_col])
        except Exception:
            st.session_state["active_order_id"] = selected_row[id_col]
    
        # also remember which dataset we're editing
        st.session_state["active_dataset"] = dataset_choice
    
    else:
        st.info("No orders available in this dataset.")
        selected_row = None

    
    # =========================
    # LPO SECTION (no form)
    # =========================
    def _to_int_safe(v, default=0):
        try:
            if v is None:
                return default
            if isinstance(v, float) and pd.isna(v):
                return default
            return int(v)
        except Exception:
            return default
    
    def collect_unique(dfs, col):
        series_list = [d[col] for d in dfs if col in d.columns]
        if not series_list:
            return []
        return (
            pd.concat(series_list, ignore_index=True)
              .dropna()
              .astype(str)
              .unique()
              .tolist()
        )
    
    item_code_options = sorted(collect_unique([df1, df2], "ITEM CODE"))
    sales_man_options = sorted(collect_unique([df1, df2], "SALES MAN"))
    

    def _to_date_safe(v):
        if v is None:
            return None
        try:
            return pd.to_datetime(v).date() if not isinstance(v, date) else v
        except Exception:
            return None
    
    
    if dataset_choice == "LPO":
        if selected_row is None:
            row = {}
        elif isinstance(selected_row, dict):
            row = selected_row
        elif hasattr(selected_row, "to_dict"):  # pandas Series/DataFrame row
            row = selected_row.to_dict()
        else:
            row = {}

        row_order_id          = row.get("Order_id") #there
        row_client            = row.get("CLIENT")#there
        row_status            = row.get("Status")#there
        row_sales_man         = row.get("SALES MAN")#there
        row_item_code         = row.get("ITEM CODE") #there
        row_date              = _to_date_safe(row.get("DATE"))
        row_so                = "" if row.get("SO") is None else str(row.get("SO"))#there
        row_li                = int(row.get("LI") or 0)#there
        row_lpo               = "" if row.get("LPO") is None else str(row.get("LPO"))
        row_category          = row.get("Category")#there
        row_order_qty         = int(row.get("Order Qty") or 0)#there
        row_uom               = row.get("UOM") #there
        row_req_deliv_date    = _to_date_safe(row.get("Requested Delivery date"))#there
        row_incoterms         = row.get("Incoterm") #there
        row_location          = row.get("Location")#there
        row_lead_time_days    = int(row.get("Lead Time days") or 0)
        row_lead_time_accept  = row.get("Lead Time Acceptance")
        row_pifot             = row.get("PIFOT")
        row_reason            = row.get("Reason")
        row_remarks           = "" if row.get("Remarks") is None else str(row.get("Remarks"))
    
        # --- Row 1: Order_id / CLIENT / Status ---
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("Order_id", value=row_order_id or "", key="edit_lpo_order_id_display", disabled=True)
        with c2:
            st.text_input("CLIENT", value=row_client or "", key="edit_lpo_client_display", disabled=True)
        with c3:
            status_options = ["", "Cancelled", "Delivered", "FG Full", "Held by Finance", "In Progress", "Partialy Delivered", "Voided"]
            status_index = status_options.index(row_status) if row_status in status_options else 0
            status = st.selectbox("Status", status_options, index=status_index, key="edit_lpo_status")
        
        # --- Row 2: SALES MAN / ITEM CODE / DATE (now 3 columns) ---
        c1, c2, c3 = st.columns(3)
        with c1:
            sales_man_options_full = ["", "➕ Add new…"] + sales_man_options
            sm_index = sales_man_options_full.index(row_sales_man) if row_sales_man in sales_man_options_full else 0
            edit_sales_sel = st.selectbox("SALES MAN", sales_man_options_full, index=sm_index, key="edit_lpo_sales_sel")
            edit_sales_new = st.text_input("New SALES MAN", key="edit_lpo_sales_new") if edit_sales_sel == "➕ Add new…" else ""
            sales_man = (edit_sales_new if edit_sales_sel == "➕ Add new…" else ("" if edit_sales_sel == "" else edit_sales_sel))
        
        with c2:
            item_code_options_full = ["", "➕ Add new…"] + item_code_options
            ic_index = item_code_options_full.index(row_item_code) if row_item_code in item_code_options_full else 0
            edit_item_sel = st.selectbox("ITEM CODE", item_code_options_full, index=ic_index, key="edit_lpo_item_sel")
            edit_item_new = st.text_input("New ITEM CODE", key="edit_lpo_item_new") if edit_item_sel == "➕ Add new…" else ""
            item_code = (edit_item_new if edit_item_sel == "➕ Add new…" else ("" if edit_item_sel == "" else edit_item_sel))
        
        with c3:
            date_ = st.date_input("DATE", value=row_date, key="edit_lpo_date")
        
        # --- Row 3: SO / LI / LPO ---
        c1, c2, c3 = st.columns(3)
        with c1:
            so = st.text_input("SO", value=row_so, key="edit_lpo_so")
        with c2:
            li = st.number_input(
                "LI",
                min_value=0,
                step=1,
                value=_to_int_safe(row.get("LI")),
                key="edit_lpo_li"
            )
        with c3:
            lpo = st.text_input("LPO", value=row_lpo, key="edit_lpo_lpo")
        
        # --- Row 4: Category / Order Qty / UOM ---
        c1, c2, c3 = st.columns(3)
        with c1:
            cat_options = ["", "DP", "SI", "Third Party"]
            cat_index = cat_options.index(row_category) if row_category in cat_options else 0
            category = st.selectbox("Category", cat_options, index=cat_index, key="edit_lpo_cat")
        with c2:
            order_qty = st.number_input(
                "Order Qty",
                min_value=0,
                step=1,
                value=_to_int_safe(row.get("Order Qty")),
                key="edit_lpo_qty"
            )

        with c3:
            uom_options = ["", "Pieces"]
            uom_index = uom_options.index(row_uom) if row_uom in uom_options else 0
            uom = st.selectbox("UOM", uom_options, index=uom_index, key="edit_lpo_uom")
        
        # --- Row 5: Requested Delivery date / Incoterms / Location ---
        c1, c2, c3 = st.columns(3)
        with c1:
            req_deliv_date = st.date_input("Requested Delivery date", value=row_req_deliv_date, key="edit_lpo_req_date")
        with c2:
            incoterms_options = ["", "DAP", "CIF", "CFR", "Ex-Work", "DDP", "DDU"]
            inc_index = incoterms_options.index(row_incoterms) if row_incoterms in incoterms_options else 0
            incoterms = st.selectbox("Incoterms", incoterms_options, index=inc_index, key="edit_lpo_incoterms")
        with c3:
            location = st.text_input("Location", value=row_location or "", key="edit_lpo_loc")
        
        # --- Row 6: Lead Time days / Lead Time Acceptance / PIFOT ---
        c1, c2, c3 = st.columns(3)
        with c1:
            lead_time_days = st.number_input(
                "Lead Time days",
                min_value=0,
                step=1,
                value=_to_int_safe(row.get("Lead Time days")),
                key="edit_lpo_lead_days"
            )
        with c2:
            lta_options = ["", "Acceptable", "Not Acceptable"]
            lta_index = lta_options.index(row_lead_time_accept) if row_lead_time_accept in lta_options else 0
            lead_time_accept = st.selectbox("Lead Time Acceptance", lta_options, index=lta_index, key="edit_lpo_lead_acc")
        with c3:
            pifot_options = ["", "PIFOT", "NO PIFOT"]
            pifot_index = pifot_options.index(row_pifot) if row_pifot in pifot_options else 0
            pifot = st.selectbox("PIFOT", pifot_options, index=pifot_index, key="edit_lpo_pifot")
        
        # --- Row 7: Delivered Qty / Balance / Delivered to FG on ---
        c1, c2, c3 = st.columns(3)
        with c1:
            delivered_qty = st.number_input(
                "Delivered Qty",
                min_value=0,
                step=1,
                value=_to_int_safe(row.get("Delivered Qty")),
                key="edit_lpo_delivered_qty"
            )
        with c2:
            # Balance is calculated, not user-editable
            balance_val = (order_qty or 0) - (delivered_qty or 0)
            st.number_input(
                "Balance",
                value=balance_val,
                key="edit_lpo_balance",
                disabled=True
            )
        with c3:
            delivered_fg_on = st.date_input(
                "Delivered to FG on",
                value=_to_date_safe(row.get("Delivered to FG on")),
                key="edit_lpo_delivered_fg_on"
            )
        
        # --- Row 8: Delivered Partially On / Delivered Complete on / Reason ---
        c1, c2, c3 = st.columns(3)
        
        with c1:
            delivered_partially_on = st.date_input(
                "Delivered Partially On",
                value=_to_date_safe(row.get("Delivered Partially On")),
                key="edit_lpo_delivered_partially_on"
            )
        
        with c2:
            delivered_complete_on = st.date_input(
                "Delivered Complete on",
                value=_to_date_safe(row.get("Delivered Complete on")),
                key="edit_lpo_delivered_complete_on"
            )
        
        with c3:
            reason_options = ["", "Production", "Operations", "Sales"]
            reason_index = reason_options.index(row_reason) if row_reason in reason_options else 0
            reason = st.selectbox(
                "Reason",
                reason_options,
                index=reason_index,
                key="edit_lpo_reason"
            )
        
        # --- Row 9: Remarks (full width) ---
        remarks_val = "" if row_remarks is None or str(row_remarks).lower() == "nan" else str(row_remarks)
        remarks = st.text_area(
            "Remarks",
            value=remarks_val,
            key="edit_lpo_remarks",
            height=80
        )
        
        if st.button("Update Order", key="edit_lpo_save_btn"):
            order_id = row.get("Order_id")
            
            updated = {
                "CLIENT": row_client,  # read-only; still included for clarity
                "DATE": pd.to_datetime(date_) if date_ else None,
                "SALES MAN": sales_man or None,
                "SO": so or None,
                "LI": int(li) if li is not None else None,
                "LPO": lpo or None,
                "ITEM CODE": item_code or None,
                "Category": category or None,
                "Order Qty": int(order_qty) if order_qty is not None else None,
                "UOM": uom or None,
                "Requested Delivery date": pd.to_datetime(req_deliv_date) if req_deliv_date else None,
                "Incoterms": incoterms or None,
                "Location": location or None,
                "Lead Time days": int(lead_time_days) if lead_time_days is not None else None,
                "Lead Time Acceptance": lead_time_accept or None,
                "Status": status or None,
                "Delivered Qty": int(delivered_qty) if delivered_qty is not None else None,
                "Balance": (int(order_qty) if order_qty is not None else 0) - (int(delivered_qty) if delivered_qty is not None else 0),
                "Delivered to FG on": pd.to_datetime(delivered_fg_on) if delivered_fg_on else None,
                "Delivered Partially On": pd.to_datetime(delivered_partially_on) if delivered_partially_on else None,
                "Delivered Complete on": pd.to_datetime(delivered_complete_on) if delivered_complete_on else None,
                "Reason": reason or None,
                "PIFOT": pifot or None,
                "Remarks": (remarks or "").strip() or None,
            }

            result = spf.update_order_row("LPO_PSPGermany", order_id, updated)
        
            if result.get("ok"):
                spf.load_table_from_db.clear()
                st.session_state.df1 = spf.load_table_from_db("LPO_PSPGermany")
                st.session_state["flash_toast"] = f"✅ Order {order_id} updated."
                st.rerun()
            else:
                st.error(f'Update failed: {result.get("error")}')

    elif dataset_choice == "Samples":
        # --- normalize selected_row to a dict ---
        if selected_row is None:
            row = {}
        elif isinstance(selected_row, dict):
            row = selected_row
        elif hasattr(selected_row, "to_dict"):
            row = selected_row.to_dict()
        else:
            row = {}
    
        # pull fields from the row (Samples schema)
        row_sample_id         = row.get("Sample_id")  # <-- PK for Samples
        row_client            = row.get("CLIENT")
        row_status            = row.get("Status")
        row_sales_man         = row.get("SALES MAN")
        row_item_code         = row.get("ITEM CODE")
        row_date              = _to_date_safe(row.get("DATE"))
        row_so                = "" if row.get("SO") is None else str(row.get("SO"))
        row_li                = _to_int_safe(row.get("LI"))
        row_category          = row.get("Category")
        row_order_qty         = _to_int_safe(row.get("Order Qty"))
        row_uom               = row.get("UOM")
        row_incoterm          = row.get("Incoterm")  # singular in Samples
        row_req_deliv_date    = _to_date_safe(row.get("Requested Delivery date"))
        row_location          = row.get("Location")
        row_status            = row.get("Status")
        row_delivered_qty     = _to_int_safe(row.get("Delivered Qty"))
        row_delivered_fg_on   = _to_date_safe(row.get("Delivered to FG on"))
        row_delivered_part_on = _to_date_safe(row.get("Delivered Partially On"))
        row_delivered_comp_on = _to_date_safe(row.get("Delivered Complete on"))
        row_soli              = "" if row.get("SOLI") is None else str(row.get("SOLI"))
        row_remarks           = "" if row.get("Remarks") is None else str(row.get("Remarks"))
        row_reason            = row.get("Reason")  # if you store a reason for Samples too
        

        # --- Row 1: Sample_id / CLIENT / Status ---
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("Sample_id", value=row_sample_id or "", key="edit_samp_id_display", disabled=True)
        with c2:
            st.text_input("CLIENT", value=row_client or "", key="edit_samp_client_display", disabled=True)
        with c3:
            status_options = ["", "Cancelled", "Delivered", "FG Full", "Held by Finance", "In Progress", "Partialy Delivered", "Voided"]
            status_index = status_options.index(row_status) if row_status in status_options else 0
            status = st.selectbox("Status", status_options, index=status_index, key="edit_samp_status")
    
        # --- Row 2: SALES MAN / ITEM CODE / DATE ---
        c1, c2, c3 = st.columns(3)
        with c1:
            sales_man_options_full = ["", "➕ Add new…"] + sales_man_options
            sm_index = sales_man_options_full.index(row_sales_man) if row_sales_man in sales_man_options_full else 0
            edit_sales_sel = st.selectbox("SALES MAN", sales_man_options_full, index=sm_index, key="edit_samp_sales_sel")
            edit_sales_new = st.text_input("New SALES MAN", key="edit_samp_sales_new") if edit_sales_sel == "➕ Add new…" else ""
            sales_man = (edit_sales_new if edit_sales_sel == "➕ Add new…" else ("" if edit_sales_sel == "" else edit_sales_sel))
    
        with c2:
            item_code_options_full = ["", "➕ Add new…"] + item_code_options
            ic_index = item_code_options_full.index(row_item_code) if row_item_code in item_code_options_full else 0
            edit_item_sel = st.selectbox("ITEM CODE", item_code_options_full, index=ic_index, key="edit_samp_item_sel")
            edit_item_new = st.text_input("New ITEM CODE", key="edit_samp_item_new") if edit_item_sel == "➕ Add new…" else ""
            item_code = (edit_item_new if edit_item_sel == "➕ Add new…" else ("" if edit_item_sel == "" else edit_item_sel))
    
        with c3:
            date_ = st.date_input("DATE", value=row_date, key="edit_samp_date")
    
        # --- Row 3: SO / LI / Category ---
        c1, c2, c3 = st.columns(3)
        with c1:
            so = st.text_input("SO", value=row_so, key="edit_samp_so")
        with c2:
            li = st.number_input("LI", min_value=0, step=1, value=row_li, key="edit_samp_li")
        with c3:
            cat_options = ["", "DP", "SI", "Third Party"]
            cat_index = cat_options.index(row_category) if row_category in cat_options else 0
            category = st.selectbox("Category", cat_options, index=cat_index, key="edit_samp_cat")
    
        # --- Row 4: Order Qty / UOM / Incoterm ---
        c1, c2, c3 = st.columns(3)
        with c1:
            order_qty = st.number_input("Order Qty", min_value=0, step=1, value=row_order_qty, key="edit_samp_qty")
        with c2:
            uom_options = ["", "Pieces"]
            uom_index = uom_options.index(row_uom) if row_uom in uom_options else 0
            uom = st.selectbox("UOM", uom_options, index=uom_index, key="edit_samp_uom")
        with c3:
            incoterm_options = ["", "DAP", "CIF", "CFR", "Ex-Work", "DDP", "DDU"]
            inc_index = incoterm_options.index(row_incoterm) if row_incoterm in incoterm_options else 0
            incoterm = st.selectbox("Incoterm", incoterm_options, index=inc_index, key="edit_samp_incoterm")
    
        # --- Row 5: Requested Delivery date / Location / SOLI ---
        c1, c2, c3 = st.columns(3)
        with c1:
            req_deliv_date = st.date_input("Requested Delivery date", value=row_req_deliv_date, key="edit_samp_req_date")
        with c2:
            location = st.text_input("Location", value=row_location or "", key="edit_samp_loc")
        with c3:
            soli = st.text_input("SOLI", value=row_soli, key="edit_samp_soli")
    
        # --- Row 6: Delivered Qty / Balance / Delivered to FG on ---
        c1, c2, c3 = st.columns(3)
        with c1:
            delivered_qty = st.number_input("Delivered Qty", min_value=0, step=1, value=row_delivered_qty, key="edit_samp_delivered_qty")
        with c2:
            balance_val = (order_qty or 0) - (delivered_qty or 0)
            st.number_input("Balance", value=balance_val, key="edit_samp_balance", disabled=True)
        with c3:
            delivered_fg_on = st.date_input("Delivered to FG on", value=row_delivered_fg_on, key="edit_samp_delivered_fg_on")
    
        # --- Row 7: Delivered Partially On / Delivered Complete on / Reason ---
        c1, c2, c3 = st.columns(3)
        with c1:
            delivered_partially_on = st.date_input("Delivered Partially On", value=row_delivered_part_on, key="edit_samp_delivered_partially_on")
        with c2:
            delivered_complete_on = st.date_input("Delivered Complete on", value=row_delivered_comp_on, key="edit_samp_delivered_complete_on")
        with c3:
            reason_options = ["", "Production", "Operations", "Sales"]
            reason_index = reason_options.index(row_reason) if row_reason in reason_options else 0
            reason = st.selectbox("Reason", reason_options, index=reason_index, key="edit_samp_reason")
    
        # --- Row 8: Remarks (full width) ---
        remarks_val = "" if row_remarks is None or str(row_remarks).lower() == "nan" else str(row_remarks)
        remarks = st.text_area("Remarks", value=remarks_val, key="edit_samp_remarks", height=80)
    
        if st.button("Update Sample", key="edit_samp_save_btn"):
            sample_id = row.get("Sample_id")  # ensure this matches your PK column name
    
            updated = {
                "CLIENT": row_client,  # read-only display; still included
                "DATE": pd.to_datetime(date_) if date_ else None,
                "SALES MAN": sales_man or None,
                "SO": so or None,
                "LI": int(li) if li is not None else None,
                "ITEM CODE": item_code or None,
                "Category": category or None,
                "Order Qty": int(order_qty) if order_qty is not None else None,
                "UOM": uom or None,
                "Incoterm": incoterm or None,  # singular
                "Requested Delivery date": pd.to_datetime(req_deliv_date) if req_deliv_date else None,
                "Location": location or None,
                "Status": status or None,
                "Delivered Qty": int(delivered_qty) if delivered_qty is not None else None,
                "Balance": (int(order_qty) if order_qty is not None else 0) - (int(delivered_qty) if delivered_qty is not None else 0),
                "Delivered to FG on": pd.to_datetime(delivered_fg_on) if delivered_fg_on else None,
                "Delivered Partially On": pd.to_datetime(delivered_partially_on) if delivered_partially_on else None,
                "Delivered Complete on": pd.to_datetime(delivered_complete_on) if delivered_complete_on else None,
                "SOLI": soli or None,
                "Reason": reason or None,
                "Remarks": (remarks or "").strip() or None,
            }
    
            # write to the Samples table
            result = spf.update_order_row("Samples_PSPGermany", sample_id, updated)
    
            if result.get("ok"):
                spf.load_table_from_db.clear()
                st.session_state.df2 = spf.load_table_from_db("Samples_PSPGermany")
                st.session_state["flash_toast"] = f"✅ Sample {sample_id} updated."
                st.rerun()
            else:
                st.error(f'Update failed: {result.get("error")}')
        
#### TAB 3B
elif chosen_tab == "Add New Order":
 
        
    order_type = st.selectbox("Order Type", ["LPO", "Sample Order"], key="tab3_order_type_nf")
    
    flash = st.session_state.pop("flash_toast", None)
    
    if flash:
        st.toast(flash)
    # options source
    df_source = df1 if order_type == "LPO" else df2
    def collect_unique(dfs, col):
        series_list = [d[col] for d in dfs if col in d.columns]
        if not series_list:
            return []
        return (
            pd.concat(series_list, ignore_index=True)
              .dropna()
              .astype(str)
              .unique()
              .tolist()
        )
    
    item_code_options = sorted(collect_unique([df1, df2], "ITEM CODE"))
    client_options   = sorted(collect_unique([df1, df2], "CLIENT"))
    sales_man_options = sorted(collect_unique([df1, df2], "SALES MAN"))
    
    st.write("Fill in the order details:")

    # =========================
    # LPO SECTION (no form)
    # =========================
    if order_type == "LPO":
        # Gating dropdowns (instant rerun → shows “New …” inputs)
        c1, c2, c3 = st.columns(3)
        with c1:
            client_sel = st.selectbox("CLIENT", ["", "➕ Add new…"] + client_options, key="lpo_client_sel")
            client_new = st.text_input("New CLIENT", key="lpo_client_new") if client_sel == "➕ Add new…" else ""
            client = client_new if client_sel == "➕ Add new…" else ("" if client_sel == "" else client_sel)
        with c2:
            sales_sel = st.selectbox("SALES MAN", ["", "➕ Add new…"] + sales_man_options, key="lpo_sales_sel")
            sales_new = st.text_input("New SALES MAN", key="lpo_sales_new") if sales_sel == "➕ Add new…" else ""
            sales_man = sales_new if sales_sel == "➕ Add new…" else ("" if sales_sel == "" else sales_sel)
        with c3:
            item_sel = st.selectbox("ITEM CODE", ["", "➕ Add new…"] + item_code_options, key="lpo_item_sel")
            item_new = st.text_input("New ITEM CODE", key="lpo_item_new") if item_sel == "➕ Add new…" else ""
            item_code = item_new if item_sel == "➕ Add new…" else ("" if item_sel == "" else item_sel)

        # Remaining inputs
        c1, c2, c3 = st.columns(3)
        with c1:
            date_ = st.date_input("DATE", key="lpo_date")
        with c2:
            so = st.text_input("SO", key="lpo_so")
        with c3:
            li = st.number_input("LI", min_value=0, step=1, key="lpo_li")

        c1, c2, c3 = st.columns(3)
        with c1:
            lpo = st.text_input("LPO", key="lpo_lpo")
        with c2:
            category = st.selectbox("Category", ["", "DP", "SI", "Third Party"], key="lpo_cat")
        with c3:
            order_qty = st.number_input("Order Qty", min_value=0, step=1, key="lpo_qty")

        c1, c2, c3 = st.columns(3)
        with c1:
            uom = st.selectbox("UOM", ["", "Pieces"], key="lpo_uom")
        with c2:
            req_deliv_date = st.date_input("Requested Delivery date", key="lpo_req_date")
        with c3:
            incoterms = st.selectbox("Incoterms", ["", "DAP","CIF","CFR","Ex-Work","DDP","DDU"], key="lpo_incoterms")

        c1, c2, c3 = st.columns(3)
        with c1:
            location = st.text_input("Location", key="lpo_loc")
        with c2:
            lead_time_days = st.number_input("Lead Time days", min_value=0, step=1, key="lpo_lead_days")
        with c3:
            lead_time_accept = st.selectbox("Lead Time Acceptance", ["", "Acceptable", "Not Acceptable"], key="lpo_lead_acc")

        c1, c2, c3 = st.columns(3)
        with c1:
            status = st.selectbox("Status", ["", "Cancelled", "Delivered", "FG Full", "Held by Finance", "In Progress", "Partialy Delivered", "Voided"], key="lpo_status")
        with c2:
            pifot = st.selectbox("PIFOT", ["", "PIFOT", "NO PIFOT"], key="lpo_pifot")
        with c3:
            reason = st.selectbox("Reason", ["", "Production", "Operations", "Sales"], key="lpo_reason")

        remarks = st.text_area("Remarks", key="lpo_remarks")

        # Insert button (no form)
        if st.button("Add LPO Order", key="btn_add_lpo"):
            new_row = {
                "CLIENT": client,
                "DATE": pd.to_datetime(date_) if date_ else None,
                "SALES MAN": sales_man,
                "SO": so,
                "LI": int(li),
                "LPO": lpo,
                "ITEM CODE": item_code,
                "Category": category,
                "Order Qty": int(order_qty),
                "UOM": uom,
                "Requested Delivery date": pd.to_datetime(req_deliv_date) if req_deliv_date else None,
                "Incoterms": incoterms,
                "Location": location,
                "Lead Time days": int(lead_time_days),
                "Lead Time Acceptance": lead_time_accept,
                "Status": status,
                "PIFOT": pifot,
                "Reason": reason,
                "Remarks": remarks,
            }
            new_row = {k: v for k, v in new_row.items() if v is not None}

            result = spf.insert_order_row("LPO_PSPGermany", new_row)
            if result.get("ok"):
                spf.load_table_from_db.clear()
                st.session_state.df1 = spf.load_table_from_db("LPO_PSPGermany")
                st.session_state["flash_toast"] = f'✅ Order added to LPO! (Order_id={result.get("inserted_pk")})'
                st.rerun()
            else:
                st.error(f'Insert failed: {result.get("error")}')
                for col, msg in (result.get("errors") or {}).items():
                    st.warning(f"{col}: {msg}")


    # =========================
    # SAMPLES SECTION (no form)
    # =========================
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            client_sel = st.selectbox("CLIENT", ["", "➕ Add new…"] + client_options, key="samp_client_sel")
            client_new = st.text_input("New CLIENT", key="samp_client_new") if client_sel == "➕ Add new…" else ""
            client = client_new if client_sel == "➕ Add new…" else ("" if client_sel == "" else client_sel)
        with c2:
            sales_sel = st.selectbox("SALES MAN", ["", "➕ Add new…"] + sales_man_options, key="samp_sales_sel")
            sales_new = st.text_input("New SALES MAN", key="samp_sales_new") if sales_sel == "➕ Add new…" else ""
            sales_man = sales_new if sales_sel == "➕ Add new…" else ("" if sales_sel == "" else sales_sel)
        with c3:
            item_sel = st.selectbox("ITEM CODE", ["", "➕ Add new…"] + item_code_options, key="samp_item_sel")
            item_new = st.text_input("New ITEM CODE", key="samp_item_new") if item_sel == "➕ Add new…" else ""
            item_code = item_new if item_sel == "➕ Add new…" else ("" if item_sel == "" else item_sel)

        c1, c2, c3 = st.columns(3)
        with c1:
            date_ = st.date_input("DATE", key="samp_date")
        with c2:
            so = st.text_input("SO", key="samp_so")
        with c3:
            li = st.number_input("LI", min_value=0, step=1, key="samp_li")

        c1, c2, c3 = st.columns(3)
        with c1:
            category = st.selectbox("Category", ["", "DP", "SI", "Third Party"], key="samp_cat")
        with c2:
            order_qty = st.number_input("Order Qty", min_value=0, step=1, key="samp_qty")
        with c3:
            uom = st.selectbox("UOM", ["", "Pieces"], key="samp_uom")

        c1, c2, c3 = st.columns(3)
        with c1:
            incoterm = st.selectbox("Incoterm", ["", "DAP","CIF","CFR","Ex-Work","DDP","DDU"], key="samp_incoterm")
        with c2:
            req_deliv_date = st.date_input("Requested Delivery date", key="samp_req_date")
        with c3:
            location = st.text_input("Location", key="samp_loc")

        c1, c2, c3 = st.columns(3)
        with c1:
            status = st.selectbox("Status", ["", "Cancelled", "Delivered", "FG Full", "Held by Finance", "In Progress", "Partialy Delivered"], key="samp_status")
        with c2:
            soli = st.text_input("SOLI", key="samp_soli")
        with c3:
            st.write("")

        remarks = st.text_area("Remarks", key="samp_remarks")

        if st.button("Add Sample Order", key="btn_add_samples"):
            new_row = {
                "CLIENT": client,
                "DATE": pd.to_datetime(date_) if date_ else None,
                "SALES MAN": sales_man,
                "SO": so,
                "LI": int(li),
                "ITEM CODE": item_code,
                "Category": category,
                "Order Qty": int(order_qty),
                "UOM": uom,
                "Incoterm": incoterm,
                "Requested Delivery date": pd.to_datetime(req_deliv_date) if req_deliv_date else None,
                "Location": location,
                "Status": status,
                "SOLI": soli,
                "Remarks": remarks,
            }
            new_row = {k: v for k, v in new_row.items() if v is not None}
            print(new_row)
            try:
                result = spf.insert_order_row("Samples_PSPGermany", new_row)
            except Exception as e:
                st.exception(e)  # shows full traceback
            
            if result.get("ok"):
                spf.load_table_from_db.clear()
                st.session_state.df2 = spf.load_table_from_db("Samples_PSPGermany")
                st.session_state["flash_toast"] = f'✅ Order added to Sample Orders! (Sample_id={result.get("inserted_pk")})'
                st.rerun()
            else:
                st.error(f'Insert failed: {result.get("error")}')
                for col, msg in (result.get("errors") or {}).items():
                    st.warning(f"{col}: {msg}")


    # Optional debug
    # st.markdown("### Debug: Current session_state keys/values")
    # st.json(st.session_state)

#### TAB 4
elif chosen_tab == "Today Delivery Schedule":
    st.title("Today Delivery Schedule")
    today_str = datetime.now().strftime("%A %B %d %Y")
    st.write(today_str)
    
    delivery_columns = ["CLIENT", "SALES MAN", "SO", "LI", "SOLI", "Order Qty", "ITEM CODE"]

    # Ensure date column is datetime
    df1['Requested Delivery date'] = pd.to_datetime(df1['Requested Delivery date'], errors='coerce')

    today = pd.Timestamp(datetime.now().date())

    # Filter rows for today
    df_delivery = df1[df1['Requested Delivery date'] == today]

    # Only keep columns that exist
    existing_columns = [col for col in delivery_columns if col in df_delivery.columns]
    df_delivery = df_delivery[existing_columns]

    gb3 = GridOptionsBuilder.from_dataframe(df_delivery)
    gb3.configure_default_column(editable=True, filter=True)
    grid_options3 = gb3.build()

    response3 = AgGrid(
        df_delivery,
        gridOptions=grid_options3,
        editable=True,
        height=400,
        fit_columns_on_grid_load=True,
        allow_unsafe_jscode=True,
        theme="streamlit"
    )
    edited_df3 = response3['data']
   
#### TAB 5
elif chosen_tab == "Next Day Delivery Schedule":
    st.title("Next Day Delivery Schedule")
    next_day = (date.today() + timedelta(days=1)).strftime('%A %B %d %Y')
    st.write(f"Next day: **{next_day}**")
    
    next_day_columns = ["CLIENT", "SALES MAN", "SO", "LI", "SOLI", "Order Qty", "ITEM CODE"]

    # Ensure date column is datetime and matches name used in tab3
    df1['Requested Delivery date'] = pd.to_datetime(df1['Requested Delivery date'], errors='coerce')

    # Filter for next day's deliveries
    next_day_ts = pd.Timestamp(date.today() + timedelta(days=1))
    df_next_day = df1[df1['Requested Delivery date'] == next_day_ts]

    # Only keep columns that exist
    existing_columns = [col for col in next_day_columns if col in df_next_day.columns]
    df_next_day = df_next_day[existing_columns]

    gb4 = GridOptionsBuilder.from_dataframe(df_next_day)
    gb4.configure_default_column(editable=True, filter=True)
    grid_options4 = gb4.build()

    response4 = AgGrid(
        df_next_day,
        gridOptions=grid_options4,
        editable=True,
        height=400,
        fit_columns_on_grid_load=True,
        allow_unsafe_jscode=True,
        theme="streamlit"
    )
    edited_df4 = response4['data']

#### TAB 6    
elif chosen_tab == "Today Delivery Schedule - Sample":
    st.title("Today Delivery Schedule - Sample")
    today_str = datetime.now().strftime("%A %B %d %Y")
    st.write(today_str)

    delivery_columns = ["CLIENT", "SALES MAN", "SO", "LI", "SOLI", "Order Qty", "ITEM CODE"]

    df2['Requested Delivery date'] = pd.to_datetime(df2['Requested Delivery date'], errors='coerce').dt.date
    today = date.today()
    df2_today = df2[df2["Requested Delivery date"] == today]

    # Only keep columns that exist and re-create the DataFrame to bulletproof against pandas weirdness
    existing_columns = [col for col in delivery_columns if col in df2_today.columns]
    df2_today_display = pd.DataFrame(df2_today[existing_columns].values, columns=existing_columns)


    if df2_today_display.empty:
        st.info("No sample deliveries scheduled for today.")
        st.dataframe(pd.DataFrame(columns=existing_columns))
    else:
        gb5 = GridOptionsBuilder.from_dataframe(df2_today_display)
        gb5.configure_default_column(editable=True, filter=True)
        grid_options5 = gb5.build()

        response5 = AgGrid(
            df2_today_display,
            gridOptions=grid_options5,
            editable=True,
            height=400,
            fit_columns_on_grid_load=True,
            allow_unsafe_jscode=True,
            theme="streamlit"
        )
        edited_df2_today = response5['data']
        
#### TAB 7
elif chosen_tab == "Next Day Delivery Schedule - Sample":
    st.title("Next Day Delivery Schedule - Sample")
    next_day = (date.today() + timedelta(days=1))
    next_day_str = next_day.strftime("%A %B %d %Y")
    st.write(f"Next day: {next_day_str}")

    delivery_columns = ["CLIENT", "SALES MAN", "SO", "LI", "SOLI", "Order Qty", "ITEM CODE"]

    df2['Requested Delivery date'] = pd.to_datetime(df2['Requested Delivery date'], errors='coerce').dt.date
    df2_next_day = df2[df2["Requested Delivery date"] == next_day]

    # Only keep columns that exist and re-create the DataFrame to bulletproof against pandas weirdness
    existing_columns = [col for col in delivery_columns if col in df2_next_day.columns]
    df2_next_day_display = pd.DataFrame(df2_next_day[existing_columns].values, columns=existing_columns)

    if df2_next_day_display.empty:
        st.info("No sample deliveries scheduled for the next day.")
        st.dataframe(pd.DataFrame(columns=existing_columns))
    else:
        gb6 = GridOptionsBuilder.from_dataframe(df2_next_day_display)
        gb6.configure_default_column(editable=True, filter=True)
        grid_options6 = gb6.build()

        response6 = AgGrid(
            df2_next_day_display,
            gridOptions=grid_options6,
            editable=True,
            height=400,
            fit_columns_on_grid_load=True,
            allow_unsafe_jscode=True,
            theme="streamlit"
        )
        edited_df2_next_day = response6['data']

