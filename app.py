import streamlit as st
import pandas as pd
import io
import math
from utils import load_data_all, inject_css, render_footer, SECONDARY

# ─── CONFIG & STYLING ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Betadine Sales Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)
inject_css()

# ─── HERO BANNER RINGKAS ─────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style='background: linear-gradient(135deg, {SECONDARY} 0%, #1E40AF 100%); padding: 30px; border-radius: 16px; color: white; margin-bottom: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);'>
        <h1 style='margin: 0; font-size: 2rem; font-weight: 800; letter-spacing: -0.02em;'>Betadine Sales Dashboard</h1>
        <p style='margin: 8px 0 0 0; font-size: 0.8rem; opacity: 0.9;'>Platform pusat data peninjauan kinerja penjualan aktual (Sell-In).</p>
    </div>
    """, 
    unsafe_allow_html=True
)

# ─── INGESTION DATA ──────────────────────────────────────────────────────────
df_raw = load_data_all(worksheet_name="sellinbysku")

if df_raw.empty:
    st.error("❌ Data dari database 'sellinbysku' kosong atau gagal terhubung.")
    st.stop()

df_proc = df_raw.copy()

# ─── BULLETPROOF COLUMN RESOLVER ─────────────────────────────────────────────
raw_cols = list(df_proc.columns)
raw_cols_upper = [str(c).strip().upper() for c in raw_cols]

def find_column_safely(possible_names, default_name):
    for name in possible_names:
        if name.upper() in raw_cols_upper:
            return raw_cols[raw_cols_upper.index(name.upper())]
    df_proc[default_name] = 0.0
    return default_name

# 🚀 Membaca kolom wilayah secara akurat menggunakan nama kolom riil Anda
region_col = find_column_safely(["INDO5_TEAM_SPV_REGION", "indo5_team_spv_region", "REGION", "WILAYAH"], "REGION")

year_col = find_column_safely(["YEAR", "YEAR_NUM", "TAHUN", "year"], "YEAR")
month_col = find_column_safely(["MONTH", "MONTH_NUM", "BULAN", "month"], "MONTH")
sku_col = find_column_safely(["inova_id_sku_name", "SKU NAME", "sku_name", "PRODUCT SKU NAME"], "PRODUCT SKU NAME")
category_col = find_column_safely(["CATEGORY", "KATEGORI", "category", "PRODUCT CATEGORY"], "CATEGORY")
value_metric_col = find_column_safely(["SUM OF VALUE", "VALUE", "value", "ACTUAL VALUE", "sum_of_value"], "Sum of Value")
qty_metric_col = find_column_safely(["SUM OF QTY", "QTY", "qty", "ACTUAL QTY", "sum_of_qty"], "Sum of Qty")

# Kolom filter tambahan baru
cust_code_col = find_column_safely(["inova_id_cust_code", "INOVA CODE", "cust_code"], "inova_id_cust_code")
cust_name_col = find_column_safely(["inova_id_cust_name", "NAMA OUTLET", "cust_name", "OUTLET NAME"], "inova_id_cust_name")
dist_cust_col = find_column_safely(["dist_cust_id", "ID APL/PPG", "dist_id"], "dist_cust_id")

# ─── CLEANING & TYPE CONVERSIONS ─────────────────────────────────────────────
df_proc[year_col] = pd.to_numeric(df_proc[year_col], errors='coerce').fillna(2026).astype(int)
df_proc[month_col] = pd.to_numeric(df_proc[month_col], errors='coerce').fillna(6).astype(int)
df_proc[value_metric_col] = pd.to_numeric(df_proc[value_metric_col], errors='coerce').fillna(0.0)
df_proc[qty_metric_col] = pd.to_numeric(df_proc[qty_metric_col], errors='coerce').fillna(0.0)

df_proc[category_col] = df_proc[category_col].fillna("WOUND").astype(str).str.strip().str.upper()
df_proc[sku_col] = df_proc[sku_col].fillna("UNASSIGNED").astype(str).str.strip()
df_proc[cust_code_col] = df_proc[cust_code_col].fillna("UNASSIGNED").astype(str).str.strip()
df_proc[cust_name_col] = df_proc[cust_name_col].fillna("UNASSIGNED").astype(str).str.strip()
df_proc[dist_cust_col] = df_proc[dist_cust_col].fillna("UNASSIGNED").astype(str).str.strip()

# 🔒 [HARDCODED ROW-LEVEL SECURITY UNTUK TESTING]
# Silakan ganti "REGION 1" di bawah ini dengan nama wilayah riil yang tertulis di dalam kolom indo5_team_spv_region Anda
TARGET_REGION_TEST = "REGION 1" 
df_proc = df_proc[df_proc[region_col].astype(str).str.upper().str.strip() == TARGET_REGION_TEST.upper()]

# ─── MAIN FILTER PANEL (DI ATAS PIVOT TABLE) ─────────────────────────────────
st.subheader("⚙️ Panel Kontrol & Filter Analisis")

# Baris Filter Utama 1: Waktu & Kategori
col1, col2, col3 = st.columns(3)
with col1:
    available_years = sorted(list(df_proc[year_col].unique()), reverse=True)
    selected_year = st.selectbox("📅 Tahun Target", available_years if available_years else [2026], index=0)

with col2:
    available_months = sorted(list(df_proc[df_proc[year_col] == selected_year][month_col].unique()), reverse=True)
    selected_month = st.selectbox("📆 Bulan Target Basis", available_months if available_months else [6], index=0)

with col3:
    available_categories = ["All Categories"] + sorted(list(df_proc[category_col].unique()))
    selected_category = st.selectbox("📂 Filter Kategori Produk", available_categories, index=0)

# Baris Filter Utama 2: Dimensi Toko & Distributor
col4, col5, col6 = st.columns(3)
with col4:
    unique_codes = ["All iNova Codes"] + sorted(list(df_proc[cust_code_col].unique()))
    selected_cust_code = st.selectbox("🔑 iNova Code", unique_codes, index=0)

with col5:
    unique_names = ["All Outlets"] + sorted(list(df_proc[cust_name_col].unique()))
    selected_cust_name = st.selectbox("🏪 Nama Outlet", unique_names, index=0)

with col6:
    unique_dist = ["All ID APL/PPG"] + sorted(list(df_proc[dist_cust_col].unique()))
    selected_dist_cust = st.selectbox("🆔 ID APL/PPG", unique_dist, index=0)

# ─── PROSES FILTERING DATA BERTAHAP ──────────────────────────────────────────
df_matrix = df_proc[df_proc[year_col] == selected_year].copy()

if selected_category != "All Categories":
    df_matrix = df_matrix[df_matrix[category_col] == selected_category]
if selected_cust_code != "All iNova Codes":
    df_matrix = df_matrix[df_matrix[cust_code_col] == selected_cust_code]
if selected_cust_name != "All Outlets":
    df_matrix = df_matrix[df_matrix[cust_name_col] == selected_cust_name]
if selected_dist_cust != "All ID APL/PPG":
    df_matrix = df_matrix[df_matrix[dist_cust_col] == selected_dist_cust]

# ─── LOGIKA PENENTUAN 4 BULAN BERJALAN SECARA DINAMIS ────────────────────────
month_names_map = {
    1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"Mei", 6:"Jun",
    7:"Jul", 8:"Agu", 9:"Sep", 10:"Okt", 11:"Nov", 12:"Des"
}

target_months_indices = []
for i in range(3, -1, -1):
    m = selected_month - i
    if m <= 0:
        m += 12 
    target_months_indices.append(m)

m_prev3, m_prev2, m_prev1, m_current = target_months_indices

col_name_prev2 = f"{month_names_map[m_prev2]} {selected_year}"
col_name_prev1 = f"{month_names_map[m_prev1]} {selected_year}"
col_name_current = f"{month_names_map[m_current]} {selected_year}"
avg_col_name = f"AVG QTY 3M ({month_names_map[m_prev3]}-{month_names_map[m_prev1]})"

# Bangun pemetaan dinamis untuk kolom pivot
dynamic_month_map = {
    m_prev3: f"{month_names_map[m_prev3]} {selected_year}",
    m_prev2: col_name_prev2,
    m_prev1: col_name_prev1,
    m_current: col_name_current
}
df_matrix['Period_Name'] = df_matrix[month_col].map(dynamic_month_map)
df_matrix = df_matrix[df_matrix[month_col].isin(target_months_indices)]

# ─── RENDER TABEL UTAMA ──────────────────────────────────────────────────────

if not df_matrix.empty:
    pivot_qty = df_matrix.pivot_table(
        index=[sku_col, category_col],
        columns='Period_Name',
        values=qty_metric_col,
        aggfunc='sum',
        fill_value=0.0
    ).reset_index()

    for m_label in dynamic_month_map.values():
        if m_label not in pivot_qty.columns:
            pivot_qty[m_label] = 0.0

    str_prev3 = dynamic_month_map[m_prev3]
    str_prev2 = dynamic_month_map[m_prev2]
    str_prev1 = dynamic_month_map[m_prev1]
    
    pivot_qty[avg_col_name] = pivot_qty[[str_prev3, str_prev2, str_prev1]].mean(axis=1).apply(lambda x: math.ceil(x))

    final_view_cols = [sku_col, category_col, avg_col_name, col_name_prev2, col_name_prev1, col_name_current]
    pivot_qty = pivot_qty.reindex(columns=final_view_cols, fill_value=0.0)
    pivot_qty.columns = ["PRODUCT SKU NAME", "CATEGORY", avg_col_name, col_name_prev2, col_name_prev1, col_name_current]

    pivot_qty = pivot_qty.sort_values(by=col_name_current, ascending=False)

    val_m3 = df_matrix[df_matrix[month_col] == m_prev3][value_metric_col].sum()
    val_m4 = df_matrix[df_matrix[month_col] == m_prev2][value_metric_col].sum()
    val_m5 = df_matrix[df_matrix[month_col] == m_prev1][value_metric_col].sum()
    val_m6 = df_matrix[df_matrix[month_col] == m_current][value_metric_col].sum()
    avg_val_3m = math.ceil((val_m3 + val_m4 + val_m5) / 3)

    total_row_dict = {
        "PRODUCT SKU NAME": "TOTAL SUMMARY",
        "CATEGORY": "ALL VALUE (IDR)",
        avg_col_name: avg_val_3m,
        col_name_prev2: val_m4,
        col_name_prev1: val_m5,
        col_name_current: val_m6
    }
    
    df_pivot_final = pd.concat([pivot_qty, pd.DataFrame([total_row_dict])], ignore_index=True)

    # ─── LOGIKA FORMATTING CELL & KONDISI WARNA TREN DATA ────────────────────
    def format_cells_with_rules(df):
        formatted_df = df.copy()
        last_row_idx = df.index[-1]
        loop_cols = [avg_col_name, col_name_prev2, col_name_prev1, col_name_current]
        
        for col in loop_cols:
            formatted_df[col] = formatted_df[col].astype(object)
        
        for idx, row in df.iterrows():
            if idx == last_row_idx:
                for col in loop_cols:
                    formatted_df.at[idx, col] = f"Rp {row[col]:,.0f}"
            else:
                v_avg = row[avg_col_name]
                v_prev2 = row[col_name_prev2]
                v_prev1 = row[col_name_prev1]
                v_current = row[col_name_current]
                
                formatted_df.at[idx, avg_col_name] = f"{v_avg:,.0f} PCS"
                
                if v_prev2 == 0:
                    formatted_df.at[idx, col_name_prev2] = f"<span style='color: #DC2626; font-weight: 600;'>0 PCS</span>"
                elif v_avg > v_prev2:
                    formatted_df.at[idx, col_name_prev2] = f"<span style='color: #D97706;'>{v_prev2:,.0f} PCS</span>"
                else:
                    formatted_df.at[idx, col_name_prev2] = f"{v_prev2:,.0f} PCS"
                
                if v_prev1 == 0:
                    formatted_df.at[idx, col_name_prev1] = f"<span style='color: #DC2626; font-weight: 600;'>0 PCS</span>"
                elif v_prev2 > v_prev1:
                    formatted_df.at[idx, col_name_prev1] = f"<span style='color: #D97706;'>{v_prev1:,.0f} PCS</span>"
                else:
                    formatted_df.at[idx, col_name_prev1] = f"{v_prev1:,.0f} PCS"
                    
                if v_current == 0:
                    formatted_df.at[idx, col_name_current] = f"<span style='color: #DC2626; font-weight: 600;'>0 PCS</span>"
                elif v_prev1 > v_current:
                    formatted_df.at[idx, col_name_current] = f"<span style='color: #D97706;'>{v_current:,.0f} PCS</span>"
                else:
                    formatted_df.at[idx, col_name_current] = f"{v_current:,.0f} PCS"
                    
        return formatted_df

    df_display = format_cells_with_rules(df_pivot_final)

    st.markdown(
        f"""
        <style>
            div[data-testid="stDataFrame"] table {{ background-color: #FFFFFF !important; color: #1E293B !important; }}
            div[data-testid="stDataFrame"] th {{ background-color: {SECONDARY} !important; color: #FFFFFF !important; font-weight: 700 !important; }}
        </style>
        """, 
        unsafe_allow_html=True
    )
    
    st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)
    st.write("<br>", unsafe_allow_html=True)
    
    col_space, col_btn = st.columns([8, 2])
    with col_btn:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_pivot_final.to_excel(writer, index=False, sheet_name='3M_Sales_Matrix')
        st.download_button(
            label="📥 Download Pivot Report (Excel)",
            data=output.getvalue(),
            file_name=f"Actual_Performance_Filtered_Month_{selected_month}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.warning("⚠️ Tidak ada data transaksi aktual pada kombinasi filter yang Anda pilih.")

render_footer()