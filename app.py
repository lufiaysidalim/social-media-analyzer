import streamlit as st

# Judul Utama
st.title("📊 Social Media Analyzer")
st.write("Masukkan parameter di bawah ini untuk memulai analisa:")

# 1. Kolom Input Utama
kata_kunci = st.text_input("Topik / Hashtag / Nama Akun:", placeholder="Contoh: #Pemilu2026 atau @username")

# 2. Tiga Filter Utama
col1, col2, col3 = st.columns(3)

with col1:
    medsos = st.multiselect("Platform:", ["Facebook", "Instagram", "TikTok", "X (Twitter)"])

with col2:
    jumlah_post = st.selectbox("Jumlah Post:", [50, 100, 500, 1000])

with col3:
    rentang_waktu = st.selectbox("Rentang Waktu:", ["1 Hari", "1 Minggu", "1 Bulan", "6 Bulan", "1 Tahun", "5 Tahun", "Custom"])

# Tampilkan opsi tanggal jika memilih Custom
if rentang_waktu == "Custom":
    st.date_input("Pilih Tanggal:")

# 3. Input Token Akses
token_user = st.text_input("Token Akses (Khusus Pengguna Berizin):", type="password")

# 4. Tombol Analisa
if st.button("🚀 ANALISA"):
    st.info("Proses analisa akan dijalankan...")
