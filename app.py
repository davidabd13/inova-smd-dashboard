"""
app.py — Betadine Sales Tracker Single-Page Portal
Menggabungkan Beranda & Analisis Performa Aktual (3 Bulan) menjadi satu kesatuan berkecepatan tinggi.
"""

import streamlit as st
import pandas as pd
import io
from utils import load_data_all, inject_css, render_footer, PRIMARY, SECONDARY, LIGHT_GRAY

# ─── CONFIG & STYLING ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Betadine Sales Tracker Portal",
    layout="wide",
    initial_sidebar_state="expanded"
)
inject_css()

# ─── HERO BANNER RINGKAS ─────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style='background: linear-gradient(135deg, {SECONDARY} 0%, #1E40AF 100%); padding: 30px; border-radius: 16px; color: white; margin-bottom: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);'>
        <h1 style='margin: 0; font-size: 2.2rem; font-weight: 800; letter-spacing: -0.02em;'>Betadine Sales Analytics Portal</h1>
        <p style='margin: 8px 0 0 0; font-size: 1rem; opacity: 0.9;'>Platform pusat data peninjauan kinerja penjualan aktual (Sell-In).</p>
    </div>
    """, 
    unsafe_allow_html=True
)

# ─── INGESTION DATA (>100K ROWS SUPPORT) ─────────────────────────────────────
df_raw = load_data_all(worksheet_name="sellinbysku")

if df_raw.empty:
    st.error("❌ Data dari database 'sellinbysku' kosong atau gagal terhubung. Periksa pengaturan jaringan atau kredensial Supabase Anda.")
    st.stop()

# Gunakan salinan independen total untuk menghindari pencemaran memori antar-run Streamlit
df_proc = df_raw.copy()

# ─── BULLETPROOF COLUMN RESOLVER (ANTI-KEYERROR LOGIKA BISNIS) ───────────────
raw_cols = list(df_proc.columns)
raw_cols_upper = [str(c).strip().upper() for c in raw_cols]

def find_column_safely(possible_names, default_name, fallback_fill_value=None):
    for name in possible_names:
        if name.upper() in raw_cols_upper:
            return raw_cols[raw_cols_upper.index(name.upper())]
    if fallback_fill_value is not None:
        df_proc[default_name] = fallback_fill_value
    else:
        df_proc[default_name] = 0.0
    return default_name

# Resolving Kolom Waktu & Dimensi Bisnis Utama
year_col = find_column_safely(["YEAR", "YEAR_NUM", "TAHUN", "year"], "YEAR")
month_col = find_column_safely(["MONTH", "MONTH_NUM", "BULAN", "month"], "MONTH")
sku_col = find_column_safely(["INOVA ID SKU NAME", "INOVA_ID_SKU_NAME", "SKU NAME", "SKU_NAME", "PRODUCT SKU NAME", "sku_name"], "iNova ID SKU Name")
category_col = find_column_safely(["CATEGORY", "KATEGORI", "PRODUCT CATEGORY", "category"], "CATEGORY")

# Resolving Kolom Operasional Filter
outlet_col = find_column_safely(["INOVA_ID_CUST_NAME", "OUTLET NAME", "NAMA OUTLET", "outlet_name"], "Outlet Name")
smd_col = find_column_safely(["INOVA_SMD_CODE", "KODE SMD", "SMD CODE", "smd_code"], "Kode SMD")
spv_col = find_column_safely(["INDO5 TEAM - SPV REGION", "SPV REGION", "REGION", "spv_region"], "SPV Region")
abm_field = find_column_safely(["ABM / KAM", "ABM", "KAM", "abm", "kam"], "ABM / KAM")
region_field = find_column_safely(["DISTRIBUTOR BRANCH", "BRANCH", "WILAYAH", "branch", "region"], "Distributor Branch")
channel_field = find_column_safely(["CHANNEL LEVEL 1", "CHANNEL", "channel"], "CHANNEL LEVEL 1")

# Resolving Kolom Metrik Angka
value_metric_col = find_column_safely(["SUM OF VALUE", "sum_of_value", "ACTUAL VALUE", "TOTAL_SALES", "VALUE", "value"], "Sum of Value")
qty_metric_col = find_column_safely(["SUM OF QTY", "sum_of_qty", "ACTUAL QTY", "TOTAL_QTY", "QTY", "qty"], "Sum of Qty")

# ─── CLEANING & TYPE CONVERSIONS ─────────────────────────────────────────────
if df_proc[value_metric_col].dtype == object:
    df_proc[value_metric_col] = df_proc[value_metric_col].astype(str).str.replace(',', '').str.replace('.00', '', regex=False)
if df_proc[qty_metric_col].dtype == object:
    df_proc[qty_metric_col] = df_proc[qty_metric_col].astype(str).str.replace(',', '').str.replace('.00', '', regex=False)

df_proc[year_col] = pd.to_numeric(df_proc[year_col], errors='coerce').fillna(2026).astype(int)
df_proc[month_col] = pd.to_numeric(df_proc[month_col], errors='coerce').fillna(1).astype(int)
df_proc[value_metric_col] = pd.to_numeric(df_proc[value_metric_col], errors='coerce').fillna(0.0)
df_proc[qty_metric_col] = pd.to_numeric(df_proc[qty_metric_col], errors='coerce').fillna(0.0)

# Pastikan pembersihan teks dilakukan menyeluruh untuk menghindari duplikasi grup item akibat leading/trailing space
df_proc[category_col] = df_proc[category_col].fillna("WOUND").astype(str).str.strip().str.upper()
df_proc[sku_col] = df_proc[sku_col].fillna("UNASSIGNED").astype(str).str.strip()

# ─── SIDEBAR FILTERS (DIFOKUSKAN PADA PARAMETER ANALISIS) ───────────────────
st.sidebar.header("🔍 Filter Waktu Analisis")
available_years = sorted(list(df_proc[year_col].unique()), reverse=True)
selected_year = st.sidebar.selectbox("Tahun Target", available_years if available_years else [2026], index=0)

df_year_filtered = df_proc[df_proc[year_col] == selected_year]
available_months = sorted(list(df_year_filtered[month_col].unique()), reverse=True)
selected_month = st.sidebar.selectbox("Bulan Target Basis", available_months if available_months else [6], index=0)

# Pembuatan Rentang Waktu 3 Bulan Mundur Secara Otomatis
month_names_map = {
    1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"Mei", 6:"Jun",
    7:"Jul", 8:"Agu", 9:"Sep", 10:"Okt", 11:"Nov", 12:"Des"
}

rolling_periods = []
for i in range(2, -1, -1):
    m = selected_month - i
    y = selected_year
    while m <= 0:
        m += 12
        y -= 1
    rolling_periods.append((y, m))

df_periods = pd.DataFrame(rolling_periods, columns=['Tahun_Trend', 'Bulan_Trend'])
df_periods['Period_Str'] = df_periods.apply(lambda r: f"{int(r['Tahun_Trend'])}-{str(int(r['Bulan_Trend'])).zfill(2)}", axis=1)
df_periods['Period_Name'] = df_periods.apply(lambda r: f"{month_names_map.get(int(r['Bulan_Trend']), 'M')} {int(r['Tahun_Trend'])}", axis=1)

list_periods_3m_keys = df_periods['Period_Str'].tolist()
list_periods_3m_names = df_periods['Period_Name'].tolist()
period_key_to_name_dict = dict(zip(list_periods_3m_keys, list_periods_3m_names))

df_proc['Period_Str'] = df_proc.apply(lambda r: f"{int(r[year_col])}-{str(int(r[month_col])).zfill(2)}", axis=1)

# Mengambil slice murni berdasarkan target 3 bulan terpilih
df_trend_base = df_proc[df_proc['Period_Str'].isin(list_periods_3m_keys)].copy()

# Filter Tambahan Operasional (Logika Diperbaiki: Menggunakan Kloning Lokal Murni Tanpa Mutasi Induk)
st.sidebar.header("⚙️ Filter Operasional")
def apply_sidebar_filter(df, column_name, label, all_label):
    temp_df = df.copy()
    temp_df[column_name] = temp_df[column_name].fillna("UNASSIGNED").astype(str).str.strip()
    options = [all_label] + sorted([x for x in temp_df[column_name].unique() if x != "UNASSIGNED"])
    selected = st.sidebar.selectbox(label, options, index=0)
    if selected == all_label:
        return df
    else:
        return df[df[column_name].fillna("UNASSIGNED").astype(str).str.strip() == selected].copy()

df_filtered_trend = df_trend_base.copy()
df_filtered_trend = apply_sidebar_filter(df_filtered_trend, abm_field, "ABM / KAM Representative", "All ABM/KAM")
df_filtered_trend = apply_sidebar_filter(df_filtered_trend, spv_col, "SPV Region", "All SPV Regions")
df_filtered_trend = apply_sidebar_filter(df_filtered_trend, region_field, "Region / Branch", "All Regions")
df_filtered_trend = apply_sidebar_filter(df_filtered_trend, channel_field, "Channel Level 1", "All Channels")
df_filtered_trend = apply_sidebar_filter(df_filtered_trend, sku_col, "Product SKU Filter", "All SKUs")
df_filtered_trend = apply_sidebar_filter(df_filtered_trend, outlet_col, "Outlet Name", "All Outlets")
df_filtered_trend = apply_sidebar_filter(df_filtered_trend, smd_col, "Kode SMD", "All SMD Codes")

# ─── MAIN DISPLAY MATRIX AREA ────────────────────────────────────────────────
st.subheader("📋 Matriks Pivot Performa Produk (3 Bulan Rolling)")
st.caption(f"Rentang waktu aktif analisis saat ini: **{list_periods_3m_names[0]}** s/d **{list_periods_3m_names[-1]}**")

#