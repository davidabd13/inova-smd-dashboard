import streamlit as st
import pandas as pd
import io
import math
from utils import load_data_all, inject_css, render_footer, SECONDARY

# ─── CONFIG & STYLING ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Betadine Sales Dashboard - Audit Mode",
    layout="wide",
    initial_sidebar_state="collapsed"
)
inject_css()

st.title("🧪 Mode Audit & Validasi Data")
st.caption("Halaman ini digunakan untuk mencocokkan angka dashboard dengan database asli Supabase.")

# ─── INGESTION DATA ──────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_cached_data():
    return load_data_all(worksheet_name="sellinbysku_with_msa")

df_raw = get_cached_data()

if df_raw.empty:
    st.error("❌ Data dari database kosong.")
    st.stop()

# ─── RESOLVE KOLOM ──────────────────────────────────────────────────────────
raw_cols = list(df_raw.columns)
raw_cols_upper = [str(c).strip().upper() for c in raw_cols]

def find_column_safely(possible_names, default_name):
    for name in possible_names:
        if name.upper() in raw_cols_upper:
            return raw_cols[raw_cols_upper.index(name.upper())]
    return default_name

region_col = find_column_safely(["INDO5_TEAM_SPV_REGION", "INDO5_TO", "REGION", "WILAYAH"], "REGION")
year_col = find_column_safely(["YEAR", "YEAR_NUM", "TAHUN", "year"], "YEAR")
month_col = find_column_safely(["MONTH", "MONTH_NUM", "BULAN", "month"], "MONTH")
value_metric_col = find_column_safely(["SUM OF VALUE", "VALUE", "value", "ACTUAL VALUE", "sum_of_value"], "Sum of Value")
qty_metric_col = find_column_safely(["SUM OF QTY", "QTY", "qty", "ACTUAL QTY", "sum_of_qty"], "Sum of Qty")

# Standardisasi Tipe Data asli
df_raw[year_col] = pd.to_numeric(df_raw[year_col], errors='coerce').fillna(2026).astype(int)
df_raw[month_col] = pd.to_numeric(df_raw[month_col], errors='coerce').fillna(6).astype(int)
df_raw[value_metric_col] = pd.to_numeric(df_raw[value_metric_col], errors='coerce').fillna(0.0)
df_raw[qty_metric_col] = pd.to_numeric(df_raw[qty_metric_col], errors='coerce').fillna(0.0)

# ─── PANEL AUDIT 1: CEK TOTAL DATABASE ASLI (TANPA FILTER) ─────────────────────
st.markdown("### 📊 1. Total Nilai di Database Asli Supabase (Tanpa Filter Apapun)")
total_value_supabase = df_raw[value_metric_col].sum()
total_qty_supabase = df_raw[qty_metric_col].sum()

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Total Baris di DB", f"{len(df_raw):,}")
with c2:
    st.metric("Total Value (IDR) di DB", f"Rp {total_value_supabase:,.0f}")
with c3:
    st.metric("Total Qty (PCS) di DB", f"{total_qty_supabase:,.0f} PCS")

# ─── PANEL AUDIT 2: BREAKDOWN PER REGION ──────────────────────────────────────
st.markdown("### 🗺️ 2. Breakdown Nilai Berdasarkan Isi Kolom Region")
st.write("Silakan cocokkan nama region di bawah ini dengan angka yang Anda pegang di excel manual:")

df_region_breakdown = df_raw.groupby(region_col).agg(
    Total_Baris=(region_col, 'count'),
    Total_Value=(value_metric_col, 'sum'),
    Total_Qty=(qty_metric_col, 'sum')
).reset_index()

st.dataframe(df_region_breakdown, use_container_width=True)

# ─── PANEL AUDIT 3: BREAKDOWN PER BULAN & TAHUN (KHUSUS REGION 1) ─────────────
st.markdown("### 📅 3. Breakdown Tren Per Bulan & Tahun (Khusus REGION 1)")
st.write("Jika Anda menerapkan filter `REGION 1`, berikut adalah total nilai asli per bulan dari database:")

# Terapkan filter Region 1 secara aman
df_r1_only = df_raw[df_raw[region_col].astype(str).str.upper().str.strip() == "REGION 1"]

if not df_r1_only.empty:
    df_monthly_breakdown = df_r1_only.groupby([year_col, month_col]).agg(
        Total_Baris=(value_metric_col, 'count'),
        Total_Value_IDR=(value_metric_col, 'sum'),
        Total_Qty_PCS=(qty_metric_col, 'sum')
    ).reset_index().sort_values(by=[year_col, month_col], ascending=False)
    
    st.dataframe(df_monthly_breakdown, use_container_width=True)
else:
    st.warning("⚠️ Tidak ada data sama sekali yang lolos teks 'REGION 1'. Periksa tabel nomor 2 di atas untuk melihat penulisan yang benar.")

render_footer()