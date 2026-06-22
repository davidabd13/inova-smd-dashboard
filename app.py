import streamlit as st
import pandas as pd
import io
import math
from utils import load_data_all, inject_css, render_footer, SECONDARY

# ─── CONFIG & STYLING ────────────────────────────────────────────────────────
st.set_config(
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

# ─── INGESTION DATA VIA UTILS ────────────────────────────────────────────────
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

# Kunci kolom region komprehensif
region_col = find_column_safely(["INDO5_TEAM_SPV_REGION", "INDO5_TO", "REGION", "WILAYAH"], "REGION")

year_col = find_column_safely(["YEAR", "YEAR_NUM", "TAHUN", "year"], "YEAR")
month_col = find_column_safely(["MONTH", "MONTH_NUM", "BULAN", "month"], "MONTH")
sku_col = find_column_safely(["inova_id_sku_name", "SKU NAME", "sku_name", "PRODUCT SKU NAME"], "PRODUCT SKU NAME")
category_col = find_column_safely(["CATEGORY", "KATEGORI", "category", "PRODUCT CATEGORY"], "CATEGORY")
value_metric_col = find_column_safely(["SUM OF VALUE", "VALUE", "value", "ACTUAL VALUE", "sum_of_value"], "Sum of Value")
qty_metric_col = find_column_safely(["SUM OF QTY", "QTY", "qty", "ACTUAL QTY", "sum_of_qty"], "Sum of Qty")

# Kolom filter tambahan baru & Kolom Kunci Channel Level 3
cust_code_col = find_column_safely(["inova_id_cust_code", "INOVA CODE", "cust_code"], "inova_id_cust_code")
cust_name_col = find_column_safely(["inova_id_cust_name", "NAMA OUTLET", "cust_name", "OUTLET NAME"], "inova_id_cust_name")
dist_cust_col = find_column_safely(["dist_cust_id", "ID APL/PPG", "dist_id"], "dist_cust_id")
channel_l3_col = find_column_safely(["CHANNEL LEVEL 3", "channel_level_3", "CHANNEL_L3"], "CHANNEL LEVEL 3")

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
df_proc[channel_l3_col] = df_proc[channel_l3_col].fillna("UNASSIGNED").astype(str).str.strip().str.upper()

# 🔒 [TESTING] SILAKAN SESUAIKAN NAMA REGION DI SINI UNTUK KEPENTINGAN SHARDING
TARGET_REGION_TEST = "REGION 1" 
df_proc = df_proc[df_proc[region_col].astype(str).str.upper().str.strip() == TARGET_REGION_TEST.upper()]

# ─── LOGIKA INTEGRASI TABEL SUPABASE: msa_recommendation ─────────────────────
df_msa = load_data_all(worksheet_name="msa_recommendation")

msa_ready = False

if not df_msa.empty:
    df_msa.columns = df_msa.columns.str.strip()
    
    # Resolver kolom dinamis untuk tabel msa
    msa_sku_col = next((c for c in df_msa.columns if c.upper() in ["SKU NAME", "SKU_NAME", "PRODUCT SKU NAME"]), None)
    msa_l3_col = next((c for c in df_msa.columns if c.upper() in ["CHANNEL LEVEL 3", "CHANNEL_LEVEL_3", "CHANNEL LEVEL3"]), None)
    msa_listing_col = next((c for c in df_msa.columns if c.upper() in ["STATUS LISTING", "STATUS_LISTING", "LISTING"]), None)
    
    if msa_sku_col and msa_l3_col and msa_listing_col:
        df_msa[msa_sku_col] = df_msa[msa_sku_col].astype(str).str.strip()
        df_msa[msa_l3_col] = df_msa[msa_l3_col].astype(str).str.strip().str.upper()
        df_msa[msa_listing_col] = pd.to_numeric(df_msa[msa_listing_col], errors='coerce').fillna(0).astype(int)
        msa_ready = True
else:
    st.warning("⚠️ Gagal memvalidasi listing karena tabel 'msa_recommendation' tidak ditemukan atau kosong.")

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

col_name_prev3 = f"{month_names_map[m_prev3]} {selected_year}"
col_name_prev2 = f"{month_names_map[m_prev2]} {selected_year}"
col_name_prev1 = f"{month_names_map[m_prev1]} {selected_year}"
col_name_current = f"{month_names_map[m_current]} {selected_year}"
avg_col_name = f"AVG QTY 3M ({month_names_map[m_prev3]}-{month_names_map[m_prev1]})"

# Amankan data subset bulan berjalan sebelum pivot dilakukan
df_matrix = df_matrix[df_matrix[month_col].isin(target_months_indices)]

# ─── RENDER TABEL UTAMA ──────────────────────────────────────────────────────

if not df_matrix.empty or msa_ready:
    
    # 1. BUAT PIVOT TABLE MURNI DARI TRANSAKSI AKTUAL TERLEBIH DAHULU (Menjamin data Maret & April utuh)
    if not df_matrix.empty:
        pivot_qty = df_matrix.pivot_table(
            index=[sku_col, category_col],
            columns=month_col,
            values=qty_metric_col,
            aggfunc='sum',
            fill_value=0.0
        ).reset_index()
    else:
        pivot_qty = pd.DataFrame(columns=[sku_col, category_col] + target_months_indices)

    # Pastikan seluruh rentang kolom bulan tersedia di dataframe hasil pivot
    for m_idx in target_months_indices:
        if m_idx not in pivot_qty.columns:
            pivot_qty[m_idx] = 0.0

    # 2. SELEKSI TARGET WAJIB DARI MSA KEMUDIAN SUNTIKKAN JIKA BELUM ADA DI TRANSAKSI
    if msa_ready:
        # Cari tahu channel apa saja yang aktif dari transaksi saat ini
        if not df_matrix.empty:
            active_channels_l3 = df_matrix[channel_l3_col].unique()
        else:
            active_channels_l3 = df_proc[channel_l3_col].unique()

        # Filter target wajib berstatus 1 dari master msa
        df_targets = df_msa[
            (df_msa[msa_listing_col] == 1) & 
            (df_msa[msa_l3_col].isin(active_channels_l3))
        ]
        
        # Cari SKU wajib yang belum masuk di pivot aktual
        existing_skus = pivot_qty[sku_col].unique() if not pivot_qty.empty else []
        missing_skus = df_targets[~df_targets[msa_sku_col].isin(existing_skus)][msa_sku_col].unique()
        
        if len(missing_skus) > 0:
            new_rows = []
            for m_sku in missing_skus:
                # Ambil kategori pendukung yang sesuai dari master msa
                match_cat_series = df_targets[df_targets[msa_sku_col] == m_sku][category_col]
                match_cat = str(match_cat_series.iloc[0]).strip().upper() if not match_cat_series.empty else "WOUND"
                
                row_data = {sku_col: m_sku, category_col: match_cat}
                for m_idx in target_months_indices:
                    row_data[m_idx] = 0.0
                new_rows.append(row_data)
                
            pivot_qty = pd.concat([pivot_qty, pd.DataFrame(new_rows)], ignore_index=True)

    # Kalkulasi rata-rata 3 bulan sebelum target berjalan secara aman
    pivot_qty[avg_col_name] = pivot_qty[[m_prev3, m_prev2, m_prev1]].mean(axis=1).apply(lambda x: math.ceil(x))

    # Reindex kolom menggunakan susunan asli bawaan
    final_view_cols = [sku_col, category_col, avg_col_name, m_prev2, m_prev1, m_current]
    pivot_qty = pivot_qty.reindex(columns=final_view_cols, fill_value=0.0)
    
    # 📌 REVISI POSISI KOLOM: Tambahkan kolom 'Target MSA' di posisi PALING KANAN (paling akhir)
    pivot_qty['Target MSA'] = "❌"
    
    # Isi penanda centang secara dinamis berdasarkan database master msa
    if msa_ready:
        for idx, row in pivot_qty.iterrows():
            current_sku = row[sku_col]
            is_listed = df_msa[(df_msa[msa_sku_col] == current_sku) & (df_msa[msa_listing_col] == 1)]
            if not is_listed.empty:
                pivot_qty.at[idx, 'Target MSA'] = "✅"

    # Setel penamaan label header kolom visual akhir
    pivot_qty.columns = ["PRODUCT SKU NAME", "CATEGORY", avg_col_name, col_name_prev2, col_name_prev1, col_name_current, "TARGET MSA"]

    # Urutkan prioritas: Target MSA (✅ di atas), lalu pencapaian kuantiti bulan saat ini tertinggi
    pivot_qty = pivot_qty.sort_values(by=["TARGET MSA", col_name_current], ascending=[False, False])

    # Ambil sum value untuk ringkasan baris total akhir
    val_m3 = df_matrix[df_matrix[month_col] == m_prev3][value_metric_col].sum() if not df_matrix.empty else 0.0
    val_m4 = df_matrix[df_matrix[month_col] == m_prev2][value_metric_col].sum() if not df_matrix.empty else 0.0
    val_m5 = df_matrix[df_matrix[month_col] == m_prev1][value_metric_col].sum() if not df_matrix.empty else 0.0
    val_m6 = df_matrix[df_matrix[month_col] == m_current][value_metric_col].sum() if not df_matrix.empty else 0.0
    avg_val_3m = math.ceil((val_m3 + val_m4 + val_m5) / 3)

    total_row_dict = {
        "PRODUCT SKU NAME": "TOTAL SUMMARY",
        "CATEGORY": "ALL VALUE (IDR)",
        avg_col_name: avg_val_3m,
        col_name_prev2: val_m4,
        col_name_prev1: val_m5,
        col_name_current: val_m6,
        "TARGET MSA": ""
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