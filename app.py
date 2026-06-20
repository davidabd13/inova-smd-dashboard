import streamlit as st
import pandas as pd
import io
import math
from utils import load_data_all, inject_css, render_footer, SECONDARY

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

year_col = find_column_safely(["YEAR", "YEAR_NUM", "TAHUN", "year"], "YEAR")
month_col = find_column_safely(["MONTH", "MONTH_NUM", "BULAN", "month"], "MONTH")
sku_col = find_column_safely(["inova_id_sku_name", "SKU NAME", "sku_name", "INOVA ID SKU NAME"], "PRODUCT SKU NAME")
category_col = find_column_safely(["CATEGORY", "KATEGORI", "category", "PRODUCT CATEGORY"], "CATEGORY")
value_metric_col = find_column_safely(["SUM OF VALUE", "VALUE", "value", "ACTUAL VALUE", "TOTAL_SALES"], "Sum of Value")
qty_metric_col = find_column_safely(["SUM OF QTY", "QTY", "qty", "ACTUAL QTY", "TOTAL_QTY"], "Sum of Qty")

# ─── CLEANING & TYPE CONVERSIONS (Aman Tanpa Merusak Data Asli) ──────────────
df_proc[year_col] = pd.to_numeric(df_proc[year_col], errors='coerce').fillna(2026).astype(int)
df_proc[month_col] = pd.to_numeric(df_proc[month_col], errors='coerce').fillna(6).astype(int)
df_proc[value_metric_col] = pd.to_numeric(df_proc[value_metric_col], errors='coerce').fillna(0.0)
df_proc[qty_metric_col] = pd.to_numeric(df_proc[qty_metric_col], errors='coerce').fillna(0.0)

df_proc[category_col] = df_proc[category_col].fillna("WOUND").astype(str).str.strip().str.upper()
df_proc[sku_col] = df_proc[sku_col].fillna("UNASSIGNED").astype(str).str.strip()

# ─── SIDEBAR LOCK TIME BASE ONLY ─────────────────────────────────────────────
st.sidebar.header("🔍 Filter Waktu Analisis")
available_years = sorted(list(df_proc[year_col].unique()), reverse=True)
selected_year = st.sidebar.selectbox("Tahun Target", available_years if available_years else [2026], index=0)

# ─── MAIN DISPLAY MATRIX AREA ────────────────────────────────────────────────
st.subheader("📋 Matriks Pivot Performa Produk (3 Bulan Rolling)")

# Filter Kategori Produk di area utama (Sesuai Layout Gambar Utama)
available_categories = ["All Categories"] + sorted(list(df_proc[category_col].unique()))
selected_category = st.selectbox("Filter Kategori Produk", available_categories, index=0)

df_matrix = df_proc[df_proc[year_col] == selected_year].copy()
if selected_category != "All Categories":
    df_matrix = df_matrix[df_matrix[category_col] == selected_category]

# Pemetaan Nama Bulan String
month_names_map = {3: "Mar 2026", 4: "Apr 2026", 5: "Mei 2026", 6: "Jun 2026"}
df_matrix['Period_Name'] = df_matrix[month_col].map(month_names_map)

# Filter Hanya 4 Bulan yang Valid (Maret s/d Juni)
df_matrix = df_matrix[df_matrix[month_col].isin([3, 4, 5, 6])]

if not df_matrix.empty:
    # 1. Pembentukan Pivot Table Menggunakan Nama String Bulan Langsung
    pivot_qty = df_matrix.pivot_table(
        index=[sku_col, category_col],
        columns='Period_Name',
        values=qty_metric_col,
        aggfunc='sum',
        fill_value=0.0
    ).reset_index()

    # Proteksi: Pastikan seluruh kolom bulan target tersedia di dataframe hasil pivot
    for m_name in month_names_map.values():
        if m_name not in pivot_qty.columns:
            pivot_qty[m_name] = 0.0

    # 2. Jalankan Perhitungan Rumus Average 3M (Maret, April, Mei)
    avg_col_name = "AVG QTY 3M (Mar-Mei)"
    pivot_qty[avg_col_name] = pivot_qty[["Mar 2026", "Apr 2026", "Mei 2026"]].mean(axis=1).apply(lambda x: math.ceil(x))

    # Re-order susunan kolom: SKU, Kategori, Avg 3M, April, Mei, Juni (Kolom Maret di-drop dari visual sesuai gambar)
    final_view_cols = [sku_col, category_col, avg_col_name, "Apr 2026", "Mei 2026", "Jun 2026"]
    pivot_qty = pivot_qty.reindex(columns=final_view_cols, fill_value=0.0)
    pivot_qty.columns = ["PRODUCT SKU NAME", "CATEGORY", avg_col_name, "Apr 2026", "Mei 2026", "Jun 2026"]

    # Sorting dari total Qty tertinggi di bulan berjalan (Juni) agar mirip contoh gambar
    pivot_qty = pivot_qty.sort_values(by="Jun 2026", ascending=False)

    # 3. Hitung Baris TOTAL SUMMARY Berbasis RUPIAH (SUM OF VALUE)
    val_m3 = df_matrix[df_matrix[month_col] == 3][value_metric_col].sum()
    val_m4 = df_matrix[df_matrix[month_col] == 4][value_metric_col].sum()
    val_m5 = df_matrix[df_matrix[month_col] == 5][value_metric_col].sum()
    val_m6 = df_matrix[df_matrix[month_col] == 6][value_metric_col].sum()
    avg_val_3m = math.ceil((val_m3 + val_m4 + val_m5) / 3)

    total_row_dict = {
        "PRODUCT SKU NAME": "TOTAL SUMMARY",
        "CATEGORY": "ALL VALUE (IDR)",
        avg_col_name: avg_val_3m,
        "Apr 2026": val_m4,
        "Mei 2026": val_m5,
        "Jun 2026": val_m6
    }
    
    df_pivot_final = pd.concat([pivot_qty, pd.DataFrame([total_row_dict])], ignore_index=True)

    # ─── DYNAMIC COERCION FORMATTING FOR DISPLAY ─────────────────────────────
    def format_cells(df):
        formatted_df = df.copy()
        numeric_cols = [avg_col_name, "Apr 2026", "Mei 2026", "Jun 2026"]
        
        for col in numeric_cols:
            # Baris data produk (0 s/d N-1) diformat Angka/Qty bulat biasa
            formatted_series = df[col].iloc[:-1].apply(lambda x: f"{x:,.0f}")
            # Baris Terakhir (TOTAL SUMMARY) dipaksa memunculkan format Rupiah (Rp)
            total_val = df[col].iloc[-1]
            formatted_series.loc[df.index[-1]] = f"Rp {total_val:,.0f}"
            
            formatted_df[col] = formatted_series
        return formatted_df

    df_display = format_cells(df_pivot_final)

    # Styling Table Tampilan High Contrast
    st.markdown(
        f"""
        <style>
            div[data-testid="stDataFrame"] table {{ background-color: #FFFFFF !important; color: #1E293B !important; }}
            div[data-testid="stDataFrame"] th {{ background-color: {SECONDARY} !important; color: #FFFFFF !important; font-weight: 700 !important; }}
        </style>
        """, 
        unsafe_allow_html=True
    )
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    # ─── EXCEL DOWNLOAD BUTTON ───────────────────────────────────────────────
    col_space, col_btn = st.columns([8, 2])
    with col_btn:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_pivot_final.to_excel(writer, index=False, sheet_name='3M_Sales_Matrix')
        st.download_button(
            label="📥 Download Pivot Report (Excel)",
            data=output.getvalue(),
            file_name="Actual_Performance_Rolling_3M.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.warning("⚠️ Tidak ada data transaksi aktual pada rentang waktu Maret - Juni 2026.")

render_footer()