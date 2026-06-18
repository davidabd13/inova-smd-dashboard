"""
Main.py — Betadine Sales Tracker Portal
Entry point utama aplikasi Streamlit. Menampilkan halaman selamat datang 
dan mengarahkan navigasi langsung ke halaman analisis yang aktif.
"""

import streamlit as st
import pandas as pd
from utils import (
    inject_css, 
    sidebar_nav, 
    section_title, 
    render_footer, 
    PRIMARY, 
    SECONDARY, 
    LIGHT_GRAY
)

# ─── CONFIG & STYLING ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Betadine Sales Tracker Portal",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Suntikkan gaya CSS global dari assets/styles.css dan tampilkan menu sidebar kustom
inject_css()
sidebar_nav()

# ─── HERO SECTION BANNER ─────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style='background: linear-gradient(135deg, {SECONDARY} 0%, #1E40AF 100%); padding: 40px; border-radius: 16px; color: white; margin-bottom: 30px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);'>
        <h1 style='margin: 0; font-size: 2.5rem; font-weight: 800; letter-spacing: -0.02em;'>Betadine Sales Analytics Portal</h1>
        <p style='margin: 10px 0 0 0; font-size: 1.1rem; font-weight: 400; opacity: 0.9;'>Selamat datang di platform pusat data dan analisis kinerja penjualan Betadine. Gunakan menu di sebelah kiri untuk melihat laporan interaktif secara real-time.</p>
    </div>
    """, 
    unsafe_allow_html=True
)

# ─── WORKSPACE OVERVIEW ──────────────────────────────────────────────────────
section_title("Ikhtisar Menu Analisis Dashboard")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        f"""
        <div style='background-color: {LIGHT_GRAY}; padding: 24px; border-radius: 12px; border-top: 4px solid {PRIMARY}; height: 220px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);'>
            <h4 style='margin-top: 0; color: {SECONDARY}; font-weight: 700;'>📈 Actual Sales Performance</h4>
            <p style='font-size: 0.9rem; color: #475569; line-height: 1.5;'>Analisis performa penjualan aktual (Sell-In) berkecepatan tinggi yang dipecah secara detail berdasarkan SKU dan Kategori, serta akumulasi tren matriks pivot selama <b>3 bulan terakhir</b>.</p>
        </div>
        """, 
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        f"""
        <div style='background-color: {LIGHT_GRAY}; padding: 24px; border-radius: 12px; border-top: 4px solid {PRIMARY}; height: 220px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);'>
            <h4 style='margin-top: 0; color: {SECONDARY}; font-weight: 700;'>🏬 Active Outlet Analysis</h4>
            <p style='font-size: 0.9rem; color: #475569; line-height: 1.5;'>Laporan penetrasi outlet aktif nasional. Dilengkapi dengan filter interaktif berjenjang berdasarkan wilayah, rantai retail (Chain Account), serta performa pencapaian target toko.</p>
        </div>
        """, 
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        f"""
        <div style='background-color: {LIGHT_GRAY}; padding: 24px; border-radius: 12px; border-top: 4px solid {PRIMARY}; height: 220px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);'>
            <h4 style='margin-top: 0; color: {SECONDARY}; font-weight: 700;'>🏆 Performance Leaderboard</h4>
            <p style='font-size: 0.9rem; color: #475569; line-height: 1.5;'>Peringkat kontribusi pendapatan tim Sales. Melacak total nilai penjualan (IMS Value) terhadap target, serta persentase pencapaian kinerja individu atau tim ABM/KAM.</p>
        </div>
        """, 
        unsafe_allow_html=True
    )

# ─── QUICK TIPS INFO BOX ─────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.info("💡 **Petunjuk Penggunaan:** Jika menu halaman tidak muncul di sidebar kiri, pastikan Anda menjalankan aplikasi ini dari terminal lokal menggunakan perintah `streamlit run Main.py` dan pastikan folder bernama `pages` ditulis dengan huruf kecil semua.")

# Tampilkan footer korporat di bagian paling bawah halaman
render_footer()