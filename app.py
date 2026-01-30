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
# HEADER
# ==============================================================
st.image("LCW_LOGO.png", width=250)
st.title("Store Stock Health & Replenishment Planner")
st.caption("LC WAIKIKI RETAIL MA – Warehouse → Sales Area Intelligence")

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

    sales_df = standardize_sales_columns(pd.read_excel(sales_file))
    stock_df = standardize_stock_columns(pd.read_excel(stock_file))

    for df in [sales_df, stock_df]:
        df["Specialcode1"] = df["Specialcode1"].astype(str).str.strip()
        df["Merch Group"] = df["Merch Group"].astype(str).str.upper().str.strip()
        df["Color"] = df["Color"].astype(str).str.upper().str.strip()

    stock_df["EtiketTip"] = stock_df["EtiketTip"].astype(str).str.upper().str.strip()

    EXCLUDED_CODE = "W5LV19Z8"
    sales_df = sales_df[sales_df["Specialcode1"] != EXCLUDED_CODE]
    stock_df = stock_df[stock_df["Specialcode1"] != EXCLUDED_CODE]

    # ==========================================================
    # BEST SELLERS
    # ==========================================================
    best_sellers = (
        sales_df
        .groupby(["Specialcode1", "Merch Group", "Color"], as_index=False)
        .agg(Qty_Sold=("Qty_Sold", "sum"))
        .sort_values("Qty_Sold", ascending=False)
    )

    stock_summary = (
        stock_df
        .groupby(["Specialcode1", "Merch Group", "Color"], as_index=False)
        .agg(
            Warehouse=("Warehouse", "sum"),
            RAYON=("RAYON", "sum"),
            Cash=("Cash", "mean")
        )
    )

    best_sellers = best_sellers.merge(
        stock_summary,
        on=["Specialcode1", "Merch Group", "Color"],
        how="left"
    ).fillna(0)

    best_sellers["🚨 Blocked Best Seller"] = best_sellers.apply(
        lambda x: "YES 🚨" if x["Warehouse"] > 0 and x["RAYON"] <= 3 else "NO",
        axis=1
    )

    best_sellers["Cash"] = best_sellers["Cash"].astype(int)
    best_sellers.rename(columns={"Specialcode1": "Special Code"}, inplace=True)

    # ==========================================================
    # MERGED DATA
    # ==========================================================
    merged = stock_df.copy()
    merged["Total_PCS"] = merged["Warehouse"] + merged["RAYON"]

    # ==========================================================
    # 🚨 IMMEDIATE REPLENISHMENT
    # ==========================================================
    blocked = (
        merged[(merged["Warehouse"] > 0) & (merged["RAYON"] == 0)]
        .groupby(["Specialcode1", "Merch Group", "Color"], as_index=False)
        .agg(
            Warehouse=("Warehouse", "sum"),
            RAYON=("RAYON", "sum"),
            Location_Quantity=("Location_Quantity", "sum"),
            Cash=("Cash", "mean")
        )
    )

    blocked["Value_At_Risk_MAD"] = blocked["Warehouse"] * blocked["Cash"]
    blocked["Urgency_Level"] = blocked["Warehouse"].apply(
        lambda x: "🟢 NORMAL" if x < 3 else "🟠 HIGH" if x <= 8 else "🔴 CRITICAL"
    )

    blocked.rename(columns={"Specialcode1": "Special Code"}, inplace=True)
    blocked = blocked.sort_values("Value_At_Risk_MAD", ascending=False)

    # ==========================================================
    # CAPACITY & FEASIBILITY
    # ==========================================================
    capacity_df = pd.DataFrame({
        "Merch Group": ["BG", "BU", "CK", "CU", "EV", "ST"],
        "Capacity": [9694, 8429, 7823, 7298, 129, 1294]
    })

    merch_occ = (
        merged.groupby("Merch Group")
        .agg(RAYON=("RAYON", "sum"), Warehouse=("Warehouse", "sum"))
        .reset_index()
        .merge(capacity_df, on="Merch Group", how="left")
    )

    merch_occ["Actual_Occupancy_%"] = merch_occ["RAYON"] / merch_occ["Capacity"] * 100
    merch_occ["PCS_To_Push_Today"] = (merch_occ["Capacity"] - merch_occ["RAYON"]).clip(lower=0)
    merch_occ["PCS_To_Push_Today"] = merch_occ[["PCS_To_Push_Today", "Warehouse"]].min(axis=1)
    merch_occ["Occupancy_After_Push_%"] = (
        (merch_occ["RAYON"] + merch_occ["PCS_To_Push_Today"]) / merch_occ["Capacity"] * 100
    )

    # ==========================================================
    # 🧩 FRAGMENTATION
    # ==========================================================
    fragmented = (
        merged.groupby(["Merch Group", "Specialcode1"], as_index=False)
        .agg(Total_PCS=("Total_PCS", "sum"))
    )

    fragmented = fragmented[fragmented["Total_PCS"] <= 4]

    frag_summary = (
        fragmented.groupby("Merch Group")
        .agg(Fragmented_PCS=("Total_PCS", "sum"))
        .reset_index()
    )

    merch_occ = merch_occ.merge(frag_summary, on="Merch Group", how="left").fillna(0)
    merch_occ["Total_PCS"] = merch_occ["RAYON"] + merch_occ["Warehouse"]
    merch_occ["Fragmentation_%"] = merch_occ["Fragmented_PCS"] / merch_occ["Total_PCS"] * 100

    total_capacity = capacity_df["Capacity"].sum()

    # ==========================================================
    # KPIs
    # ==========================================================
    total_rayon = merged["RAYON"].sum()
    total_wh = merged["Warehouse"].sum()
    total_push = merch_occ["PCS_To_Push_Today"].sum()
    total_frag = merch_occ["Fragmented_PCS"].sum()

    discounted_df = stock_df[stock_df["EtiketTip"] == "KIRMIZI"]
    discounted_qty = discounted_df["Warehouse"].sum() + discounted_df["RAYON"].sum()
    discounted_pct = discounted_qty / (total_wh + total_rayon) * 100

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📦 Warehouse %", f"{total_wh / (total_wh + total_rayon) * 100:.2f}%")
    k2.metric("🏬 Rayon Occupancy %", f"{total_rayon / total_capacity * 100:.2f}%")
    k3.metric("📦 Total Warehouse Qty", int(total_wh))
    k4.metric("📦 PCS to Push Today", int(total_push))

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("🏬 Occupancy After Push %", f"{(total_rayon + total_push) / total_capacity * 100:.2f}%")
    k6.metric("🧩 Fragmented PCS", int(total_frag))
    k7.metric("🧩 Fragmentation %", f"{total_frag / (total_wh + total_rayon) * 100:.2f}%")
    k8.metric("🏷️ Discounted PCS", f"{int(discounted_qty)} ({discounted_pct:.2f}%)")

    # ==========================================================
    # 📊 DISCOUNTED PER MERCH GROUP (WITH %)
    # ==========================================================
    st.subheader("🏷️ Discounted Products per Merch Group")

    discounted_mg = (
        stock_df[stock_df["EtiketTip"] == "KIRMIZI"]
        .groupby("Merch Group", as_index=False)
        .agg(
            Discounted_Warehouse=("Warehouse", "sum"),
            Discounted_RAYON=("RAYON", "sum")
        )
    )

    discounted_mg["Total_Discounted_PCS"] = (
        discounted_mg["Discounted_Warehouse"] + discounted_mg["Discounted_RAYON"]
    )

    total_mg_pcs = (
        merged.groupby("Merch Group")
        .agg(Total_PCS=("Total_PCS", "sum"))
        .reset_index()
    )

    discounted_mg = discounted_mg.merge(
        total_mg_pcs, on="Merch Group", how="left"
    )

    discounted_mg["Discounted_%"] = (
        discounted_mg["Total_Discounted_PCS"] / discounted_mg["Total_PCS"] * 100
    )

    st.dataframe(discounted_mg, use_container_width=True, hide_index=True)

    # ==========================================================
    # DISPLAY
    # ==========================================================
    st.subheader("📈 Best Sellers")
    top_n = st.slider("Select Top Best Sellers", 10, 50, 20, step=10)

    bs_display = best_sellers.head(top_n).copy()
    for col in ["Qty_Sold", "Warehouse", "RAYON", "Cash"]:
        bs_display[col] = bs_display[col].astype(int).astype(str)

    st.dataframe(
        bs_display.style.apply(
            lambda x: ["background-color: #ffcccc" if x["🚨 Blocked Best Seller"] == "YES 🚨" else "" for _ in x],
            axis=1
        ),
        use_container_width=True,
        hide_index=True
    )

    st.subheader("🚨 Immediate Replenishment (Priority by Financial Risk)")
    merch_filter = st.multiselect(
        "Filter by Merch Group",
        options=sorted(blocked["Merch Group"].unique()),
        default=sorted(blocked["Merch Group"].unique())
    )

    blocked_filtered = blocked[blocked["Merch Group"].isin(merch_filter)]

    if blocked_filtered.empty:
        st.success("✅ No fully blocked items")
    else:
        st.dataframe(blocked_filtered, use_container_width=True, hide_index=True)

    st.subheader("📋 Merch Group Capacity & Feasibility")
    st.dataframe(
        merch_occ[
            ["Merch Group", "RAYON", "Warehouse", "Capacity",
             "Actual_Occupancy_%", "PCS_To_Push_Today",
             "Occupancy_After_Push_%", "Fragmented_PCS", "Fragmentation_%"]
        ],
        use_container_width=True,
        hide_index=True
    )

    # ==========================================================
    # EXPORT
    # ==========================================================
    st.download_button(
        "⬇️ Download Daily Store Action Plan",
        export_to_excel({
            "Best_Sellers": best_sellers,
            "Immediate_Replenishment": blocked,
            "Merch_Group_Action_Plan": merch_occ
        }),
        file_name="LCW_Store_Daily_Action_Plan.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ==============================================================
    # STORE LOGIN (STORE ONLY)
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

else:
    st.info("📥 Please upload Sales & Stock Excel files to start analysis.")

st.caption(f"📍 Store: {STORE_CODE}")
