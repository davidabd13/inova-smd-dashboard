"""
utils.py — Betadine Sales Tracker
Central data loader, cloud integration, shared helper utilities, and bulletproof light-mode styling.
Optimized Professional Version - Integrated with Supabase Client (Auto Reverse-Mapping to Legacy Display Headers).
"""

import pandas as pd
import streamlit as st
import io
import os
import re
from supabase import create_client, Client

# ─── CONSTANTS ───────────────────────────────────────────────────────────────

PRIMARY     = "#FF6200"  # Betadine Orange
SECONDARY   = "#002F6C"  # Deep Corporate iNova Blue
ACCENT      = "#00AEEF"  # Light Blue Accent
DARK_GRAY   = "#1E293B"  # High-contrast Dark Text
LIGHT_GRAY  = "#F8FAFC"  # Clean card backgrounds
WHITE       = "#FFFFFF"
SUCCESS     = "#10B981"  # Vibrant Emerald Green
WARNING     = "#F59E0B"  # Clear Amber Warning
DANGER      = "#EF4444"  # Coral Red Danger

MONTH_NAMES = {
    1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"May", 6:"Jun",
    7:"Jul", 8:"Aug", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dec"
}

# ─── DATABASE REVERSE MAPPING (SNAKE_CASE -> LEGACY DISPLAY HEADERS) ──────────

MAP_SKU_DISPLAY = {
    "no": "NO",
    "category": "CATEGORY",
    "sub_category": "SUB CATEGORY",
    "brand": "BRAND",
    "sku_name": "SKU NAME",
    "na_june": "N-A JUNE",
    "na_july": "N-A JULY",
    "na_aug": "N-A AUG",
    "na_sept": "N-A SEPT",
    "na_oct": "N-A OCT",
    "na_nov": "N-A NOV",
    "total_6_months": "TOTAL 6 MONTHS",
    "average": "AVERAGE"
}

MAP_RAW_DISPLAY = {
    "year": "Year",
    "month_num": "Month Num",
    "month": "Month",
    "date": "Date",
    "sales_name": "Sales Name",
    "abm_kam": "ABM / KAM",
    "rbm": "RBM",
    "nsm": "NSM",
    "channel": "Channel",
    "sub_channel": "Sub Channel",
    "account_name": "Account Name",
    "store_id": "Store ID",
    "customer_name": "Customer Name",
    "city": "City",
    "area_name": "Area Name",
    "region_name": "Region Name",
    "brand": "Brand",
    "product_name": "Product Name",
    "actual_ims_value": "Actual IMS Value",
    "target_ims_value": "Target IMS Value",
    "oos_status": "OOS Status",
    "facing_share": "Facing Share"
}

# ─── CORE CLOUD CONNECTOR (SUPABASE) ─────────────────────────────────────────

@st.cache_resource
def init_supabase() -> Client:
    """Establishes a cached, secure connection to the backend Supabase instance."""
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        st.warning("⚠️ Cloud connection parameters missing. Attempting to run via fallback mechanism.")
        return None
    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Failed to initialize database architecture: {str(e)}")
        return None

@st.cache_data(ttl=600)  # Cache results safely for 10 minutes to maintain lightning speed
def load_data(worksheet_name: str, target_year: int = None, months_list: list = None) -> pd.DataFrame:
    """
    Bulletproof central data ingestion dengan optimasi RAM tingkat tinggi.
    Menerima filter target_year dan months_list opsional untuk membatasi pemuatan baris langsung dari query database.
    """
    # 1. Fallback Ingestion Strategy (Local Project Files)
    local_file = f"{worksheet_name}.csv"
    if os.path.exists(local_file):
        try:
            df_local = pd.read_csv(local_file)
            # Jika file lokal ada, bantu filter di level pandas untuk menghemat memori runtime
            if target_year and 'year' in df_local.columns:
                df_local = df_local[df_local['year'] == target_year]
            return df_local
        except Exception:
            pass

    # 2. Production Cloud Ingestion Strategy (Supabase)
    supabase = init_supabase()
    if not supabase:
        return pd.DataFrame()
        
    db_table_map = {
        "sellinbysku": "sellinbysku",
        "NEW RAW": "new_raw"
    }
    
    target_table = db_table_map.get(worksheet_name)
    if not target_table:
        st.error(f"❌ Unknown worksheet mapping identifier requested: '{worksheet_name}'")
        return pd.DataFrame()
        
    try:
        # Inisialisasi basis query data
        query = supabase.table(target_table).select("*")
        
        # ─── OPTIMASI RAM: Query Filtering tingkat Database ───
        # Jika parameter filter tahun & rentang bulan dikirim dari halaman depan, jalankan filter server-side
        if target_year:
            query = query.eq("year", target_year)
        if months_list:
            # Supabase Python mengandalkan pencocokan tipe list array (.in_ atau filter kustom)
            query = query.in_("month_num", months_list)

        # Ambil data hasil filter dengan limit aman
        response = query.limit(50000).execute()
        data = response.data
        
        if not data:
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        
        # Strip internal database timestamps jika ada untuk menghemat ruang memori kolom
        for ts_col in ['created_at', 'id']:
            if ts_col in df.columns:
                df.drop(columns=[ts_col], inplace=True)
                
        # Apply strict reverse-mapping to prevent any downstream KeyErrors
        if worksheet_name == "sellinbysku":
            df.rename(columns=MAP_SKU_DISPLAY, inplace=True)
        elif worksheet_name == "NEW RAW":
            df.rename(columns=MAP_RAW_DISPLAY, inplace=True)
            
        return df
    except Exception as e:
        st.error(f"❌ Cloud execution error during data retrieval pipeline: {str(e)}")
        return pd.DataFrame()

# ─── INTERFACE VISUAL INJECTORS & NAVIGATION ──────────────────────────────────

def inject_css():
    """Injects high-fidelity corporate light-mode theme directly from assets/styles.css."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    css_path = os.path.join(current_dir, "assets", "styles.css")
    
    if os.path.exists(css_path):
        try:
            with open(css_path, "r") as f:
                css = f.read()
                
            css = css\
                .replace("__PRIMARY__", PRIMARY)\
                .replace("__SECONDARY__", SECONDARY)\
                .replace("__ACCENT__", ACCENT)\
                .replace("__DARK_GRAY__", DARK_GRAY)\
                .replace("__LIGHT_GRAY__", LIGHT_GRAY)\
                .replace("__WHITE__", WHITE)\
                .replace("__SUCCESS__", SUCCESS)\
                .replace("__WARNING__", WARNING)\
                .replace("__DANGER__", DANGER)
                
            st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
            return
        except Exception as e:
            st.warning(f"⚠️ Gagal membaca berkas eksternal assets/styles.css ({e}), memuat gaya bawaan...")

    st.markdown(
        f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            
            html, body, [data-testid="stAppViewContainer"] {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
                background-color: {WHITE} !important;
                color: {DARK_GRAY} !important;
            }}
            
            [data-testid="stSidebar"] {{
                background-color: {LIGHT_GRAY} !important;
                border-right: 1px solid #E2E8F0 !important;
            }}
            
            .kpi-card {{
                background-color: {WHITE};
                padding: 1.25rem;
                border-radius: 12px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
                border: 1px solid #E2E8F0;
                margin-bottom: 1rem;
            }}
            .kpi-card-inner {{
                display: flex;
                flex-direction: column;
            }}
            .kpi-label {{
                font-size: 0.85rem;
                font-weight: 600;
                color: #64748B;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 0.35rem;
            }}
            .kpi-value {{
                font-size: 1.75rem;
                font-weight: 700;
                color: {SECONDARY};
                line-height: 1.2;
            }}
            .kpi-delta {{
                font-size: 0.85rem;
                font-weight: 600;
                margin-top: 0.4rem;
                display: inline-flex;
                align-items: center;
            }}
            .kpi-delta.up {{ color: {SUCCESS}; }}
            .kpi-delta.down {{ color: {DANGER}; }}
            
            .section-title {{
                font-size: 1.35rem;
                font-weight: 700;
                color: {SECONDARY};
                border-left: 5px solid {PRIMARY};
                padding-left: 12px;
                margin-top: 1.5rem;
                margin-bottom: 1.25rem;
            }}
            
            div[data-baseweb="select"] {{
                border-radius: 8px !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def sidebar_nav():
    """Renders the modern, clean side navigation menu adjusted to the current layout."""
    st.sidebar.markdown(
        f"""
        <div style='padding: 10px 0px; text-align: center;'>
            <h2 style='margin: 0; color: {PRIMARY}; font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em;'>BETADINE</h2>
            <p style='margin: 2px 0 0 0; color: {SECONDARY}; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em;'>Sales Analytics Portal</p>
        </div>
        <hr style='margin-top: 10px; margin-bottom: 20px; border: 0; border-top: 1px solid #E2E8F0;' />
        """, 
        unsafe_allow_html=True
    )
    
    st.sidebar.markdown(
        f"<div style='color: #64748B; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px; padding-left: 5px;'>MAIN DASHBOARD</div>", 
        unsafe_allow_html=True
    )
    
    st.sidebar.page_link("pages/1_Actual_Sales_Performance.py", label="Actual Sales Performance", icon="📈")
    
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

# ─── REUSABLE UI COMPONENT BUILDERS ──────────────────────────────────────────

def kpi_card(label: str, value: str, delta: str = None, delta_dir: str = "up", val_color: str = None):
    delta_html = f"<div class='kpi-delta {delta_dir}'>{delta}</div>" if delta else ""
    style_val = f"style='color: {val_color} !important;'" if val_color else ""
    
    st.markdown(
        f"""
        <div class='kpi-card'>
            <div class='kpi-card-inner'>
                <div class='kpi-label'>{label}</div>
                <div class='kpi-value' {style_val}>{value}</div>
                {delta_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def section_title(title: str):
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)

def render_footer():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    footer_path = os.path.join(current_dir, "assets", "footer.html")
    try:
        with open(footer_path, "r") as f:
            footer_html = f.read()
        st.markdown(footer_html, unsafe_allow_html=True)
    except Exception:
        st.markdown(
            f"""
            <hr style='margin-top: 50px; border: 0; border-top: 1px solid #E2E8F0;' />
            <div class="custom-footer" style="text-align: center !important; color: #64748B !important; font-size: 0.65rem !important; font-weight: 500 !important; letter-spacing: 0.03em; padding-bottom: 15px;">
                © {pd.Timestamp.now().year} PT Oji Indo Makmur / Mundipharma Betadine Tracker. All Rights Reserved.
            </div>
            """,
            unsafe_allow_html=True
        )