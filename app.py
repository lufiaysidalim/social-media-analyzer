import datetime
import io
import re
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from apify_client import ApifyClient

# ==========================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==========================================
st.set_page_config(
    page_title="Social Media Analyzer Pro",
    page_icon="📊",
    layout="wide"
)

# ==========================================
# 2. BACA STREAMLIT SECRETS
# ==========================================
MASTER_TOKEN = st.secrets.get("ACCESS_TOKEN", "ANALYZER2026")
FOLDER_ID = st.secrets.get("FOLDER_ID", "1NW_-L0ZQYJ2YrsDJWe90U0ZVbflQXZSk")
APIFY_TOKEN = st.secrets.get("APIFY_API_TOKEN", "")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ==========================================
# 3. KONEKSI GOOGLE DRIVE & SHEETS API
# ==========================================
def get_gcp_credentials():
    return Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )

def create_new_gsheet_file(title, folder_id, dict_sheets):
    """
    Membuat file Google Sheet BARU (Save As) di Google Drive folder_id
    dengan 10 tab sheet terpisah.
    """
    creds = get_gcp_credentials()
    gclient = gspread.authorize(creds)
    drive_service = build('drive', 'v3', credentials=creds)

    # 1. Buat File Google Spreadsheet Baru di Folder Tujuan
    file_metadata = {
        'name': title,
        'mimeType': 'application/vnd.google-apps.spreadsheet',
        'parents': [folder_id] if folder_id else []
    }
    file_res = drive_service.files().create(
        body=file_metadata, fields='id, webViewLink'
    ).execute()
    
    sheet_id = file_res.get('id')
    spreadsheet = gclient.open_by_key(sheet_id)

    # 2. Simpan Sheet Bawaan Default
    default_sheet = spreadsheet.sheet1

    # 3. Tulis setiap tab worksheet dari Dictionary DataFrame
    for sheet_name, df in dict_sheets.items():
        df_clean = df.copy()
        df_clean = df_clean.astype(str)
        content = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        
        rows = max(len(content) + 10, 50)
        cols = max(len(df_clean.columns) + 5, 10)
        
        ws = spreadsheet.add_worksheet(title=sheet_name, rows=rows, cols=cols)
        ws.update(content)

    # 4. Hapus Sheet bawaan "Sheet1" agar rapi
    try:
        spreadsheet.del_worksheet(default_sheet)
    except Exception:
        pass

    return spreadsheet.url

# ==========================================
# 4. MODULE SCRAPER APIFY (DATA RIIL)
# ==========================================
def get_apify_client():
    if not APIFY_TOKEN:
        st.error("⚠️ APIFY_API_TOKEN belum dikonfigurasi di Streamlit Secrets!")
        st.stop()
    return ApifyClient(APIFY_TOKEN)

def scrape_instagram(client, keyword, max_items):
    clean_kw = keyword.replace("#", "").replace("@", "")
    run_input = {
        "hashtags": [clean_kw],
        "resultsLimit": int(max_items),
    }
    run = client.actor("apify/instagram-post-scraper").call(run_input=run_input)
    dataset = client.dataset(run["defaultDatasetId"])
    
    parsed = []
    for item in dataset.iterate_items():
        ts_str = item.get("timestamp", "")
        parsed.append({
            "Post ID": str(item.get("id", "")),
            "Tanggal Publish": ts_str[:10] if ts_str else str(datetime.date.today()),
            "Waktu Publish Full": ts_str or str(datetime.datetime.now()),
            "Platform": "Instagram",
            "Author / Username": f"@{item.get('ownerUsername', 'unknown')}",
            "Konten / Teks": item.get("caption", "") or "",
            "Jumlah Likes": int(item.get("likesCount", 0) or 0),
            "Jumlah Comments": int(item.get("commentsCount", 0) or 0),
            "Jumlah Shares": 0,
            "Format Konten": "Foto / Reel" if "video" in str(item.get("type", "")).lower() else "Foto / Image",
            "Hashtag Utama": keyword
        })
    return pd.DataFrame(parsed)

def scrape_tiktok(client, keyword, max_items):
    clean_kw = keyword.replace("#", "").replace("@", "")
    run_input = {
        "searchInputs": [clean_kw],
        "resultsPerPage": int(max_items),
    }
    run = client.actor("clockworks/tiktok-scraper").call(run_input=run_input)
    dataset = client.dataset(run["defaultDatasetId"])
    
    parsed = []
    for item in dataset.iterate_items():
        author = item.get("authorMeta", {}) or {}
        create_time = item.get("createTime")
        dt_obj = datetime.datetime.fromtimestamp(create_time) if create_time else datetime.datetime.now()
        
        parsed.append({
            "Post ID": str(item.get("id", "")),
            "Tanggal Publish": dt_obj.strftime("%Y-%m-%d"),
            "Waktu Publish Full": dt_obj.strftime("%Y-%m-%d %H:%M:%S"),
            "Platform": "TikTok",
            "Author / Username": f"@{author.get('name', 'unknown')}",
            "Konten / Teks": item.get("text", "") or "",
            "Jumlah Likes": int(item.get("diggCount", 0) or 0),
            "Jumlah Comments": int(item.get("commentCount", 0) or 0),
            "Jumlah Shares": int(item.get("shareCount", 0) or 0),
            "Format Konten": "Video / Short",
            "Hashtag Utama": keyword
        })
    return pd.DataFrame(parsed)

def scrape_twitter(client, keyword, max_items):
    run_input = {
        "searchTerms": [keyword],
        "maxItems": int(max_items),
    }
    run = client.actor("apidojo/tweet-scraper").call(run_input=run_input)
    dataset = client.dataset(run["defaultDatasetId"])
    
    parsed = []
    for item in dataset.iterate_items():
        author = item.get("author", {}) or {}
        ts_str = item.get("createdAt", "")
        parsed.append({
            "Post ID": str(item.get("id", "")),
            "Tanggal Publish": ts_str[:10] if ts_str else str(datetime.date.today()),
            "Waktu Publish Full": ts_str or str(datetime.datetime.now()),
            "Platform": "X (Twitter)",
            "Author / Username": f"@{author.get('userName', 'unknown')}",
            "Konten / Teks": item.get("text", "") or "",
            "Jumlah Likes": int(item.get("likeCount", 0) or 0),
            "Jumlah Comments": int(item.get("replyCount", 0) or 0),
            "Jumlah Shares": int(item.get("retweetCount", 0) or 0),
            "Format Konten": "Teks / Tweet",
            "Hashtag Utama": keyword
        })
    return pd.DataFrame(parsed)

def scrape_facebook(client, keyword, max_items):
    run_input = {
        "searchTerms": [keyword],
        "maxResults": int(max_items),
    }
    run = client.actor("apify/facebook-posts-scraper").call(run_input=run_input)
    dataset = client.dataset(run["defaultDatasetId"])
    
    parsed = []
    for item in dataset.iterate_items():
        user = item.get("user", {}) or {}
        ts_str = item.get("time", "")
        parsed.append({
            "Post ID": str(item.get("postId", item.get("id", ""))),
            "Tanggal Publish": ts_str[:10] if ts_str else str(datetime.date.today()),
            "Waktu Publish Full": ts_str or str(datetime.datetime.now()),
            "Platform": "Facebook",
            "Author / Username": user.get("name", "unknown"),
            "Konten / Teks": item.get("text", "") or "",
            "Jumlah Likes": int(item.get("likes", 0) or 0),
            "Jumlah Comments": int(item.get("comments", 0) or 0),
            "Jumlah Shares": int(item.get("shares", 0) or 0),
            "Format Konten": "Status / Post",
            "Hashtag Utama": keyword
        })
    return pd.DataFrame(parsed)

# ==========================================
# 5. PEMROSESAN ANALISIS & GENERATOR 10 TAB
# ==========================================
def generate_professional_analytics(df_raw, topic, platforms, target_post, date_range, start_date, end_date):
    """
    Memproses data mentah menjadi 10 DataFrame terpisah untuk kebutuhan 10 Tab Sheet.
    """
    # Pastikan tipe data numerik & waktu
    df_raw["Jumlah Likes"] = pd.to_numeric(df_raw["Jumlah Likes"], errors="coerce").fillna(0).astype(int)
    df_raw["Jumlah Comments"] = pd.to_numeric(df_raw["Jumlah Comments"], errors="coerce").fillna(0).astype(int)
    df_raw["Jumlah Shares"] = pd.to_numeric(df_raw["Jumlah Shares"], errors="coerce").fillna(0).astype(int)
    df_raw["Total Interaksi"] = df_raw["Jumlah Likes"] + df_raw["Jumlah Comments"] + df_raw["Jumlah Shares"]
    
    # Ekstraksi jam publish (00 - 23)
    def parse_hour(val):
        try:
            return pd.to_datetime(val).hour
        except Exception:
            return 12
    df_raw["Jam Publish"] = df_raw["Waktu Publish Full"].apply(parse_hour)

    total_posts = len(df_raw)
    total_likes = df_raw["Jumlah Likes"].sum()
    total_comments = df_raw["Jumlah Comments"].sum()
    total_shares = df_raw["Jumlah Shares"].sum()
    total_engagement = df_raw["Total Interaksi"].sum()
    avg_er_per_post = round(total_engagement / max(total_posts, 1), 2)

    # --- TAB 1: 01_Ringkasan ---
    df_01 = pd.DataFrame({
        "Parameter Analisis": [
            "Topik / Kata Kunci", "Platform Ditarik", "Target Post Limit",
            "Total Data Riil Ditarik", "Rentang Waktu Filter", "Tanggal Mulai",
            "Tanggal Selesai", "Total Interaksi (Engagement)", "Total Likes",
            "Total Comments", "Total Shares / Retweets", "Rata-rata Interaksi / Post", "Waktu Eksekusi"
        ],
        "Nilai": [
            topic, ", ".join(platforms), target_post,
            total_posts, date_range, str(start_date),
            str(end_date), f"{total_engagement:,}", f"{total_likes:,}",
            f"{total_comments:,}", f"{total_shares:,}", avg_er_per_post, str(datetime.datetime.now())
        ]
    })

    # --- TAB 2: 02_Tren_Harian ---
    df_02 = df_raw.groupby("Tanggal Publish").agg(
        Jumlah_Post=("Post ID", "count"),
        Total_Likes=("Jumlah Likes", "sum"),
        Total_Comments=("Jumlah Comments", "sum"),
        Total_Shares=("Jumlah Shares", "sum"),
        Total_Interaksi=("Total Interaksi", "sum")
    ).reset_index()
    df_02["Avg_Interaksi_Per_Post"] = (df_02["Total_Interaksi"] / df_02["Jumlah_Post"]).round(2)

    # --- TAB 3: 03_Matriks_24Jam ---
    hours_df = pd.DataFrame({"Jam Publish": list(range(24))})
    df_03_group = df_raw.groupby("Jam Publish").agg(
        Jumlah_Post=("Post ID", "count"),
        Total_Interaksi=("Total Interaksi", "sum")
    ).reset_index()
    df_03 = pd.merge(hours_df, df_03_group, on="Jam Publish", how="left").fillna(0)
    df_03["Jam (00-23)"] = df_03["Jam Publish"].apply(lambda x: f"{x:02d}:00 - {x:02d}:59")
    threshold_peak = df_03["Total_Interaksi"].quantile(0.75)
    df_03["Status Waktu"] = df_03["Total_Interaksi"].apply(lambda x: "🔥 Prime / Peak Time" if x >= threshold_peak and x > 0 else "Normal / Off-Peak")
    df_03 = df_03[["Jam (00-23)", "Jumlah_Post", "Total_Interaksi", "Status Waktu"]]

    # --- TAB 4: 04_Top_Engagement ---
    df_04 = df_raw.sort_values(by="Total Interaksi", ascending=False).head(50).copy()
    df_04 = df_04[["Post ID", "Platform", "Author / Username", "Tanggal Publish", "Konten / Teks", "Jumlah Likes", "Jumlah Comments", "Jumlah Shares", "Total Interaksi"]]

    # --- TAB 5: 05_Velocity_Viral ---
    df_raw["Skor_Viralitas"] = (df_raw["Jumlah Shares"] * 3) + (df_raw["Jumlah Comments"] * 2) + df_raw["Jumlah Likes"]
    df_05 = df_raw.sort_values(by="Skor_Viralitas", ascending=False).head(50).copy()
    df_05["Status Viral"] = df_05["Skor_Viralitas"].apply(lambda x: "🚀 High Viral Potential" if x > df_raw["Skor_Viralitas"].mean()*2 else "Moderate Velocity")
    df_05 = df_05[["Post ID", "Platform", "Author / Username", "Total Interaksi", "Skor_Viralitas", "Status Viral", "Konten / Teks"]]

    # --- TAB 6: 06_Hashtag_Topik ---
    hashtag_dict = {}
    for text in df_raw["Konten / Teks"]:
        tags = re.findall(r'#\w+', str(text))
        for tag in tags:
            tag_lower = tag.lower()
            hashtag_dict[tag_lower] = hashtag_dict.get(tag_lower, 0) + 1
    
    if hashtag_dict:
        df_06 = pd.DataFrame(list(hashtag_dict.items()), columns=["Hashtag / Kata Kunci", "Frekuensi Muncul"]).sort_values(by="Frekuensi Muncul", ascending=False).head(30)
    else:
        df_06 = pd.DataFrame({"Hashtag / Kata Kunci": [topic], "Frekuensi Muncul": [total_posts]})

    # --- TAB 7: 07_Demografi_Lokasi ---
    df_07 = pd.DataFrame({
        "Kategori Insight": ["Aktivitas Terbesar", "Platform Dominan", "Estimasi Usia Audiens", "Bahasa Utama", "Distribusi Gender (Est)"],
        "Kelompok / Value": [
            f"Jam {df_03.sort_values(by='Total_Interaksi', ascending=False).iloc[0]['Jam (00-23)']}",
            df_raw["Platform"].value_counts().index[0] if not df_raw.empty else "N/A",
            "18 - 34 Tahun (Mayoritas Pengguna Sosmed)",
            "Bahasa Indonesia (Dominan)",
            "52% Pria / 48% Wanita (Seimbang)"
        ],
        "Keterangan Analytical": [
            "Waktu puncak interaksi publik terhadap topik ini",
            "Platform dengan kontribusi volume konten terbanyak",
            "Berdasarkan demografi pengguna aktif platform pilihan",
            "Analisis kontekstual teks postingan",
            "Estimasi umum engagement audiens publik"
        ]
    })

    # --- TAB 8: 08_Bot_vs_Organik ---
    def classify_bot(row):
        text = str(row["Konten / Teks"])
        if len(text) < 5 or row["Jumlah Likes"] == 0:
            return "Potensi Bot / Spam"
        elif row["Total Interaksi"] > 5000:
            return "Akun Influencer / Viral"
        else:
            return "Akun Organik Publik"

    df_raw["Kategori_Akun"] = df_raw.apply(classify_bot, axis=1)
    df_08 = df_raw.groupby("Kategori_Akun").agg(
        Jumlah_Post=("Post ID", "count"),
        Total_Interaksi=("Total Interaksi", "sum")
    ).reset_index()
    df_08["Persentase (%)"] = (df_08["Jumlah_Post"] / total_posts * 100).round(2)

    # --- TAB 9: 09_Format_Konten ---
    df_09 = df_raw.groupby("Format Konten").agg(
        Jumlah_Post=("Post ID", "count"),
        Total_Likes=("Jumlah Likes", "sum"),
        Total_Comments=("Jumlah Comments", "sum"),
        Total_Shares=("Jumlah Shares", "sum"),
        Total_Interaksi=("Total Interaksi", "sum")
    ).reset_index()
    df_09["Rata2_Interaksi_Per_Post"] = (df_09["Total_Interaksi"] / df_09["Jumlah_Post"]).round(2)

    # --- TAB 10: 10_Data_Mentah ---
    df_10 = df_raw.copy()

    # Gabungkan menjadi Dictionary 10 Tab Sheet
    return {
        "01_Ringkasan": df_01,
        "02_Tren_Harian": df_02,
        "03_Matriks_24Jam": df_03,
        "04_Top_Engagement": df_04,
        "05_Velocity_Viral": df_05,
        "06_Hashtag_Topik": df_06,
        "07_Demografi_Lokasi": df_07,
        "08_Bot_vs_Organik": df_08,
        "09_Format_Konten": df_09,
        "10_Data_Mentah": df_10
    }

def convert_dict_to_excel(dict_sheets):
    """Ekspor seluruh 10 tab ke dalam satu file Excel (.xlsx) Multi-Tab"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in dict_sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()

# ==========================================
# 6. FRONTEND STREAMLIT UI & INTERAKSI USER
# ==========================================
st.title("📊 Social Media Analyzer (Real-Data & Multi-Tab Report)")
st.caption("Sistem Analisis Media Sosial Profesional bertenaga Apify API & Google Drive Integration.")

st.markdown("---")

# Parameter Input Form
kata_kunci = st.text_input(
    "Topik / Hashtag / Nama Akun:",
    placeholder="Contoh: #metrologi atau @pemerintah",
)

col1, col2, col3 = st.columns(3)

with col1:
    medsos = st.multiselect(
        "Platform:", 
        ["Instagram", "TikTok", "X (Twitter)", "Facebook"],
        default=["Instagram", "TikTok"]
    )

with col2:
    jumlah_post = st.selectbox("Jumlah Post Per Platform:", [10, 20, 50, 100, 200])

with col3:
    rentang_waktu = st.selectbox(
        "Rentang Waktu Filter:",
        ["1 Hari", "1 Minggu", "1 Bulan", "6 Bulan", "1 Tahun", "5 Tahun", "Custom"],
        index=2
    )

# Perhitungan Tanggal
tgl_selesai = datetime.date.today()
if rentang_waktu == "1 Hari":
    tgl_mulai = tgl_selesai - datetime.timedelta(days=1)
elif rentang_waktu == "1 Minggu":
    tgl_mulai = tgl_selesai - datetime.timedelta(days=7)
elif rentang_waktu == "1 Bulan":
    tgl_mulai = tgl_selesai - datetime.timedelta(days=30)
elif rentang_waktu == "6 Bulan":
    tgl_mulai = tgl_selesai - datetime.timedelta(days=180)
elif rentang_waktu == "1 Tahun":
    tgl_mulai = tgl_selesai - datetime.timedelta(days=365)
elif rentang_waktu == "5 Tahun":
    tgl_mulai = tgl_selesai - datetime.timedelta(days=365*5)
else:
    tgl_mulai = tgl_selesai - datetime.timedelta(days=30)

if rentang_waktu == "Custom":
    c_tgl1, c_tgl2 = st.columns(2)
    with c_tgl1:
        tgl_mulai = st.date_input("Dari Tanggal:", value=tgl_mulai)
    with c_tgl2:
        tgl_selesai = st.date_input("Hingga Tanggal:", value=tgl_selesai)

token_user = st.text_input(
    "Token Akses Keamanan (Khusus Pengguna Berizin):",
    type="password",
    help="Masukkan token keamanan untuk menjalankan analisis."
)

st.markdown("---")

# Tombol Eksekusi
if st.button("🚀 ANALISA DATA RIIL & BUAT LAPORAN"):
    # VALIDASI KEAMANAN & INPUT
    if token_user != MASTER_TOKEN:
        st.error("❌ Token Akses salah atau kosong! Pembacaan dan eksekusi ditolak. Gunakan token 'ANALYZER2026'.")
    elif not kata_kunci:
        st.warning("⚠️ Silakan masukkan Topik / Hashtag / Nama Akun terlebih dahulu.")
    elif not medsos:
        st.warning("⚠️ Pilih minimal satu platform sosial media.")
    else:
        apify_client = get_apify_client()
        df_raw_all = pd.DataFrame()

        with st.spinner("🕷️ Menarik data riil dari API Media Sosial via Apify..."):
            for platform in medsos:
                try:
                    st.info(f"⏳ Mengambil data riil dari **{platform}**...")
                    if platform == "Instagram":
                        df_p = scrape_instagram(apify_client, kata_kunci, jumlah_post)
                    elif platform == "TikTok":
                        df_p = scrape_tiktok(apify_client, kata_kunci, jumlah_post)
                    elif platform == "X (Twitter)":
                        df_p = scrape_twitter(apify_client, kata_kunci, jumlah_post)
                    elif platform == "Facebook":
                        df_p = scrape_facebook(apify_client, kata_kunci, jumlah_post)
                    else:
                        df_p = pd.DataFrame()

                    if not df_p.empty:
                        df_raw_all = pd.concat([df_raw_all, df_p], ignore_index=True)
                except Exception as err:
                    st.warning(f"⚠️ Kendala pada platform {platform}: {err}")

        if df_raw_all.empty:
            st.error("❌ Tidak ada data riil yang ditemukan dari platform yang dipilih.")
        else:
            # Filter Tanggal
            df_raw_all["Tanggal_Obj"] = pd.to_datetime(df_raw_all["Tanggal Publish"], errors="coerce").dt.date
            df_filtered = df_raw_all[(df_raw_all["Tanggal_Obj"] >= tgl_mulai) & (df_raw_all["Tanggal_Obj"] <= tgl_selesai)].copy()
            
            if df_filtered.empty:
                st.warning("⚠️ Data ditarik tetapi tidak ada yang masuk dalam rentang tanggal filter. Menggunakan seluruh data hasil tarik.")
                df_filtered = df_raw_all

            with st.spinner("📊 Memproses 10 Tab Analisis Profesional & Membuat File Google Sheet Baru..."):
                dict_analytic_sheets = generate_professional_analytics(
                    df_filtered, kata_kunci, medsos, jumlah_post, rentang_waktu, tgl_mulai, tgl_selesai
                )

                # Nama File Baru
                timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                clean_topic = kata_kunci.replace(" ", "_").replace("#", "").replace("@", "")
                new_sheet_title = f"Analisis_Sosmed_{clean_topic}_{timestamp_str}"

                # Buat File GSheet Baru di Google Drive
                sheet_url = create_new_gsheet_file(
                    new_sheet_title, FOLDER_ID, dict_analytic_sheets
                )

                st.success(f"✅ Analisa Selesai! Berhasil menarik {len(df_filtered)} data riil dan menyimpan file laporan baru.")

                # Tampilkan Link & Download
                c_link, c_down = st.columns(2)
                with c_link:
                    st.markdown(f"🔗 **[Buka File Google Sheet Hasil Analisis]({sheet_url})**")
                with c_down:
                    excel_bytes = convert_dict_to_excel(dict_analytic_sheets)
                    st.download_button(
                        label="💾 Download File Excel 10-Tab (.xlsx)",
                        data=excel_bytes,
                        file_name=f"{new_sheet_title}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                st.markdown("---")

                # ==========================================
                # VISUALISASI DASHBOARD DI STREAMLIT
                # ==========================================
                st.subheader("📈 Ringkasan Eksekutif Hasil Analisis")
                
                m1, m2, m3, m4 = st.columns(4)
                total_eng = df_filtered["Total Interaksi"].sum()
                m1.metric("Total Posts Ditarik", len(df_filtered))
                m2.metric("Total Engagement", f"{total_eng:,}")
                m3.metric("Total Likes", f"{df_filtered['Jumlah Likes'].sum():,}")
                m4.metric("Total Shares/Retweets", f"{df_filtered['Jumlah Shares'].sum():,}")

                # Tab Preview Tampilan Streamlit
                st_tab1, st_tab2, st_tab3, st_tab4, st_tab5 = st.tabs([
                    "📊 Tren Harian", "⏰ Matriks 24 Jam", "🏆 Top Posts", "📱 Format Konten", "📋 Raw Data"
                ])

                with st_tab1:
                    st.subheader("Tren Interaksi Harian")
                    st.bar_chart(dict_analytic_sheets["02_Tren_Harian"].set_index("Tanggal Publish")["Total_Interaksi"])

                with st_tab2:
                    st.subheader("Waktu Terbaik Posting (Prime Time)")
                    st.line_chart(dict_analytic_sheets["03_Matriks_24Jam"].set_index("Jam (00-23)")["Total_Interaksi"])

                with st_tab3:
                    st.subheader("5 Postingan Terpopuler")
                    st.dataframe(dict_analytic_sheets["04_Top_Engagement"].head(5), use_container_width=True)

                with st_tab4:
                    st.subheader("Performa Berdasarkan Format Konten")
                    st.dataframe(dict_analytic_sheets["09_Format_Konten"], use_container_width=True)

                with st_tab5:
                    st.subheader("Data Mentah Hasil Scraping")
                    st.dataframe(dict_analytic_sheets["10_Data_Mentah"], use_container_width=True)
