import streamlit as st
import pandas as pd
import io
import math
from utils import load_data_all, inject_css, render_footer, SECONDARY

# ─── CONFIG & STYLING ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Betadine Sales Tracker Portal",
    layout="wide",
    initial_sidebar_state="expanded" # Mengunci sidebar agar tetap terbuka statis
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
sku_col = find_column_safely(["inova_id_sku_name", "SKU NAME", "sku_name", "PRODUCT SKU NAME"], "PRODUCT SKU NAME")
category_col = find_column_safely(["CATEGORY", "KATEGORI", "category", "PRODUCT CATEGORY"], "CATEGORY")
value_metric_col = find_column_safely(["SUM OF VALUE", "VALUE", "value", "ACTUAL VALUE", "sum_of_value"], "Sum of Value")
qty_metric_col = find_column_safely(["SUM OF QTY", "QTY", "qty", "ACTUAL QTY", "sum_of_qty"], "Sum of Qty")

# ─── CLEANING & TYPE CONVERSIONS ─────────────────────────────────────────────
df_proc[year_col] = pd.to_numeric(df_proc[year_col], errors='coerce').fillna(2026).astype(int)
df_proc[month_col] = pd.to_numeric(df_proc[month_col], errors='coerce').fillna(6).astype(int)
df_proc[value_metric_col] = pd.to_numeric(df_proc[value_metric_col], errors='coerce').fillna(0.0)
df_proc[qty_metric_col] = pd.to_numeric(df_proc[qty_metric_col], errors='coerce').fillna(0.0)

df_proc[category_col] = df_proc[category_col].fillna("WOUND").astype(str).str.strip().str.upper()
df_proc[sku_col] = df_proc[sku_col].fillna("UNASSIGNED").astype(str).str.strip()

# ─── SIDEBAR LOCK TIME BASE ──────────────────────────────────────────────────
st.sidebar.header("🔍 Filter Waktu Analisis")
available_years = sorted(list(df_proc[year_col].unique()), reverse=True)
selected_year = st.sidebar.selectbox("Tahun Target", available_years if available_years else [2026], index=0)

available_months = sorted(list(df_proc[df_proc[year_col] == selected_year][month_col].unique()), reverse=True)
selected_month = st.sidebar.selectbox("Bulan Target Basis", available_months if available_months else [6], index=0)

# ─── LOGIKA PENENTUAN 4 BULAN BERJALAN SECARA DINAMIS (REUSEABLE) ────────────
month_names_map = {
    1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"Mei", 6:"Jun",
    7:"Jul", 8:"Agu", 9:"Sep", 10:"Okt", 11:"Nov", 12:"Des"
}

# Hitung mundur 4 bulan dari bulan yang dipilih pengguna
target_months_indices = []
for i in range(3, -1, -1):
    m = selected_month - i
    if m <= 0:
        m += 12 # Rollback ke tahun sebelumnya jika filter dipilih Januari/Februari
    target_months_indices.append(m)

m_prev3, m_prev2, m_prev1, m_current = target_months_indices

# Membuat label nama kolom string dinamis
col_name_prev2 = f"{month_names_map[m_prev2]} {selected_year}"
col_name_prev1 = f"{month_names_map[m_prev1]} {selected_year}"
col_name_current = f"{month_names_map[m_current]} {selected_year}"
avg_col_name = f"AVG QTY 3M ({month_names_map[m_prev3]}-{month_names_map[m_prev1]})"

# ─── MAIN DISPLAY MATRIX AREA ────────────────────────────────────────────────
st.subheader("📋 Matriks Pivot Performa Produk (3 Bulan Rolling)")

# Filter Kategori Produk diletakkan di bagian atas tabel utama (Sesuai Layout Gambar)
available_categories = ["All Categories"] + sorted(list(df_proc[category_col].unique()))
selected_category = st.selectbox("Filter Kategori Produk", available_categories, index=0)

df_matrix = df_proc[df_proc[year_col] == selected_year].copy()
if selected_category != "All Categories":
    df_matrix = df_matrix[df_matrix[category_col] == selected_category]

# Bangun pemetaan dinamis untuk kolom pivot
dynamic_month_map = {
    m_prev3: f"{month_names_map[m_prev3]} {selected_year}",
    m_prev2: col_name_prev2,
    m_prev1: col_name_prev1,
    m_current: col_name_current
}
df_matrix['Period_Name'] = df_matrix[month_col].map(dynamic_month_map)
df_matrix = df_matrix[df_matrix[month_col].isin(target_months_indices)]

if not df_matrix.empty:
    # 1. Pembuatan Pivot Table Utama untuk Qty
    pivot_qty = df_matrix.pivot_table(
        index=[sku_col, category_col],
        columns='Period_Name',
        values=qty_metric_col,
        aggfunc='sum',
        fill_value=0.0
    ).reset_index()

    # Pastikan struktur kolom lengkap tanpa bug pecahan
    for m_label in dynamic_month_map.values():
        if m_label not in pivot_qty.columns:
            pivot_qty[m_label] = 0.0

    # 2. Perhitungan Validasi Rata-rata 3 Bulan Sebelumnya
    str_prev3 = dynamic_month_map[m_prev3]
    str_prev2 = dynamic_month_map[m_prev2]
    str_prev1 = dynamic_month_map[m_prev1]
    
    pivot_qty[avg_col_name] = pivot_qty[[str_prev3, str_prev2, str_prev1]].mean(axis=1).apply(lambda x: math.ceil(x))

    # Re-index susunan kolom visual akhir (Menyembunyikan bulan terlama m_prev3)
    final_view_cols = [sku_col, category_col, avg_col_name, col_name_prev2, col_name_prev1, col_name_current]
    pivot_qty = pivot_qty.reindex(columns=final_view_cols, fill_value=0.0)
    pivot_qty.columns = ["PRODUCT SKU NAME", "CATEGORY", avg_col_name, col_name_prev2, col_name_prev1, col_name_current]

    # Sorting berdasarkan performa bulan berjalan tertinggi
    pivot_qty = pivot_qty.sort_values(by=col_name_current, ascending=False)

    # 3. Perhitungan Baris TOTAL SUMMARY Berbasis Nilai RUPIAH (SUM OF VALUE)
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
        
        # Kolom angka yang diproses
        loop_cols = [avg_col_name, col_name_prev2, col_name_prev1, col_name_current]
        
        for idx, row in df.iterrows():
            if idx == last_row_idx:
                # Format Khusus Baris Total Akhir -> Menggunakan Prefix Rp
                for col in loop_cols:
                    formatted_df.at[idx, col] = f"Rp {row[col]:,.0f}"
            else:
                # AMBIL VALUE ASLI LOGIKA WARNA (Sebelum diconvert ke string)
                v_avg = row[avg_col_name]
                v_prev2 = row[col_name_prev2] # Contoh: April
                v_prev1 = row[col_name_prev1] # Contoh: Mei
                v_current = row[col_name_current] # Contoh: Juni
                
                # 1. Format Kolom Avg 3M
                formatted_df.at[idx, avg_col_name] = f"{v_avg:,.0f} PCS"
                
                # 2. Format Kolom Bulan Ke-1 (April) -> Dibandingkan dengan Avg
                if v_prev2 == 0:
                    formatted_df.at[idx, col_name_prev2] = f"<span style='color: #DC2626; font-weight: 600;'>0 PCS</span>"
                elif v_avg > v_prev2:
                    formatted_df.at[idx, col_name_prev2] = f"<span style='color: #D97706;'>{v_prev2:,.0f} PCS</span>"
                else:
                    formatted_df.at[idx, col_name_prev2] = f"{v_prev2:,.0f} PCS"
                
                # 3. Format Kolom Bulan Ke-2 (Mei) -> Dibandingkan dengan Bulan Ke-1 (April)
                if v_prev1 == 0:
                    formatted_df.at[idx, col_name_prev1] = f"<span style='color: #DC2626; font-weight: 600;'>0 PCS</span>"
                elif v_prev2 > v_prev1:
                    formatted_df.at[idx, col_name_prev1] = f"<span style='color: #D97706;'>{v_prev1:,.0f} PCS</span>"
                else:
                    formatted_df.at[idx, col_name_prev1] = f"{v_prev1:,.0f} PCS"
                    
                # 4. Format Kolom Bulan Berjalan (Juni) -> Dibandingkan dengan Bulan Ke-2 (Mei)
                # Jika Mei < Juni, maka warna hitam default
                if v_current == 0:
                    formatted_df.at[idx, col_name_current] = f"<span style='color: #DC2626; font-weight: 600;'>0 PCS</span>"
                elif v_prev1 > v_current:
                    formatted_df.at[idx, col_name_current] = f"<span style='color: #D97706;'>{v_current:,.0f} PCS</span>"
                else:
                    formatted_df.at[idx, col_name_current] = f"{v_current:,.0f} PCS"
                    
        return formatted_df

    df_display = format_cells_with_rules(df_pivot_final)

    # Mempercantik Tampilan Element Tabel Supaya Support HTML Render Span Tag Warna
    st.markdown(
        f"""
        <style>
            div[data-testid="stDataFrame"] table {{ background-color: #FFFFFF !important; color: #1E293B !important; }}
            div[data-testid="stDataFrame"] th {{ background-color: {SECONDARY} !important; color: #FFFFFF !important; font-weight: 700 !important; }}
        </style>
        """, 
        unsafe_allow_html=True
    )
    
    # Render menggunakan st.write / HTML markdown table agar warna CSS span berfungsi optimal di browser
    st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)
    st.write("<br>", unsafe_allow_html=True)
    
    # ─── EXCEL DOWNLOAD BUTTON ───────────────────────────────────────────────
    col_space, col_btn = st.columns([8, 2])
    with col_btn:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_pivot_final.to_excel(writer, index=False, sheet_name='3M_Sales_Matrix')
        st.download_button(
            label="📥 Download Pivot Report (Excel)",
            data=output.getvalue(),
            file_name=f"Actual_Performance_Rolling_Month_{selected_month}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.warning(f"⚠️ Tidak ada data transaksi aktual pada rentang waktu yang dipilih pada tahun {selected_year}.")

render_footer()