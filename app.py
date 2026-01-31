import streamlit as st
import pandas as pd
from io import BytesIO

# ==============================================================
# PAGE CONFIG
# ==============================================================
st.set_page_config(
    page_title="Store Stock Health & Replenishment Planner",
    layout="wide"
)

# ==============================================================
# 🔐 STORE LOGIN (STORE ONLY)  ✅ ADDED
# ==============================================================
st.title("🔐 Store Login")

stores = list(st.secrets["stores"].keys())
selected_store = st.selectbox("Select Store", stores)
password = st.text_input("Password", type="password")

if password != st.secrets["stores"][selected_store]:
    st.warning("❌ Incorrect password")
    st.stop()

STORE_CODE = selected_store
st.success(f"✅ Logged in as {STORE_CODE}")

# ==============================================================
# HEADER
# ==============================================================
st.image("LCW_LOGO.png", width=250)
st.title("Store Stock Health & Replenishment Planner")
st.caption("LC WAIKIKI RETAIL MA – Warehouse → Sales Area Intelligence")
st.caption(f"📍 Store: {STORE_CODE}")

# ==============================================================
# FILE UPLOAD
# ==============================================================
sales_file = st.file_uploader("Upload Sales Report (Excel)", type=["xlsx"])
stock_file = st.file_uploader("Upload Stock Report (Excel)", type=["xlsx"])

# ==============================================================
# AUTO-DETECT UTILITIES
# ==============================================================
def detect_column(df, possible_names):
    for col in df.columns:
        if col.strip().lower() in [p.lower() for p in possible_names]:
            return col
    return None

def standardize_sales_columns(df):
    mapping = {
        "Specialcode1": detect_column(df, ["Specialcode1", "Special Code"]),
        "Qty_Sold": detect_column(df, ["Quantity", "Qty"]),
        "Merch Group": detect_column(df, ["Merch Group", "Top Group"]),
        "Color": detect_column(df, ["Color", "RenkKodu"])
    }
    missing = [k for k, v in mapping.items() if v is None]
    if missing:
        st.error(f"❌ Sales report missing columns: {missing}")
        st.stop()
    return df.rename(columns={v: k for k, v in mapping.items()})

def standardize_stock_columns(df):
    mapping = {
        "Specialcode1": detect_column(df, ["Specialcode1", "Special Code"]),
        "Merch Group": detect_column(df, ["Merch Group", "Top Group"]),
        "Color": detect_column(df, ["Color", "RenkKodu"]),
        "Warehouse": detect_column(df, ["Warehouse", "WH"]),
        "RAYON": detect_column(df, ["RAYON", "Store"]),
        "Cash": detect_column(df, ["Cash", "Price"]),
        "Location_Quantity": detect_column(
            df, ["Location: Quantity", "Location Quantity", "Location_Qty"]
        ),
        "EtiketTip": detect_column(
            df, ["EtiketTip", "Etiket Tip", "Label Type"]
        )
    }
    missing = [k for k, v in mapping.items() if v is None]
    if missing:
        st.error(f"❌ Stock report missing columns: {missing}")
        st.stop()
    return df.rename(columns={v: k for k, v in mapping.items()})

def export_to_excel(dfs):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in dfs.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return output.getvalue()

# ==============================================================
# MAIN LOGIC
# ==============================================================
if sales_file and stock_file:
    ...
    # (NO CHANGES BELOW THIS LINE)
    ...
    st.download_button(
        "⬇️ Download Daily Store Action Plan",
        export_to_excel({
            "Best_Sellers": best_sellers,
            "Immediate_Replenishment": blocked,
            "Merch_Group_Action_Plan": merch_occ
        }),
        file_name=f"LCW_{STORE_CODE}_Daily_Action_Plan.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("📥 Please upload Sales & Stock Excel files to start analysis.")
