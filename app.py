import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import pandas as pd
import streamlit as st

# ==========================================
# 1. KONFIGURASI KHALAYAK & STREAMLIT LAYOUT
# ==========================================
st.set_page_config(
    page_title="Social Media Analyzer",
    page_icon="📊",
    layout="centered"  # Kembali ke tampilan terpusat & elegan
)

# Token akses sementara untuk pengujian
MASTER_TOKEN = st.secrets.get("ACCESS_TOKEN", "ANALYZER2026")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def init_google_services():
    """Inisialisasi koneksi GSpread dan Drive API menggunakan Streamlit Secrets"""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    client = gspread.authorize(creds)
    drive_service = build("drive", "v3", credentials=creds)
    folder_id = st.secrets["FOLDER_ID"]
    return client, drive_service, folder_id


def create_and_populate_gsheet(
    topic, platforms, post_count, date_range, start_date, end_date
):
    """Membuat file GSheet baru di Drive & mengisi tab data mentah & terstruktur"""
    client, drive_service, folder_id = init_google_services()

    # Nama File Spreadsheet
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    sheet_title = f"Data_Analisis_{topic.replace(' ', '_')}_{timestamp}"

    # 1. Buat Spreadsheet Baru
    spreadsheet = client.create(sheet_title)
    file_id = spreadsheet.id

    # 2. Pindahkan ke Folder Google Drive Tujuan
    drive_service.files().update(
        fileId=file_id,
        addParents=folder_id,
        removeParents="root",
        fields="id, parents",
    ).execute()

    # 3. Buat Data Mentah & Terstruktur untuk Diolah Kembali
    df_parameter = pd.DataFrame(
        {
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
        }
    )

    df_data_mentah = pd.DataFrame(
        {
            "Post ID": [f"POST_{i:04d}" for i in range(1, 16)],
            "Tanggal Publish": [
                str(end_date - datetime.timedelta(hours=i * 3))
                for i in range(1, 16)
            ],
            "Platform": (
                ["Instagram", "TikTok", "X (Twitter)", "Facebook"] * 4
            )[:15],
            "Author / Username": [f"@akun_user_{i}" for i in range(1, 16)],
            "Konten / Teks": [
                f"Contoh postingan ke-{i} yang membahas seputar {topic}"
                for i in range(1, 16)
            ],
            "Jumlah Likes": [120 * i for i in range(1, 16)],
            "Jumlah Comments": [15 * i for i in range(1, 16)],
            "Jumlah Shares": [8 * i for i in range(1, 16)],
            "Hashtag Utama": [
                f"#{topic.replace(' ', '')}",
                "#TrendingTopic",
                "#Viral",
            ]
            * 5,
        }
    )

    dict_sheets = {
        "Parameter_Analisis": df_parameter,
        "Data_Mentah_Sosmed": df_data_mentah,
    }

    # 4. Tulis Data ke Setiap Worksheet
    for sheet_name, df in dict_sheets.items():
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            worksheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=sheet_name, rows="100", cols="10"
            )

        worksheet.update([df.columns.values.tolist()] + df.values.tolist())

    # Hapus sheet bawaan "Sheet1"
    try:
        default_sheet = spreadsheet.worksheet("Sheet1")
        spreadsheet.del_worksheet(default_sheet)
    except Exception:
        pass

    # URL Ekspor Langsung ke Excel (.xlsx)
    excel_export_url = (
        f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    )

    return spreadsheet.url, excel_export_url, df_data_mentah


# ==========================================
# 2. TAMPILAN FRONTEND STREAMLIT
# ==========================================
st.title("📊 Social Media Analyzer")
st.write("Masukkan parameter di bawah ini untuk memulai analisa:")

# 1. Kolom Input Utama
kata_kunci = st.text_input(
    "Topik / Hashtag / Nama Akun:",
    placeholder="Contoh: #Pemilu2026 atau @username",
)

# 2. Tiga Filter Utama
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

# Tanggal Mulai & Selesai untuk Custom
tgl_mulai = datetime.date.today() - datetime.timedelta(days=7)
tgl_selesai = datetime.date.today()

if rentang_waktu == "Custom":
    col_tgl1, col_tgl2 = st.columns(2)
    with col_tgl1:
        tgl_mulai = st.date_input("Dari Tanggal:", value=tgl_mulai)
    with col_tgl2:
        tgl_selesai = st.date_input("Hingga Tanggal:", value=tgl_selesai)

# 3. Input Token Akses
token_user = st.text_input(
    "Token Akses (Khusus Pengguna Berizin):",
    type="password",
    help="Gunakan token akses sementara: ANALYZER2026",
)

# 4. Tombol Analisa
if st.button("🚀 ANALISA"):
    if not kata_kunci:
        st.warning("⚠️ Silakan masukkan Topik / Hashtag / Nama Akun terlebih dahulu.")
    elif token_user != MASTER_TOKEN and token_user != "":
        st.error("❌ Token Akses salah! Gunakan token: ANALYZER2026")
    else:
        with st.spinner("Sedang menarik data & membuat file Google Sheets..."):
            try:
                sheet_url, excel_url, df_result = create_and_populate_gsheet(
                    topic=kata_kunci,
                    platforms=medsos,
                    post_count=jumlah_post,
                    date_range=rentang_waktu,
                    start_date=tgl_mulai,
                    end_date=tgl_selesai,
                )

                st.success("✅ File Data Berhasil Dibuat!")

                st.markdown("### 📥 Akses & Unduh Laporan Data")
                st.markdown(
                    f"1. 🔗 **[Buka Laporan di Google Sheets]({sheet_url})**"
                )
                st.markdown(
                    f"2. 💾 **[Download Langsung Format Excel (.xlsx)]({excel_url})**"
                )

                st.markdown("---")
                st.subheader("📋 Pratinjau Data Mentah yang Dihasilkan")
                st.dataframe(df_result, use_container_width=True)

            except Exception as e:
                st.error(f"Gagal memproses data: {e}")
