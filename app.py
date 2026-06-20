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
sku_col = find_column_safely(["PRODUCT SKU NAME", "SKU NAME", "sku_name"], "PRODUCT SKU NAME")
category_col = find_column_safely(["CATEGORY", "KATEGORI", "category"], "CATEGORY")
value_metric_col = find_column_safely(["SUM OF VALUE", "VALUE", "value"], "Sum of Value")
qty_metric_col = find_column_safely(["SUM OF QTY", "QTY", "qty"], "Sum of Qty")

# ─── CLEANING & TYPE CONVERSIONS ─────────────────────────────────────────────
df_proc[year_col] = pd.to_numeric(df_proc[year_col], errors='coerce').fillna(2026).astype(int)
df_proc[month_col] = pd.to_numeric(df_proc[month_col], errors='coerce').fillna(1).astype(int)
df_proc[value_metric_col] = pd.to_numeric(df_proc[value_metric_col], errors='coerce').fillna(0.0)
df_proc[qty_metric_col] = pd.to_numeric(df_proc[qty_metric_col], errors='coerce').fillna(0.0)

df_proc[category_col] = df_proc[category_col].fillna("WOUND").astype(str).str.strip().str.upper()
df_proc[sku_col] = df_proc[sku_col].fillna("UNASSIGNED").astype(str).str.strip()

# ─── SIDEBAR LOCK TIME BASE ONLY ─────────────────────────────────────────────
st.sidebar.header("🔍 Filter Waktu Analisis")
available_years = sorted(list(df_proc[year_col].unique()), reverse=True)
selected_year = st.sidebar.selectbox("Tahun Target", available_years if available_years else [2026], index=0)

# Mengunci Juni 2026 sebagai basis target (Bulan 6)
selected_month = 6 

# Pemetaan Nama Bulan
month_names_map = {
    1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"Mei", 6:"Jun",
    7:"Jul", 8:"Agu", 9:"Sep", 10:"Okt", 11:"Nov", 12:"Des"
}

# ─── PROSES PIVOT & PERHITUNGAN MATRIKS (QTY) ────────────────────────────────
st.subheader("📋 Matriks Pivot Performa Produk (3 Bulan Rolling)")

# Filter Kategori Produk di area utama (Sesuai Gambar Layout)
available_categories = ["All Categories"] + sorted(list(df_proc[category_col].unique()))
selected_category = st.selectbox("Filter Kategori Produk", available_categories, index=0)
if selected_category != "All Categories":
    df_matrix = df_proc[df_proc[category_col] == selected_category].copy()
else:
    df_matrix = df_proc.copy()

if not df_matrix.empty:
    # 1. Pivot untuk QTY (Maret, April, Mei, Juni)
    # Filter data 4 bulan yang dibutuhkan (Bulan 3, 4, 5, 6)
    df_qty_4m = df_matrix[(df_matrix[year_col] == selected_year) & (df_matrix[month_col].isin([3, 4, 5, 6]))]
    
    pivot_qty = df_qty_4m.pivot_table(
        index=[sku_col, category_col],
        columns=month_col,
        values=qty_metric_col,
        aggfunc='sum',
        fill_value=0.0
    ).reset_index()

    # Pastikan seluruh kolom bulan (3, 4, 5, 6) terbentuk di dataframe
    for m in [3, 4, 5, 6]:
        if m not in pivot_qty.columns:
            pivot_qty[m] = 0.0

    # Perhitungan Average 3 Bulan Sebelumnya (Maret, April, Mei) & Round Up
    avg_col_name = f"AVG QTY 3M ({month_names_map[3]}-{month_names_map[5]})"
    pivot_qty[avg_col_name] = pivot_qty[[3, 4, 5]].mean(axis=1).apply(lambda x: math.ceil(x))

    # Reorganisasi Struktur Kolom Utama sesuai ekspektasi
    # SKU, Kategori, Avg 3M, April, Mei, Juni
    final_cols_qty = [sku_col, category_col, avg_col_name, 4, 5, 6]
    pivot_qty = pivot_qty.reindex(columns=final_cols_qty)
    
    # Berikan nama string pada header bulan
    pivot_qty.columns = ["PRODUCT SKU NAME", "CATEGORY", avg_col_name, "Apr 2026", "Mei 2026", "Jun 2026"]

    # 2. Perhitungan Baris TOTAL SUMMARY Berbasis Rupiah (SUM OF VALUE)
    # Ambil total Value dari data yang terfilter kategori untuk bulan terkait
    df_val_filtered = df_matrix[(df_matrix[year_col] == selected_year)]
    
    val_m3 = df_val_filtered[df_val_filtered[month_col] == 3][value_metric_col].sum()
    val_m4 = df_val_filtered[df_val_filtered[month_col] == 4][value_metric_col].sum()
    val_m5 = df_val_filtered[df_val_filtered[month_col] == 5][value_metric_col].sum()
    val_m6 = df_val_filtered[df_val_filtered[month_col] == 6][value_metric_col].sum()
    
    avg_val_3m = math.ceil((val_m3 + val_m4 + val_m5) / 3)

    # Gabungkan baris total summary ke dalam tabel utama
    total_row_dict = {
        "PRODUCT SKU NAME": "TOTAL SUMMARY",
        "CATEGORY": "ALL VALUE (IDR)",
        avg_col_name: avg_val_3m,
        "Apr 2026": val_m4,
        "Mei 2026": val_m5,
        "Jun 2026": val_m6
    }
    
    df_pivot_final = pd.concat([pivot_qty, pd.DataFrame([total_row_dict])], ignore_index=True)

    # ─── DYNAMIC FORMATTING RULE ─────────────────────────────────────────────
    # Agar baris terakhir muncul Rp sedangkan data atas berupa angka bulat biasa (Unit Qty)
    def format_cells(df):
        formatted_df = df.copy()
        numeric_cols = [avg_col_name, "Apr 2026", "Mei 2026", "Jun 2026"]
        
        for col in numeric_cols:
            # Format baris reguler (0 sampai N-1) sebagai unit angka bulat
            formatted_series = df[col].iloc[:-1].apply(lambda x: f"{x:,.0f}")
            # Format baris terakhir (Total Summary) dengan prefix mata uang Rp
            total_val = df[col].iloc[-1]
            formatted_series.loc[df.index[-1]] = f"Rp {total_val:,.0f}"
            
            formatted_df[col] = formatted_series
        return formatted_df

    df_display = format_cells(df_pivot_final)

    # Inject style table agar kontras tinggi
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
    st.warning("⚠️ Tidak ada riwayat transaksi yang cocok dengan kombinasi filter saat ini.")

render_footer()