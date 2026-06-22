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
        <p style='margin: 8px 0 0 0; font-size: 0.8rem; opacity: 0.9;'>Platform pusat data peninjauan kinerja penjualan aktual (Sell-In) & Target Kepatuhan MSA - Khusus Region 1.</p>
    </div>
    """, 
    unsafe_allow_html=True
)

# ─── INGESTION DATA VIA UTILS ────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_cached_data():
    return load_data_all(worksheet_name="sellinbysku_with_msa")

df_raw = get_cached_data()

if df_raw.empty:
    st.error("❌ Data dari database 'sellinbysku_with_msa' kosong atau gagal terhubung.")
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

region_col = find_column_safely(["INDO5_TEAM_SPV_REGION", "INDO5_TO", "REGION", "WILAYAH"], "REGION")
year_col = find_column_safely(["YEAR", "YEAR_NUM", "TAHUN", "year"], "YEAR")
month_col = find_column_safely(["MONTH", "MONTH_NUM", "BULAN", "month"], "MONTH")
sku_col = find_column_safely(["inova_id_sku_name", "SKU NAME", "sku_name", "PRODUCT SKU NAME"], "PRODUCT SKU NAME")
category_col = find_column_safely(["CATEGORY", "KATEGORI", "category", "PRODUCT CATEGORY"], "CATEGORY")
value_metric_col = find_column_safely(["SUM OF VALUE", "VALUE", "value", "ACTUAL VALUE", "sum_of_value"], "Sum of Value")
qty_metric_col = find_column_safely(["SUM OF QTY", "QTY", "qty", "ACTUAL QTY", "sum_of_qty"], "Sum of Qty")

cust_code_col = find_column_safely(["inova_id_cust_code", "INOVA CODE", "cust_code"], "inova_id_cust_code")
cust_name_col = find_column_safely(["inova_id_cust_name", "NAMA OUTLET", "cust_name", "OUTLET NAME"], "inova_id_cust_name")
dist_cust_col = find_column_safely(["dist_cust_id", "ID APL/PPG", "dist_id"], "dist_cust_id")
channel_l3_col = find_column_safely(["CHANNEL LEVEL 3", "channel_level_3", "CHANNEL_L3"], "CHANNEL LEVEL 3")
msa_listing_col = find_column_safely(["STATUS_LISTING_MSA", "STATUS_LISTING", "status_listing_msa"], "status_listing_msa")

# ─── CLEANING & TYPE CONVERSIONS ─────────────────────────────────────────────
df_proc[year_col] = pd.to_numeric(df_proc[year_col], errors='coerce').fillna(2026).astype(int)
df_proc[month_col] = pd.to_numeric(df_proc[month_col], errors='coerce').fillna(6).astype(int)
df_proc[value_metric_col] = pd.to_numeric(df_proc[value_metric_col], errors='coerce').fillna(0.0)
df_proc[qty_metric_col] = pd.to_numeric(df_proc[qty_metric_col], errors='coerce').fillna(0.0)
df_proc[msa_listing_col] = pd.to_numeric(df_proc[msa_listing_col], errors='coerce').fillna(0).astype(int)

# Filter Mutlak Awal Regional (Dikunci Sejak Awal)
df_proc = df_proc[df_proc[region_col].astype(str).str.upper().str.strip() == "REGION 1"]

# Handle string kosong / NaN
for col in [sku_col, cust_code_col, cust_name_col, dist_cust_col, channel_l3_col]:
    df_proc[col] = df_proc[col].fillna("UNASSIGNED").astype(str).str.strip()
df_proc[category_col] = df_proc[category_col].fillna("WOUND").astype(str).str.strip().str.upper()

# Penentu Dimensi Waktu Unik (YYYY_MM)
df_proc['PERIOD_KEY'] = df_proc[year_col].astype(str) + "_" + df_proc[month_col].astype(str).str.zfill(2)

# ─── MAIN FILTER PANEL ───────────────────────────────────────────────────────
st.subheader("⚙️ Panel Kontrol & Filter Analisis (Region 1)")

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

# ─── GENERATE LOOKBACK TIMELINE ──────────────────────────────────────────────
month_names_map = {
    1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"Mei", 6:"Jun",
    7:"Jul", 8:"Agu", 9:"Sep", 10:"Okt", 11:"Nov", 12:"Des"
}

target_periods = []
for i in [3, 2, 1, 0]:
    m = selected_month - i
    y = selected_year
    if m <= 0:
        m += 12 
        y -= 1
    target_periods.append((y, m))

(y_prev3, m_prev3), (y_prev2, m_prev2), (y_prev1, m_prev1), (y_current, m_current) = target_periods

col_name_prev3 = f"{month_names_map[m_prev3]} {y_prev3}"
col_name_prev2 = f"{month_names_map[m_prev2]} {y_prev2}"
col_name_prev1 = f"{month_names_map[m_prev1]} {y_prev1}"
col_name_current = f"{month_names_map[m_current]} {y_current}"
avg_col_name = f"AVG QTY 3M ({month_names_map[m_prev3]}-{month_names_map[m_prev1]})"

k_prev3 = f"{y_prev3}_{str(m_prev3).zfill(2)}"
k_prev2 = f"{y_prev2}_{str(m_prev2).zfill(2)}"
k_prev1 = f"{y_prev1}_{str(m_prev1).zfill(2)}"
k_current = f"{y_current}_{str(m_current).zfill(2)}"
target_keys = [k_prev3, k_prev2, k_prev1, k_current]

# ─── PROSES FILTERING DATA BERTAHAP ──────────────────────────────────────────
df_filtered = df_proc[df_proc['PERIOD_KEY'].isin(target_keys)].copy()

if selected_category != "All Categories":
    df_filtered = df_filtered[df_filtered[category_col] == selected_category]
if selected_cust_code != "All iNova Codes":
    df_filtered = df_filtered[df_filtered[cust_code_col] == selected_cust_code]
if selected_cust_name != "All Outlets":
    df_filtered = df_filtered[df_filtered[cust_name_col] == selected_cust_name]
if selected_dist_cust != "All ID APL/PPG":
    df_filtered = df_filtered[df_filtered[dist_cust_col] == selected_dist_cust]

# Ambil acuan data target MSA khusus bulan berjalan (Current Month)
df_targets = df_filtered[(df_filtered['PERIOD_KEY'] == k_current) & (df_filtered[msa_listing_col] == 1)]

# ─── RENDER TABEL UTAMA ──────────────────────────────────────────────────────
if not df_filtered.empty or not df_targets.empty:
    
    # KOREKSI UTAMA: Masukkan channel_l3_col ke index pivot agar agregasi data presisi sesuai database asli
    pivot_qty = df_filtered.pivot_table(
        index=[sku_col, category_col, channel_l3_col],
        columns='PERIOD_KEY',
        values=qty_metric_col,
        aggfunc='sum',
        fill_value=0.0
    ).reset_index()

    for k in target_keys:
        if k not in pivot_qty.columns:
            pivot_qty[k] = 0.0

    # Menghubungkan mapping Target MSA berdasarkan kombinasi unik SKU + Channel Level 3
    # Menggunakan fungsi .max() untuk mengabaikan angka 0 jika ditemukan angka 1 (Menang Centang)
    target_msa_map = df_filtered[df_filtered['PERIOD_KEY'] == k_current].groupby(
        [sku_col, channel_l3_col]
    )[msa_listing_col].max().to_dict()
    
    # Injeksi target SKU MSA yang belum memiliki transaksi penjualan aktual
    if not df_targets.empty:
        df_unique_targets = df_targets.drop_duplicates(subset=[sku_col, channel_l3_col])
        for _, t_row in df_unique_targets.iterrows():
            m_sku = t_row[sku_col]
            m_cat = t_row[category_col]
            m_chan = t_row[channel_l3_col]
            
            # Cek apakah kombinasi dimensi ini sudah ada di tabel pivot aktual
            exists = not pivot_qty[(pivot_qty[sku_col] == m_sku) & (pivot_qty[channel_l3_col] == m_chan)].empty
            if not exists:
                row_data = {sku_col: m_sku, category_col: m_cat, channel_l3_col: m_chan}
                for k in target_keys:
                    row_data[k] = 0.0
                pivot_qty = pd.concat([pivot_qty, pd.DataFrame([row_data])], ignore_index=True)

    # Menghitung Rata-rata 3 Bulan ke Belakang (Sebelum Current Month)
    pivot_qty[avg_col_name] = pivot_qty[[k_prev3, k_prev2, k_prev1]].mean(axis=1).apply(lambda x: math.ceil(x))

    # Re-ordering susunan kolom tabel utama beserta penambahan kolom Channel Level 3
    final_view_cols = [sku_col, category_col, channel_l3_col, avg_col_name, k_prev3, k_prev2, k_prev1, k_current]
    pivot_qty = pivot_qty.reindex(columns=final_view_cols, fill_value=0.0)
    
    # Kolom Validasi Target Kepatuhan MSA mengacu mutlak pada channel_level_3
    pivot_qty['TARGET MSA'] = pivot_qty.apply(
        lambda r: "✅" if target_msa_map.get((r[sku_col], r[channel_l3_col]), 0) == 1 else "❌", axis=1
    )

    # Kalkulasi Akurat Baris Total Summary Value (IDR) Berdasarkan Seluruh Data Terfilter
    val_m3 = df_filtered[df_filtered['PERIOD_KEY'] == k_prev3][value_metric_col].sum()
    val_m4 = df_filtered[df_filtered['PERIOD_KEY'] == k_prev2][value_metric_col].sum()
    val_m5 = df_filtered[df_filtered['PERIOD_KEY'] == k_prev1][value_metric_col].sum()
    val_m6 = df_filtered[df_filtered['PERIOD_KEY'] == k_current][value_metric_col].sum()
    avg_val_3m = math.ceil((val_m3 + val_m4 + val_m5) / 3)

    # Rename Kolom untuk representasi UI agar rapi
    pivot_qty.columns = [
        "PRODUCT SKU NAME", "CATEGORY", "CHANNEL LEVEL 3", avg_col_name, 
        col_name_prev3, col_name_prev2, col_name_prev1, col_name_current, 
        "TARGET MSA"
    ]

    pivot_qty = pivot_qty.sort_values(by=["TARGET MSA", col_name_current], ascending=[False, False])

    total_row_dict = {
        "PRODUCT SKU NAME": "TOTAL SUMMARY",
        "CATEGORY": "ALL VALUE (IDR)",
        "CHANNEL LEVEL 3": "",
        avg_col_name: avg_val_3m,
        col_name_prev3: val_m3,
        col_name_prev2: val_m4,
        col_name_prev1: val_m5,
        col_name_current: val_m6,
        "TARGET MSA": ""
    }
    
    df_pivot_final = pd.concat([pivot_qty, pd.DataFrame([total_row_dict])], ignore_index=True)

    # ─── LOGIKA FORMATTING KHUSUS TAMPILAN WEB (HTML) ────────────────────────
    def format_cells_with_rules(df):
        formatted_df = df.copy()
        last_row_idx = df.index[-1]
        loop_cols = [avg_col_name, col_name_prev3, col_name_prev2, col_name_prev1, col_name_current]
        
        for col in loop_cols:
            formatted_df[col] = formatted_df[col].astype(object)
        
        for idx, row in df.iterrows():
            if idx == last_row_idx:
                for col in loop_cols:
                    formatted_df.at[idx, col] = f"<b>Rp {row[col]:,.0f}</b>"
            else:
                v_avg = row[avg_col_name]
                v_m3 = row[col_name_prev3]
                v_m4 = row[col_name_prev2]
                v_m5 = row[col_name_prev1]
                v_m6 = row[col_name_current]
                
                formatted_df.at[idx, avg_col_name] = f"{v_avg:,.0f} PCS"
                
                if v_m3 == 0:
                    formatted_df.at[idx, col_name_prev3] = f"<span style='color: #DC2626; font-weight: 600;'>0 PCS</span>"
                else:
                    formatted_df.at[idx, col_name_prev3] = f"{v_m3:,.0f} PCS"

                if v_m4 == 0:
                    formatted_df.at[idx, col_name_prev2] = f"<span style='color: #DC2626; font-weight: 600;'>0 PCS</span>"
                elif v_m4 < v_m3:
                    formatted_df.at[idx, col_name_prev2] = f"<span style='color: #D97706;'>{v_m4:,.0f} PCS ↓</span>"
                else:
                    formatted_df.at[idx, col_name_prev2] = f"{v_m4:,.0f} PCS"
                
                if v_m5 == 0:
                    formatted_df.at[idx, col_name_prev1] = f"<span style='color: #DC2626; font-weight: 600;'>0 PCS</span>"
                elif v_m5 < v_m4:
                    formatted_df.at[idx, col_name_prev1] = f"<span style='color: #D97706;'>{v_m5:,.0f} PCS ↓</span>"
                else:
                    formatted_df.at[idx, col_name_prev1] = f"{v_m5:,.0f} PCS"
                    
                if v_m6 == 0:
                    formatted_df.at[idx, col_name_current] = f"<span style='color: #DC2626; font-weight: 600;'>0 PCS</span>"
                elif v_m6 < v_m5:
                    formatted_df.at[idx, col_name_current] = f"<span style='color: #D97706;'>{v_m6:,.0f} PCS ↓</span>"
                else:
                    formatted_df.at[idx, col_name_current] = f"{v_m6:,.0f} PCS"
                    
        return formatted_df

    df_display = format_cells_with_rules(df_pivot_final)

    st.markdown(
        f"""
        <style>
            div[data-testid=\"stDataFrame\"] table {{ background-color: #FFFFFF !important; color: #1E293B !important; }}
            div[data-testid=\"stDataFrame\"] th {{ background-color: {SECONDARY} !important; color: #FFFFFF !important; font-weight: 700 !important; }}
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
            file_name=f"Region1_Performance_Month_{selected_month}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.warning("⚠️ Tidak ada data transaksi aktual pada kombinasi filter yang Anda pilih.")

render_footer()