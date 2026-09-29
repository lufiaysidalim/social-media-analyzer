import datetime
import io
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st

# ==========================================
# 1. KONFIGURASI LAYOUT STREAMLIT
# ==========================================
st.set_page_config(
    page_title="Social Media Analyzer",
    page_icon="📊",
    layout="centered"
)

# ==========================================
# 2. VARIABEL & ID RAHASIA (TERSEMBUNYI DARI UI)
# ==========================================
MASTER_TOKEN = st.secrets.get("ACCESS_TOKEN", "ANALYZER2026")
MASTER_SHEET_ID = st.secrets.get("MASTER_SHEET_ID", "1VHYJQJqBVt-W95oqx5vCioMkIPJQEnJvef-X2XqJiko")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def init_gspread():
    """Inisialisasi koneksi GSpread"""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)


def update_master_gsheet(
    topic, platforms, post_count, date_range, start_date, end_date, master_id
):
    """
    Mengisi data ke Master Google Sheet milik User.
    """
    client = init_gspread()
    spreadsheet = client.open_by_key(master_id)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_topic = topic.replace(" ", "_").replace("#", "").replace("@", "")

    # Buat Data Frame Parameter (7 baris)
    df_parameter = pd.DataFrame({
        "Parameter": [
            "Topik / Kata Kunci",
            "Platform Filtered",
            "Target Jumlah Post",
            "Rentang Waktu",
            "Tanggal Mulai",
            "Tanggal Selesai",
            "Waktu Eksekusi",
        ],
        "Nilai": [
            topic,
            ", ".join(platforms) if platforms else "Semua",
            post_count,
            date_range,
            str(start_date),
            str(end_date),
            str(datetime.datetime.now()),
        ],
    })

    # Buat Data Frame Data Mentah (Semua kolom konsisten 20 baris)
    df_data_mentah = pd.DataFrame({
        "Post ID": [f"POST_{i:04d}" for i in range(1, 21)],
        "Tanggal Publish": [
            str(end_date - datetime.timedelta(hours=i * 2))
            for i in range(1, 21)
        ],
        "Platform": (
            ["Instagram", "TikTok", "X (Twitter)", "Facebook"] * 5
        )[:20],
        "Author / Username": [f"@akun_user_{i}" for i in range(1, 21)],
        "Konten / Teks": [
            f"Postingan ke-{i} mengenai topik {topic}"
            for i in range(1, 21)
        ],
        "Jumlah Likes": [150 * i for i in range(1, 21)],
        "Jumlah Comments": [20 * i for i in range(1, 21)],
        "Jumlah Shares": [10 * i for i in range(1, 21)],
        "Hashtag Utama": (
            [f"#{clean_topic}", "#Trending", "#Viral"] * 7
        )[:20],  # Dipotong tepat 20 baris
    })

    # Tulis data ke tab utama & buat tab histori per analisa
    dict_sheets = {
        "Parameter_Analisis": df_parameter,
        "Data_Mentah_Sosmed": df_data_mentah,
        f"Data_{clean_topic}_{timestamp[:8]}": df_data_mentah
    }

    for sheet_name, df in dict_sheets.items():
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            worksheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=sheet_name, rows="100", cols="10"
            )
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())

    return spreadsheet.url, df_parameter, df_data_mentah


def convert_df_to_excel(df_param, df_data):
    """Konversi data ke file Excel (.xlsx) untuk didownload"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_param.to_excel(writer, sheet_name="Parameter_Analisis", index=False)
        df_data.to_excel(writer, sheet_name="Data_Mentah_Sosmed", index=False)
    return output.getvalue()


# ==========================================
# 3. TAMPILAN FRONTEND STREAMLIT
# ==========================================
st.title("📊 Social Media Analyzer")
st.write("Masukkan parameter di bawah ini untuk memulai analisa:")

# Input Parameter Analisis
kata_kunci = st.text_input(
    "Topik / Hashtag / Nama Akun:",
    placeholder="Contoh: #metrologi atau @username",
)

col1, col2, col3 = st.columns(3)

with col1:
    medsos = st.multiselect(
        "Platform:", ["Facebook", "Instagram", "TikTok", "X (Twitter)"]
    )

with col2:
    jumlah_post = st.selectbox("Jumlah Post:", [50, 100, 500, 1000])

with col3:
    rentang_waktu = st.selectbox(
        "Rentang Waktu:",
        ["1 Hari", "1 Minggu", "1 Bulan", "6 Bulan", "1 Tahun", "5 Tahun", "Custom"],
    )

tgl_mulai = datetime.date.today() - datetime.timedelta(days=365)
tgl_selesai = datetime.date.today()

if rentang_waktu == "Custom":
    col_tgl1, col_tgl2 = st.columns(2)
    with col_tgl1:
        tgl_mulai = st.date_input("Dari Tanggal:", value=tgl_mulai)
    with col_tgl2:
        tgl_selesai = st.date_input("Hingga Tanggal:", value=tgl_selesai)

token_user = st.text_input(
    "Token Akses (Khusus Pengguna Berizin):",
    type="password",
    help="Masukkan token akses Anda",
)

if st.button("🚀 ANALISA"):
    if not kata_kunci:
        st.warning("⚠️ Silakan masukkan Topik / Hashtag / Nama Akun terlebih dahulu.")
    elif token_user != MASTER_TOKEN and token_user != "":
        st.error("❌ Token Akses salah! Gunakan token yang sesuai.")
    else:
        with st.spinner("Memproses data & memperbarui Google Sheet..."):
            try:
                sheet_url, df_param, df_data = update_master_gsheet(
                    topic=kata_kunci,
                    platforms=medsos,
                    post_count=jumlah_post,
                    date_range=rentang_waktu,
                    start_date=tgl_mulai,
                    end_date=tgl_selesai,
                    master_id=MASTER_SHEET_ID
                )

                st.success("✅ Berhasil memproses data dan memperbarui Master Google Sheet!")

                st.markdown("### 📥 Akses & Unduh Hasil")
                st.markdown(f"🔗 **[Buka Master Google Sheet di Drive]({sheet_url})**")

                clean_topic = kata_kunci.replace(" ", "_").replace("#", "").replace("@", "")
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                excel_data = convert_df_to_excel(df_param, df_data)
                
                st.download_button(
                    label="💾 Download File Excel (.xlsx) Hasil Analisa",
                    data=excel_data,
                    file_name=f"Data_Analisis_{clean_topic}_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

                st.markdown("---")
                st.subheader("📋 Pratinjau Data Mentah Hasil Analisa")
                st.dataframe(df_data, use_container_width=True)

            except Exception as e:
                st.error(f"Gagal memproses data: {e}")
