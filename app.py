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
        <p style='margin: 8px 0 0 0; font-size: 1rem; opacity: 0.9;'>Platform pusat data peninjauan kinerja penjualan aktual (Sell-In) Betadine secara langsung berdasar data Supabase.</p>
    </div>
    """, 
    unsafe_allow_html=True
)

# ─── INGESTION DATA (>100K ROWS SUPPORT) ─────────────────────────────────────
df_raw = load_data_all(worksheet_name="sellinbysku")

if df_raw.empty:
    st.error("❌ Data dari database 'sellinbysku' kosong atau gagal terhubung. Periksa pengaturan jaringan atau kredensial Supabase Anda.")
    st.stop()

df_proc = df_raw.copy()

# ─── BULLETPROOF COLUMN RESOLVER (SINKRONISASI UTILS & ANTI-KEYERROR) ────────
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

# Mengunci koordinat kolom waktu & dimensi bisnis utama (Menghubungkan kecocokan dengan utils.py)
year_col = find_column_safely(["YEAR", "YEAR_NUM", "TAHUN", "year"], "YEAR")
month_col = find_column_safely(["MONTH", "MONTH_NUM", "BULAN", "month"], "MONTH")
sku_col = find_column_safely(["PRODUCT SKU NAME", "INOVA ID SKU NAME", "INOVA_ID_SKU_NAME", "SKU NAME", "SKU_NAME", "sku_name"], "PRODUCT SKU NAME")
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

df_proc[category_col] = df_proc[category_col].fillna("WOUND").astype(str).str.strip().str.upper()
df_proc[sku_col] = df_proc[sku_col].fillna("UNASSIGNED").astype(str).str.strip()

# ─── SIDEBAR FILTERS ─────────────────────────────────────────────────────────
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
df_trend_base = df_proc[df_proc['Period_Str'].isin(list_periods_3m_keys)].copy()

# Filter Tambahan Operasional
st.sidebar.header("⚙️ Filter Operasional")
def apply_sidebar_filter(df, column_name, label, all_label):
    df[column_name] = df[column_name].fillna("UNASSIGNED").astype(str).str.strip()
    options = [all_label] + sorted([x for x in df[column_name].unique() if x != "UNASSIGNED"])
    selected = st.sidebar.selectbox(label, options, index=0)
    return df if selected == all_label else df[df[column_name] == selected]

df_trend_base = apply_sidebar_filter(df_trend_base, abm_field, "ABM / KAM Representative", "All ABM/KAM")
df_trend_base = apply_sidebar_filter(df_trend_base, spv_col, "SPV Region", "All SPV Regions")
df_trend_base = apply_sidebar_filter(df_trend_base, region_field, "Region / Branch", "All Regions")
df_trend_base = apply_sidebar_filter(df_trend_base, channel_field, "Channel Level 1", "All Channels")
df_trend_base = apply_sidebar_filter(df_trend_base, sku_col, "Product SKU Filter", "All SKUs")
df_trend_base = apply_sidebar_filter(df_trend_base, outlet_col, "Outlet Name", "All Outlets")
df_trend_base = apply_sidebar_filter(df_trend_base, smd_col, "Kode SMD", "All SMD Codes")

df_filtered_trend = df_trend_base.copy()

# ─── MAIN DISPLAY MATRIX AREA ────────────────────────────────────────────────
st.subheader("📋 Matriks Pivot Performa Produk (3 Bulan Rolling)")
st.caption(f"Rentang waktu aktif analisis saat ini: **{list_periods_3m_names[0]}** s/d **{list_periods_3m_names[-1]}**")

# Kontrol Perspektif Perhitungan & Kategori
col_ctrl1, col_ctrl2 = st.columns(2)
with col_ctrl1:
    chosen_metric_label = st.radio("Perspektif Penghitungan:", ["SUM OF VALUE", "SUM OF QTY"], index=0, horizontal=True)
    active_ims_col = value_metric_col if chosen_metric_label == "SUM OF VALUE" else qty_metric_col
    prefix_unit = "Rp " if chosen_metric_label == "SUM OF VALUE" else ""

with col_ctrl2:
    available_categories = ["All Categories"] + sorted(list(df_filtered_trend[category_col].unique()))
    selected_category = st.selectbox("Filter Kategori Produk", available_categories, index=0)
    if selected_category != "All Categories":
        df_filtered_trend = df_filtered_trend[df_filtered_trend[category_col] == selected_category]

df_filtered_trend['Period_Formatted'] = df_filtered_trend['Period_Str'].map(period_key_to_name_dict)

if not df_filtered_trend.empty:
    # Pembentukan Pivot Table Amandemen
    df_pivot = df_filtered_trend.pivot_table(
        index=[sku_col, category_col],
        columns='Period_Formatted',
        values=active_ims_col,
        aggfunc='sum',
        fill_value=0.0
    ).reset_index()
    
    # Deteksi dan pel pelindung jika ada bulan yang kosong transaksi agar tidak memicu pergeseran kolom
    for p_name in list_periods_3m_names:
        if p_name not in df_pivot.columns:
            df_pivot[p_name] = 0.0
            
    # PERBAIKAN AKURASI: Susun ulang kolom berdasarkan pemetaan eksplisit Pandas (Mencegah pergeseran data bulan)
    ordered_columns = [sku_col, category_col] + list_periods_3m_names
    df_pivot = df_pivot.reindex(columns=ordered_columns, fill_value=0.0)
    df_pivot.columns = ["PRODUCT SKU NAME", "CATEGORY"] + list_periods_3m_names
    
    label_total_header = f"TOTAL AMOUNT ({chosen_metric_label})"
    df_pivot[label_total_header] = df_pivot[list_periods_3m_names].sum(axis=1)
    df_pivot = df_pivot.sort_values(by=label_total_header, ascending=False)
    
    # Baris Total Summary Paling Bawah
    total_row_dict = {"PRODUCT SKU NAME": "TOTAL SUMMARY", "CATEGORY": "ALL CATEGORIES"}
    for p_name in list_periods_3m_names:
        total_row_dict[p_name] = df_pivot[p_name].sum()
    total_row_dict[label_total_header] = df_pivot[label_total_header].sum()
    
    df_pivot_final = pd.concat([df_pivot, pd.DataFrame([total_row_dict])], ignore_index=True)
    format_rules = {col: f"{prefix_unit}{{:,.0f}}" for col in list_periods_3m_names + [label_total_header]}
    
    # Custom CSS khusus untuk rendering dataframe agar rapi dan kontras tinggi
    st.markdown(
        f"""
        <style>
            div[data-testid="stDataFrame"] table {{ background-color: #FFFFFF !important; color: #1E293B !important; }}
            div[data-testid="stDataFrame"] th {{ background-color: {SECONDARY} !important; color: #FFFFFF !important; font-weight: 700 !important; }}
        </style>
        """, 
        unsafe_allow_html=True
    )
    
    st.dataframe(df_pivot_final.style.format(format_rules), use_container_width=True, hide_index=True)
    
    # Fitur Download Laporan Excel Ekspor
    col_space, col_btn = st.columns([8, 2])
    with col_btn:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_pivot_final.to_excel(writer, index=False, sheet_name='3M_Sales_Matrix')
        st.download_button(
            label="📥 Download Pivot Report (Excel)",
            data=output.getvalue(),
            file_name=f"Actual_Performance_3M_{chosen_metric_label.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.warning("⚠️ Tidak ada riwayat transaksi yang cocok dengan kombinasi filter saat ini.")

render_footer()