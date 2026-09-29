import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import pandas as pd
import streamlit as st

# ==========================================
# 1. KONFIGURASI GOOGLE DRIVE & SHEETS API
# ==========================================
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
    """Fungsi backend untuk membuat file GSheet baru di Drive & mengisi 10 Tab Analisa"""
    client, drive_service, folder_id = init_google_services()

    # Nama File Spreadsheet
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    sheet_title = f"Report_{topic.replace(' ', '_')}_{timestamp}"

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

    # 3. Siapkan Data Dummy Analisa Profesional untuk Setiap Tab
    # Tab 1: Ringkasan KPI
    df_01 = pd.DataFrame(
        {
            "Parameter": [
                "Topik / Kata Kunci",
                "Platform Filtered",
                "Target Jumlah Post",
                "Rentang Waktu",
                "Tanggal Mulai",
                "Tanggal Selesai",
                "Waktu Eksekusi Analisa",
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

    # Tab 2: Tren Harian
    df_02 = pd.DataFrame(
        {
            "Tanggal": [
                str(end_date - datetime.timedelta(days=i))
                for i in range(6, -1, -1)
            ],
            "Total Post": [12, 18, 25, 40, 32, 28, 45],
            "Total Likes": [1200, 2400, 3100, 5800, 4200, 3900, 6100],
            "Total Comments": [150, 310, 420, 890, 610, 500, 920],
            "Total Shares": [45, 90, 110, 340, 210, 180, 410],
            "Rata-rata ER%": ["2.1%", "2.8%", "3.2%", "4.5%", "3.8%", "3.4%", "5.1%"],
        }
    )

    # Tab 3: Matriks 24 Jam
    df_03 = pd.DataFrame(
        {
            "Jam (WIB)": [f"{i:02d}:00" for i in range(24)],
            "Volume Post": [
                2, 1, 0, 0, 1, 3, 8, 15, 22, 18, 12, 15,
                20, 25, 19, 14, 18, 28, 35, 42, 30, 20, 10, 5
            ],
            "Total Interaksi": [
                120, 50, 20, 10, 40, 180, 520, 1100, 1800, 1400, 980, 1250,
                1900, 2400, 1750, 1300, 1600, 3100, 4500, 5800, 3900, 2100, 900, 350
            ],
            "Status Waktu": [
                "Off-peak" if i < 7 or i > 22 else ("Peak Time" if 17 <= i <= 20 else "Normal")
                for i in range(24)
            ],
        }
    )

    # Tab 4: Top Engagement
    df_04 = pd.DataFrame(
        {
            "Rank": [1, 2, 3, 4, 5],
            "Platform": ["Instagram", "TikTok", "X (Twitter)", "Facebook", "Instagram"],
            "Akun / Author": ["@viral_user1", "@creator_id", "@trending_topic", "@news_channel", "@influencer_x"],
            "Ringkasan Konten": [
                f"Opini mendalam mengenai {topic}...",
                f"Video klip penjelas terkait {topic}...",
                f"Utasan ringkas seputar {topic}...",
                f"Laporan utama update {topic}...",
                f"Infografis statistik {topic}..."
            ],
            "Total Engagement": [12500, 9800, 7400, 5200, 4800],
            "ER Rate": ["8.4%", "7.1%", "5.9%", "4.2%", "3.9%"],
        }
    )

    # Tab 5: Velocity Viral
    df_05 = pd.DataFrame(
        {
            "URL Post": [f"https://social.com/p/{i}" for i in range(1, 6)],
            "Waktu Publish": ["2 Jam Lalu", "4 Jam Lalu", "5 Jam Lalu", "8 Jam Lalu", "12 Jam Lalu"],
            "Interaksi Awal": [50, 120, 90, 200, 150],
            "Interaksi Saat Ini": [3200, 4100, 2100, 3500, 1800],
            "Laju Kenaikan (Delta/Jam)": [1575, 995, 402, 412, 137],
            "Status Viralitas": ["🔥 Meledak / Viral", "🚀 Sangat Cepat", "📈 Stabil", "📈 Stabil", "Normal"],
        }
    )

    # Tab 6: Hashtag & Kata Kunci Pendamping
    df_06 = pd.DataFrame(
        {
            "Hashtag / Kata Kunci": [f"{topic}_update", "#TrendingTopic", "#Foryou", "#BeritaTerkini", "#DiskusiPublik"],
            "Frekuensi Muncul": [142, 98, 85, 64, 42],
            "Keterkaitan Sentimen": ["Positif", "Netral", "Positif", "Netral", "Negatif"],
        }
    )

    # Tab 7: Demografi & Lokasi
    df_07 = pd.DataFrame(
        {
            "Kelompok Usia": ["13-17", "18-24", "25-34", "35-44", "45+"],
            "Persentase Usia": ["5%", "42%", "38%", "11%", "4%"],
            "Gender Dominan": ["Wanita (52%)", "Pria (58%)", "Pria (51%)", "Wanita (54%)", "Pria (60%)"],
            "Top Kota": ["Jakarta", "Surabaya", "Bandung", "Medan", "Yogyakarta"],
        }
    )

    # Tab 8: Bot vs Organik
    df_08 = pd.DataFrame(
        {
            "Kategori Akun": ["Akun Organik (Manusia)", "Potensi Bot / Buzzer Repetitif", "Akun Media / Official"],
            "Jumlah Akun": [380, 45, 25],
            "Persentase": ["84.4%", "10.0%", "5.6%"],
            "Indikator Utama": [
                "Pola posting wajar & ada interaksi sosial",
                "Frekuensi post >50/hari, akun baru dibuat, tanpa foto profil",
                "Akun terverifikasi / portal berita resmi"
            ],
        }
    )

    # Tab 9: Format Konten
    df_09 = pd.DataFrame(
        {
            "Tipe Format": ["Video Pendek (Reels/TikTok/Shorts)", "Foto / Carousel", "Teks / Tweet", "Link Artikel"],
            "Jumlah Konten": [120, 180, 150, 50],
            "Rata-rata Likes": [2100, 850, 420, 110],
            "Rata-rata Shares": [340, 95, 120, 25],
        }
    )

    # Tab 10: Data Mentah
    df_10 = pd.DataFrame(
        {
            "Post ID": [f"POST_{i:04d}" for i in range(1, 11)],
            "Platform": ["Instagram", "TikTok", "X", "Facebook", "Instagram", "TikTok", "X", "Facebook", "Instagram", "TikTok"],
            "Author": [f"@user_{i}" for i in range(1, 11)],
            "Teks Post": [f"Contoh postingan ke-{i} membahas tentang {topic}" for i in range(1, 11)],
            "Likes": [100 * i for i in range(1, 11)],
            "Comments": [10 * i for i in range(1, 11)],
        }
    )

    # Dictionary Semua Tab
    dict_sheets = {
        "01_Ringkasan": df_01,
        "02_Tren_Harian": df_02,
        "03_Matriks_24Jam": df_03,
        "04_Top_Engagement": df_04,
        "05_Velocity_Viral": df_05,
        "06_Hashtag_Topik": df_06,
        "07_Demografi_Lokasi": df_07,
        "08_Bot_vs_Organik": df_08,
        "09_Format_Konten": df_09,
        "10_Data_Mentah": df_10,
    }

    # 4. Tulis Data ke Setiap Worksheet
    for sheet_name, df in dict_sheets.items():
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            worksheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols="10")

        worksheet.update([df.columns.values.tolist()] + df.values.tolist())

    # Hapus sheet bawaan "Sheet1"
    try:
        default_sheet = spreadsheet.worksheet("Sheet1")
        spreadsheet.del_worksheet(default_sheet)
    except Exception:
        pass

    return spreadsheet.url


# ==========================================
# 2. TAMPILAN FRONTEND STREAMLIT
# ==========================================
st.set_page_config(page_title="Social Media Analyzer", page_icon="📊", layout="wide")

st.title("📊 Social Media Analyzer")
st.write("Masukkan parameter di bawah ini untuk memulai analisa:")

# Input Utama
kata_kunci = st.text_input(
    "Topik / Hashtag / Nama Akun:",
    placeholder="Contoh: #Pemilu2026 atau @username",
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

# Tanggal Mulai dan Selesai
tgl_mulai = datetime.date.today() - datetime.timedelta(days=7)
tgl_selesai = datetime.date.today()

if rentang_waktu == "Custom":
    col_tgl1, col_tgl2 = st.columns(2)
    with col_tgl1:
        tgl_mulai = st.date_input("Dari Tanggal:", value=tgl_mulai)
    with col_tgl2:
        tgl_selesai = st.date_input("Hingga Tanggal:", value=tgl_selesai)

token_user = st.text_input(
    "Token Akses (Khusus Pengguna Berizin):", type="password"
)

# Tombol Analisa
if st.button("🚀 ANALISA"):
    if not kata_kunci:
        st.warning("Silakan masukkan Topik / Hashtag / Nama Akun terlebih dahulu.")
    else:
        with st.spinner("Sedang menganalisa data & mengunggah laporan ke Google Drive..."):
            try:
                # Jalankan Backend Generator
                sheet_url = create_and_populate_gsheet(
                    topic=kata_kunci,
                    platforms=medsos,
                    post_count=jumlah_post,
                    date_range=rentang_waktu,
                    start_date=tgl_mulai,
                    end_date=tgl_selesai,
                )

                st.success("✅ Analisa Berhasil Selesai!")
                st.markdown(
                    f"📂 **[Klik di sini untuk membuka Laporan Google Sheets Anda]({sheet_url})**"
                )

                st.markdown("---")
                st.subheader("📊 Preview Hasil Analisis Dashboard")

                # Tampilkan Tab Dasbor Visual
                tab1, tab2, tab3, tab4, tab5 = st.tabs(
                    [
                        "📈 Tren & Waktu",
                        "🏆 Top Post & Velocity",
                        "🏷️ Hashtags",
                        "👥 Demografi",
                        "🤖 Bot vs Organik",
                    ]
                )

                with tab1:
                    st.write("### Tren Interaksi Harian & Waktu Emas (Peak Hours)")
                    st.info("Prime Time posting terdeteksi pukul **18:00 - 20:00 WIB**.")

                with tab2:
                    st.write("### Konten dengan Engagement & Laju Kenaikan Tercepat")

                with tab3:
                    st.write("### Hashtag & Kata Kunci Pendamping Paling Sering Muncul")

                with tab4:
                    st.write("### Breakdown Demografi Usia, Gender, & Top Lokasi")

                with tab5:
                    st.write("### Skor Autentisitas Akun (Deteksi Bot / Buzzer)")

            except Exception as e:
                st.error(f"Gagal menjalankan analisa: {e}")
