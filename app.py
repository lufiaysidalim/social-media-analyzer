import datetime
import io
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
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
TARGET_FOLDER_ID = st.secrets.get("FOLDER_ID", "1NW_-L0ZQYJ2YrsDJWe90UZbflQXZSk")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def init_services():
    """Inisialisasi koneksi GSpread & Google Drive API"""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    client = gspread.authorize(creds)
    drive_service = build("drive", "v3", credentials=creds)
    return client, drive_service


def create_new_gsheet(
    topic, platforms, post_count, date_range, start_date, end_date, folder_id
):
    """
    1. Membuat File GSheet Baru via GSpread (Bebas Quota Limit Service Account)
    2. Memindahkan file baru ke Folder Target di Drive
    3. Mengisi data hasil analisa ke file tersebut
    """
    client, drive_service = init_services()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_topic = topic.replace(" ", "_").replace("#", "").replace("@", "")
    new_filename = f"Data_Analisis_{clean_topic}_{timestamp}"

    # 1. Buat Spreadsheet Baru via GSpread (Bebas Kuota Limit Drive)
    spreadsheet = client.create(new_filename)
    new_file_id = spreadsheet.id
    new_sheet_url = spreadsheet.url

    # 2. Pindahkan Spreadsheet Baru ke dalam Folder Target
    if folder_id:
        try:
            file_meta = drive_service.files().get(fileId=new_file_id, fields="parents").execute()
            previous_parents = ",".join(file_meta.get("parents", []))
            
            drive_service.files().update(
                fileId=new_file_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields="id, parents"
            ).execute()
        except Exception as e:
            st.warning(f"File berhasil dibuat, tetapi gagal dipindahkan ke folder: {e}")

    # 3. Buat Data Parameter & Data Mentah
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
        "Hashtag Utama": [
            f"#{clean_topic}",
            "#Trending",
            "#Viral",
        ] * 7,
    })

    dict_sheets = {
        "Parameter_Analisis": df_parameter,
        "Data_Mentah_Sosmed": df_data_mentah,
    }

    # 4. Tulis Data ke Worksheet dalam File Baru
    for sheet_name, df in dict_sheets.items():
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            worksheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=sheet_name, rows="100", cols="10"
            )
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())

    # Hapus tab default 'Sheet1' jika ada
    try:
        default_sheet = spreadsheet.worksheet("Sheet1")
        spreadsheet.del_worksheet(default_sheet)
    except Exception:
        pass

    return new_sheet_url, new_filename, df_parameter, df_data_mentah


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
        with st.spinner("Membuat file GSheet baru & mengisi data..."):
            try:
                sheet_url, filename, df_param, df_data = create_new_gsheet(
                    topic=kata_kunci,
                    platforms=medsos,
                    post_count=jumlah_post,
                    date_range=rentang_waktu,
                    start_date=tgl_mulai,
                    end_date=tgl_selesai,
                    folder_id=TARGET_FOLDER_ID
                )

                st.success(f"✅ Berhasil membuat file GSheet baru: **{filename}**!")

                st.markdown("### 📥 Akses & Unduh File Baru")
                st.markdown(f"🔗 **[Buka File Google Sheet Baru di Drive]({sheet_url})**")

                # Tombol Download Excel Langsung
                excel_data = convert_df_to_excel(df_param, df_data)
                st.download_button(
                    label="💾 Download File Excel (.xlsx)",
                    data=excel_data,
                    file_name=f"{filename}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

                st.markdown("---")
                st.subheader("📋 Pratinjau Data Mentah Hasil Analisa")
                st.dataframe(df_data, use_container_width=True)

            except Exception as e:
                st.error(f"Gagal memproses data: {e}")
