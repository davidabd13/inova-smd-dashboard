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
    # PERBAIKAN: Pastikan kolom bulan dipaksa menjadi integer untuk kalkulasi filter
    df_matrix['MONTH_INT'] = pd.to_numeric(df_matrix[month_col], errors='coerce').fillna(0).astype(int)
    df_matrix['YEAR_INT'] = pd.to_numeric(df_matrix[year_col], errors='coerce').fillna(0).astype(int)
    
    # Filter data 4 bulan yang dibutuhkan (Maret=3, April=4, Mei=5, Juni=6)
    df_qty_4m = df_matrix[(df_matrix['YEAR_INT'] == selected_year) & (df_matrix['MONTH_INT'].isin([3, 4, 5, 6]))].copy()
    
    if df_qty_4m.empty:
        st.warning(f"⚠️ Data ditemukan, tetapi tidak ada transaksi pada bulan Maret s/d Juni untuk tahun {selected_year}.")
    else:
        # Pivot menggunakan kolom 'MONTH_INT' yang sudah pasti tipenya angka
        pivot_qty = df_qty_4m.pivot_table(
            index=[sku_col, category_col],
            columns='MONTH_INT',
            values=qty_metric_col,
            aggfunc='sum',
            fill_value=0.0
        ).reset_index()

        # Pastikan seluruh kolom bulan (3, 4, 5, 6) terbentuk di dataframe pivot
        for m in [3, 4, 5, 6]:
            if m not in pivot_qty.columns:
                pivot_qty[m] = 0.0

        # Perhitungan Average 3 Bulan Sebelumnya (Maret=3, April=4, Mei=5) & Round Up
        avg_col_name = f"AVG QTY 3M ({month_names_map[3]}-{month_names_map[5]})"
        pivot_qty[avg_col_name] = pivot_qty[[3, 4, 5]].mean(axis=1).apply(lambda x: math.ceil(x))

        # Reorganisasi Struktur Kolom Utama: SKU, Kategori, Avg 3M, April, Mei, Juni
        final_cols_qty = [sku_col, category_col, avg_col_name, 4, 5, 6]
        pivot_qty = pivot_qty.reindex(columns=final_cols_qty, fill_value=0.0)
        
        # Berikan nama string pada header kolom tabel
        pivot_qty.columns = ["PRODUCT SKU NAME", "CATEGORY", avg_col_name, "Apr 2026", "Mei 2026", "Jun 2026"]

        # 2. Perhitungan Baris TOTAL SUMMARY Berbasis Rupiah (SUM OF VALUE)
        val_m3 = df_matrix[(df_matrix['YEAR_INT'] == selected_year) & (df_matrix['MONTH_INT'] == 3)][value_metric_col].sum()
        val_m4 = df_matrix[(df_matrix['YEAR_INT'] == selected_year) & (df_matrix['MONTH_INT'] == 4)][value_metric_col].sum()
        val_m5 = df_matrix[(df_matrix['YEAR_INT'] == selected_year) & (df_matrix['MONTH_INT'] == 5)][value_metric_col].sum()
        val_m6 = df_matrix[(df_matrix['YEAR_INT'] == selected_year) & (df_matrix['MONTH_INT'] == 6)][value_metric_col].sum()
        
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

        # ─── DYNAMIC FORMATTING RULE ─────────────────────────────────────────
        def format_cells(df):
            formatted_df = df.copy()
            numeric_cols = [avg_col_name, "Apr 2026", "Mei 2026", "Jun 2026"]
            
            for col in numeric_cols:
                # Format baris reguler sebagai unit angka bulat (Qty)
                formatted_series = df[col].iloc[:-1].apply(lambda x: f"{x:,.0f}")
                # Format baris terakhir (Total Summary) dengan mata uang Rp (Value)
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
        
        # ─── EXCEL DOWNLOAD BUTTON ───────────────────────────────────────────
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