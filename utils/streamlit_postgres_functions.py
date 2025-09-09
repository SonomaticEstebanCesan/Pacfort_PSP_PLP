# -*- coding: utf-8 -*-
"""
Created on Wed Aug 27 15:27:14 2025

@author: Esti
"""

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, MetaData, Table, text
from sqlalchemy.exc import SQLAlchemyError
from datetime import date, datetime
from typing import Tuple, List, Dict
import re, unicodedata
import os
import logging


# --- Database Connection ---
# For Railway deployment, the DATABASE_URL is injected as an environment variable.
# The hardcoded URL is a fallback for local development only.
db_url = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:LlMQsPXTOlvnvtSwGJyitvqCOyhIOXzc@trolley.proxy.rlwy.net:43349/railway?sslmode=require"
)


# Cache the engine once per session
@st.cache_resource
def get_engine():
    return create_engine(db_url, pool_pre_ping=True)

# Cache the table loads (per table name)
@st.cache_data(show_spinner=False)
def load_table_from_db(table_name: str) -> pd.DataFrame:
    eng = get_engine()
    df = pd.read_sql(f'SELECT * FROM "{table_name}"', eng)

    # normalize date columns (per your schema)
    date_cols = [
        "DATE",
        "Requested Delivery date",
        "Delivered to FG on",
        "Delivered Partially On",
        "Delivered Complete on",
    ]
    for c in date_cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce").apply(
                lambda x: x.date() if pd.notna(x) else None
            )
    return df



LPO_SCHEMA = {
    "CLIENT": str,
    "DATE": "date",   # special case -> datetime.date
    "SALES MAN": str,
    "SO": str,
    "LI": int,
    "LPO": str,
    "ITEM CODE": str,
    "Category": str,
    "Order Qty": int,
    "UOM": str,
    "Requested Delivery date": "date",
    "Incoterms": str,
    "Location": str,
    "Lead Time days": int,
    "Lead Time Acceptance": str,
    "Status": str,
    "Delivered Qty": int,
    "Balance": int,
    "Delivered to FG on": "date",
    "Delivered Partially On": "date",
    "Delivered Complete on": "date",
    "PIFOT": str,
    "Reason": str,
    "Remarks": str,
}

SAMPLES_SCHEMA = {
    "CLIENT": str,
    "DATE": "date",
    "SALES MAN": str,
    "SO": str,
    "LI": int,
    "ITEM CODE": str,
    "Category": str,
    "Order Qty": int,
    "UOM": str,
    "Incoterm": str,  # singular for Samples
    "Requested Delivery date": "date",
    "Location": str,
    "Status": str,
    "Delivered Qty": int,
    "Balance": int,
    "Delivered to FG on": "date",
    "Delivered Partially On": "date",
    "Delivered Complete on": "date",
    "SOLI": str,
    "Remarks": str,
}

def _is_empty(v):
    # Treat None, "", NaN-like as empty
    try:
        if v is None:
            return True
        if isinstance(v, str) and v.strip() == "":
            return True
        # pd.isna handles np.nan, pd.NA, NAType
        return bool(pd.isna(v))
    except Exception:
        return False

def _norm_text(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    # Replace common non-breaking spaces with a normal space
    s = (s
         .replace("\u00A0", " ")  # NBSP
         .replace("\u2007", " ")  # Figure space
         .replace("\u202F", " ")) # Narrow NBSP
    # Trim *any* leading/trailing whitespace
    s = re.sub(r"^\s+|\s+$", "", s)
    return s

def _coerce_explicit(schema: dict, row: dict) -> tuple[dict, dict]:
    clean, errors = {}, {}

    for col, expected in schema.items():
        v = row.get(col, None)

        if _is_empty(v):
            clean[col] = None
            continue

        if expected == "date":
            if isinstance(v, date) and not isinstance(v, datetime):
                clean[col] = v
            elif isinstance(v, (datetime, pd.Timestamp)):
                clean[col] = v.date()
            elif isinstance(v, str):
                dt = pd.to_datetime(_norm_text(v), errors="coerce")
                if pd.isna(dt):
                    errors[col] = f'Invalid date string "{v}"'
                else:
                    clean[col] = dt.date()
            else:
                errors[col] = f"Expected date, got {type(v).__name__}"

        elif expected is int:
            try:
                if isinstance(v, float):
                    if not v.is_integer():
                        raise ValueError(f"non-integer float {v}")
                    v = int(v)
                clean[col] = int(v)
            except Exception:
                errors[col] = f"Expected integer, got {v} ({type(v).__name__})"

        elif expected is str:
            try:
                s = _norm_text(v)          # << normalize + trim (handles NBSP etc.)
                # Treat common sentinel strings as empty
                s_lower = s.lower()
                if s == "" or s_lower in {"nan", "none", "null"}:
                    clean[col] = None
                else:
                    clean[col] = s
            except Exception:
                errors[col] = f"Expected text, got {type(v).__name__}"

        else:
            clean[col] = v

    return clean, errors

def _coerce_subset(schema: dict, patch: dict) -> tuple[dict, dict]:
    subset_schema = {k: v for k, v in schema.items() if k in patch}
    return _coerce_explicit(subset_schema, patch)

def insert_order_row(table_name: str, row: dict) -> dict:
    eng = get_engine()
    if table_name == "LPO_PSPGermany":
        schema = LPO_SCHEMA
    elif table_name == "Samples_PSPGermany":
        schema = SAMPLES_SCHEMA   # ✅ use samples schema
    else:
        return {"ok": False, "error": f"No schema defined for {table_name}"}

    clean, errors = _coerce_explicit(schema, row)

    
    if not clean:
        return {"ok": False, "error": "No valid fields to update."}
    
    if errors:
        return {"ok": False, "error": "Validation failed", "errors": errors, "clean": clean}

    md = MetaData()
    tbl = Table(table_name, md, autoload_with=eng)

    # (optional) drop keys that aren't real columns
    clean = {k: v for k, v in clean.items() if k in tbl.c.keys()}


    try:
        with eng.begin() as conn:
            pk_col = list(tbl.primary_key.columns)[0]   # gets the real PK col
            res = conn.execute(tbl.insert().values(**clean).returning(pk_col))
            pk = res.scalar()
        return {"ok": True, "inserted_pk": pk, "clean": clean, "errors": {}}
    except Exception as e:
        logging.error(f"Database insert failed for table {table_name}", exc_info=True)
        return {"ok": False, "error": str(e), "clean": clean, "errors": {}}

def update_order_row(table_name: str, order_id: int, row: dict) -> dict:
    """Overwrite a specific row in the given table by primary key (Order_id)."""
    eng = get_engine()

    # Pick schema
    if table_name == "LPO_PSPGermany":
        schema = LPO_SCHEMA
    elif table_name == "Samples_PSPGermany":
        schema = SAMPLES_SCHEMA
    else:
        return {"ok": False, "error": f"No schema defined for {table_name}"}

    # Validate & coerce all fields
    clean, errors = _coerce_explicit(schema, row)

    if not clean:
        return {"ok": False, "error": "No valid fields to update."}

    if errors:
        return {
            "ok": False,
            "error": "Validation failed",
            "errors": errors,
            "clean": clean,
        }

    md = MetaData()
    tbl = Table(table_name, md, autoload_with=eng)

    # Drop keys not in actual table
    clean = {k: v for k, v in clean.items() if k in tbl.c.keys()}

    try:
        with eng.begin() as conn:
            pk_col = list(tbl.primary_key.columns)[0]  # usually "Order_id"
            stmt = tbl.update().where(pk_col == order_id).values(**clean)
            res = conn.execute(stmt)
            rowcount = res.rowcount

        return {
            "ok": True,
            "updated_pk": order_id,
            "rows_affected": rowcount,
            "clean": clean,
            "errors": {},
        }
    except Exception as e:
        logging.error(f"Database update failed for table {table_name}, pk {order_id}", exc_info=True)
        return {"ok": False, "error": str(e), "clean": clean, "errors": {}}