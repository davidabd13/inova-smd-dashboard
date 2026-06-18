"""
utils.py — Betadine Sales Tracker Cloud Connection
Optimized for Large Dataset Ingestion (>100k rows) with PostgREST Pagination.
"""

import pandas as pd
import streamlit as st
import os
from supabase import create_client, Client

# ─── CONSTANTS & STYLING COLORS ──────────────────────────────────────────────
PRIMARY     = "#FF6200"  # Betadine Orange
SECONDARY   = "#002F6C"  # Deep Corporate Blue
LIGHT_GRAY  = "#F8FAFC"  # Clean card backgrounds
WHITE       = "#FFFFFF"

MAP_SKU_DISPLAY = {
    "no": "NO",
    "category": "CATEGORY",
    "sub_category": "SUB CATEGORY",
    "brand": "BRAND",
    "sku_name": "SKU NAME",
    "total_6_months": "TOTAL 6 MONTHS",
    "average": "AVERAGE"
}

@st.cache_resource
def init_supabase() -> Client:
    """Membuka koneksi aman ke Supabase Client."""
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        st.error("❌ Kredensial Supabase tidak ditemukan di Secrets!")
        return None
    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Gagal inisialisasi arsitektur database: {str(e)}")
        return None

@st.cache_data(ttl=1800)  # Simpan di cache selama 30 menit demi efisiensi RAM
def load_data_all(worksheet_name: str) -> pd.DataFrame:
    """
    Menarik seluruh data dari Supabase tanpa terpotong batas limit (Mendukung >100.000 baris)
    menggunakan teknik urutan range pagination.
    """
    # Strategi Fallback File Lokal CSV
    local_file = f"{worksheet_name}.csv"
    if os.path.exists(local_file):
        try:
            return pd.read_csv(local_file)
        except Exception:
            pass

    supabase = init_supabase()
    if not supabase:
        return pd.DataFrame()
        
    db_table_map = {
        "sellinbysku": "sellinbysku",
        "NEW RAW": "new_raw"
    }
    
    target_table = db_table_map.get(worksheet_name)
    if not target_table:
        return pd.DataFrame()
        
    try:
        all_records = []
        page_size = 1000  # Standar maksimal batas API Supabase per request
        start_row = 0
        
        # Buat placeholder loading bar di Streamlit agar user tahu proses sedang berjalan
        progress_bar = st.progress(0, text="Mengunduh data terintegrasi dari Supabase...")
        
        while True:
            # Tarik data bertahap menggunakan range (misal: 0-999, 1000-1999, dst)
            response = supabase.table(target_table)\
                               .select("*")\
                               .range(start_row, start_row + page_size - 1)\
                               .execute()
            
            batch_data = response.data
            if not batch_data:
                break
                
            all_records.extend(batch_data)
            
            # Jika baris yang dikembalikan kurang dari page_size, berarti ini halaman terakhir
            if len(batch_data) < page_size:
                break
                
            start_row += page_size
            
            # Update info status baris (Mencegah tampilan membeku)
            if start_row % 5000 == 0:
                progress_bar.progress(min(start_row / 150000, 0.95), text=f"Sudah mengunduh {start_row:,} baris data...")
                
        progress_bar.empty() # Hapus progress bar setelah selesai
        
        if not all_records:
            return pd.DataFrame()
            
        df = pd.DataFrame(all_records)
        
        # Bersihkan memori dari kolom tracking internal database
        for ts_col in ['created_at', 'id']:
            if ts_col in df.columns:
                df.drop(columns=[ts_col], inplace=True)
                
        # Lakukan pemetaan nama kolom database ke nama display legasi agar logika lama tidak rusak
        if worksheet_name == "sellinbysku":
            df.rename(columns=MAP_SKU_DISPLAY, inplace=True)
            
        return df
        
    except Exception as e:
        st.error(f"❌ Masalah transmisi data Supabase: {str(e)}")
        return pd.DataFrame()

def inject_css():
    """Menyuntikkan gaya visual Light-Mode dari assets/styles.css."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    css_path = os.path.join(current_dir, "assets", "styles.css")
    
    if os.path.exists(css_path):
        try:
            with open(css_path, "r") as f:
                css = f.read()
            st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
            return
        except Exception:
            pass
            
    # Fallback inline jika file css bermasalah
    st.markdown(
        f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            html, body, [data-testid="stAppViewContainer"] {{ font-family: 'Inter', sans-serif !important; background-color: #FFFFFF !important; color: #1E293B !important; }}
            div[data-baseweb="select"] {{ border-radius: 8px !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_footer():
    """Menampilkan footer di bawah halaman."""
    st.markdown(
        f"""
        <hr style='margin-top: 50px; border: 0; border-top: 1px solid #E2E8F0;' />
        <div style="text-align: center; color: #64748B; font-size: 0.7rem; font-weight: 500; padding-bottom: 15px;">
            © {pd.Timestamp.now().year} PT Oji Indo Makmur / Mundipharma Betadine Tracker. All Rights Reserved.
        </div>
        """,
        unsafe_allow_html=True
    )