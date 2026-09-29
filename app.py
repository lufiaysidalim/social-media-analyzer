import streamlit as st
import pandas as pd
import plotly.express as px
from apify_client import ApifyClient
from datetime import datetime, timedelta, timezone
import io
import os
import time

# Import instagrapi dan exception handling-nya
from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired,
    PleaseWaitFewMinutes,
    LoginRequired,
    ClientError
)

# ==========================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==========================================
st.set_page_config(
    page_title="Social Media Analyzer Pro",
    page_icon="📊",
    layout="centered"
)

st.title("📊 Social Media Analyzer Pro")
st.caption("Sistem Analisis Media Sosial Profesional bertenaga instagrapi (Instagram) & Apify API (TikTok, X, FB).")

# ==========================================
# 2. FORM INPUT UTAMA
# ==========================================

keyword = st.text_input("Topik / Hashtag / Nama Akun:", value="viral")
st.info("💡 **Tips Input:** Gunakan `@` untuk Akun (contoh: @jokowi), `#` untuk Hashtag (contoh: #metrologi), atau ketik langsung untuk Topik (contoh: metrologi).")

col1, col2, col3, col4 = st.columns(4)

with col1:
    platforms = st.multiselect("Platform:", ["Facebook", "Instagram", "TikTok", "X(Twitter)"], default=["Instagram"])

with col2:
    max_items_options = [10, 20, 50, 100, 500, 1000, "-"]
    max_items_selection = st.selectbox("Tampilkan Top Postingan:", max_items_options, index=0)

with col3:
    filter_time_options = ["1 Hari", "1 Minggu", "1 Bulan", "3 Bulan", "6 Bulan", "1 Tahun", "5 Tahun", "Custom", "-"]
    filter_time = st.selectbox("Rentang Waktu:", filter_time_options, index=2)

with col4:
    raw_limit = st.number_input("Batas Tarik Raw Data:", min_value=10, max_value=5000000, value=500, step=50)

start_date, end_date = None, None
if filter_time == "Custom":
    col_date1, col_date2 = st.columns(2)
    with col_date1:
        start_date = st.date_input("Waktu Range Awal")
    with col_date2:
        end_date = st.date_input("Waktu Range Akhir")

program_token = st.text_input("Token Program:", type="password", placeholder="Masukkan token program...")
btn_analyze = st.button("ANALISA")


# ==========================================
# 3. KONFIGURASI INSTAGRAPI & SESI
# ==========================================

IG_USERNAME = "analisamediasosialmu"
IG_PASSWORD = "928272Mi@"
SESSION_FILE = "ig_session.json"

def get_instagrapi_client():
    """
    Inisialisasi instagrapi Client dengan Manajemen Sesi & Anti-Ban Delay.
    """
    cl = Client()
    # Menambahkan jeda acak 2-5 detik antar request untuk meniru perilaku manusia
    cl.delay_range = [2, 5]
    
    session_loaded = False
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(IG_USERNAME, IG_PASSWORD)
            session_loaded = True
        except Exception:
            session_loaded = False

    if not session_loaded:
        cl.login(IG_USERNAME, IG_PASSWORD)
        cl.dump_settings(SESSION_FILE)
        
    return cl


# ==========================================
# 4. FUNGSI BANTUAN & SCRAPER PER PLATFORM
# ==========================================

def get_dataset_id(run):
    if isinstance(run, dict):
        return run.get("defaultDatasetId")
    return getattr(run, "defaultDatasetId", getattr(run, "default_dataset_id", None))

def parse_timestamp(ts):
    if not ts or ts == "N/A":
        return datetime.now(timezone.utc)
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        try:
            if str(ts).isdigit():
                val = float(ts)
                if val > 1e12: # milidetik
                    val = val / 1000.0
                return datetime.fromtimestamp(val, tz=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)

def filter_by_time_range(df, filter_time, start_date=None, end_date=None):
    if df.empty or filter_time == "-":
        return df
    
    now = datetime.now(timezone.utc)
    df['ParsedTime'] = df['Timestamp'].apply(parse_timestamp)

    if filter_time == "1 Hari":
        limit_date = now - timedelta(days=1)
        filtered = df[df['ParsedTime'] >= limit_date]
    elif filter_time == "1 Minggu":
        limit_date = now - timedelta(weeks=1)
        filtered = df[df['ParsedTime'] >= limit_date]
    elif filter_time == "1 Bulan":
        limit_date = now - timedelta(days=30)
        filtered = df[df['ParsedTime'] >= limit_date]
    elif filter_time == "3 Bulan":
        limit_date = now - timedelta(days=90)
        filtered = df[df['ParsedTime'] >= limit_date]
    elif filter_time == "6 Bulan":
        limit_date = now - timedelta(days=180)
        filtered = df[df['ParsedTime'] >= limit_date]
    elif filter_time == "1 Tahun":
        limit_date = now - timedelta(days=365)
        filtered = df[df['ParsedTime'] >= limit_date]
    elif filter_time == "5 Tahun":
        limit_date = now - timedelta(days=365*5)
        filtered = df[df['ParsedTime'] >= limit_date]
    elif filter_time == "Custom" and start_date and end_date:
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        filtered = df[(df['ParsedTime'] >= start_dt) & (df['ParsedTime'] <= end_dt)]
    else:
        filtered = df

    return filtered.drop(columns=['ParsedTime'], errors='ignore')


def scrape_instagram_instagrapi(keyword, scrape_limit):
    """
    Penarikan data Instagram menggunakan instagrapi (bebas biaya Apify).
    """
    clean_kw = keyword.replace("#", "").replace("@", "").strip()
    results = []
    
    # Batasi jumlah scraping aman per panggilan (max 300-500) demi keamanan akun
    safe_limit = min(scrape_limit, 300)
    
    try:
        cl = get_instagrapi_client()
        medias = []
        
        # 1. Scraping Berdasarkan Username (@username)
        if keyword.startswith("@"):
            user_id = cl.user_id_from_username(clean_kw)
            medias = cl.user_medias(user_id, amount=safe_limit)
        # 2. Scraping Berdasarkan Hashtag/Topik (#hashtag)
        else:
            medias = cl.hashtag_medias_recent(clean_kw, amount=safe_limit)

        for item in medias:
            # Ambil nilai penonton/views jika media berbentuk Reel atau Video
            views = getattr(item, 'view_count', 0) or getattr(item, 'play_count', 0) or 0
            
            author_username = item.user.username if (item.user and hasattr(item.user, 'username')) else clean_kw
            
            results.append({
                "Platform": "Instagram",
                "Author": author_username,
                "Followers": "N/A",
                "Account_Created": "N/A", 
                "Content": item.caption_text or "",
                "Likes": item.like_count or 0,
                "Comments": item.comment_count or 0,
                "Shares/Views": views,
                "Url": f"https://www.instagram.com/p/{item.code}/",
                "Timestamp": item.taken_at.isoformat() if item.taken_at else str(datetime.now(timezone.utc))
            })

    except PleaseWaitFewMinutes:
        st.error("⚠️ **Instagram Rate Limit**: Instagram membatasi akses sementara. Silakan tunggu 5-10 menit sebelum mencoba kembali.")
    except ChallengeRequired:
        st.error("⚠️ **Verifikasi Diperlukan**: Instagram meminta verifikasi keamanan. Silakan buka aplikasi Instagram di ponsel dengan akun `@analisamediasosialmu` untuk menyetujui login.")
    except LoginRequired:
        # Hapus sesi usang jika login gagal dan minta login ulang pada run berikutnya
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        st.error("⚠️ **Sesi Login Kedaluwarsa**: Sesi direset. Silakan tekan tombol 'ANALISA' kembali.")
    except Exception as e:
        st.warning(f"Kendala pada platform Instagram (instagrapi): {str(e)}")

    return results

def scrape_tiktok(client, keyword, scrape_limit):
    results = []
    clean_kw = keyword.replace("#", "").replace("@", "").strip()
    try:
        if keyword.startswith("@"):
            run_input = {"profiles": [clean_kw], "resultsPerPage": scrape_limit}
        elif keyword.startswith("#"):
            run_input = {"hashtags": [clean_kw], "resultsPerPage": scrape_limit}
        else:
            run_input = {"searchQueries": [clean_kw], "resultsPerPage": scrape_limit}

        run = client.actor("clockworks/free-tiktok-scraper").call(run_input=run_input)
        dataset_id = get_dataset_id(run)
        
        for item in client.dataset(dataset_id).iterate_items():
            results.append({
                "Platform": "TikTok",
                "Author": item.get("authorMeta", {}).get("name") or item.get("author", "N/A"),
                "Followers": item.get("authorMeta", {}).get("fans", "N/A"),
                "Account_Created": "N/A",
                "Content": item.get("text") or item.get("desc") or "",
                "Likes": item.get("diggCount") or item.get("likesCount", 0) or 0,
                "Comments": item.get("commentCount", 0) or 0,
                "Shares/Views": item.get("playCount") or item.get("shareCount", 0) or 0,
                "Url": item.get("webVideoUrl") or item.get("videoUrl") or "",
                "Timestamp": item.get("createTime") or str(datetime.now(timezone.utc))
            })
    except Exception as e:
        st.warning(f"Kendala pada platform TikTok: {str(e)}")
    return results

def scrape_twitter(client, keyword, scrape_limit):
    results = []
    clean_kw = keyword.replace("#", "").replace("@", "").strip()
    try:
        if keyword.startswith("@"):
            search_query = f"from:{clean_kw}"
        elif keyword.startswith("#"):
            search_query = f"#{clean_kw}"
        else:
            search_query = clean_kw

        run_input = {"searchTerms": [search_query], "maxItems": scrape_limit, "sort": "Top"}
        run = client.actor("apify/twitter-scraper").call(run_input=run_input)
        dataset_id = get_dataset_id(run)
        
        for item in client.dataset(dataset_id).iterate_items():
            results.append({
                "Platform": "X(Twitter)",
                "Author": item.get("author", {}).get("userName") or "N/A",
                "Followers": item.get("author", {}).get("followers", "N/A"),
                "Account_Created": item.get("author", {}).get("createdAt", "N/A"),
                "Content": item.get("full_text") or item.get("text") or "",
                "Likes": item.get("likeCount", 0) or 0,
                "Comments": item.get("replyCount", 0) or 0,
                "Shares/Views": item.get("retweetCount", 0) or 0,
                "Url": item.get("url") or "",
                "Timestamp": item.get("createdAt") or str(datetime.now(timezone.utc))
            })
    except Exception as e:
        st.warning(f"Kendala pada platform X(Twitter): {str(e)}")
    return results

def scrape_facebook(client, keyword, scrape_limit):
    results = []
    clean_kw = keyword.replace("#", "").replace("@", "").strip()
    try:
        if keyword.startswith("@"):
            start_url = f"https://www.facebook.com/{clean_kw}"
        elif keyword.startswith("#"):
            start_url = f"https://www.facebook.com/hashtag/{clean_kw}"
        else:
            start_url = f"https://www.facebook.com/search/posts/?q={clean_kw.replace(' ', '%20')}"

        run_input = {
            "startUrls": [{"url": start_url}],
            "resultsLimit": scrape_limit
        }
        run = client.actor("apify/facebook-posts-scraper").call(run_input=run_input)
        dataset_id = get_dataset_id(run)
        
        for item in client.dataset(dataset_id).iterate_items():
            results.append({
                "Platform": "Facebook",
                "Author": item.get("user", {}).get("name") or "N/A",
                "Followers": "N/A",
                "Account_Created": "N/A",
                "Content": item.get("text") or "",
                "Likes": item.get("likes", 0) or 0,
                "Comments": item.get("comments", 0) or 0,
                "Shares/Views": item.get("shares", 0) or 0,
                "Url": item.get("url") or "",
                "Timestamp": item.get("time") or str(datetime.now(timezone.utc))
            })
    except Exception as e:
        st.warning(f"Kendala pada platform Facebook: {str(e)}")
    return results


# ==========================================
# 5. EKSEKUSI PENCARIAN & LAPORAN
# ==========================================

if btn_analyze:
    if program_token != "ANALYZER2026":
        st.error("❌ Token Program salah! Masukkan token yang valid (ANALYZER2026).")
    elif not platforms:
        st.error("❌ Silakan pilih minimal satu platform media sosial!")
    else:
        APIFY_PERMANENT_TOKEN = st.secrets.get("APIFY_API_TOKEN", "")
        all_raw_data = []

        status_box = st.status(f"🔍 Mengambil data mentah untuk database awal...", expanded=True)

        for p in platforms:
            status_box.write(f"⏳ Mengekstrak data dari **{p}**...")
            
            if p == "Instagram":
                # Menggunakan instagrapi
                res = scrape_instagram_instagrapi(keyword, raw_limit)
            else:
                # Menggunakan Apify untuk platform selain Instagram
                if not APIFY_PERMANENT_TOKEN:
                    st.error(f"❌ APIFY_API_TOKEN belum disetting di Streamlit Secrets untuk platform {p}.")
                    res = []
                else:
                    client = ApifyClient(APIFY_PERMANENT_TOKEN)
                    if p == "TikTok":
                        res = scrape_tiktok(client, keyword, raw_limit)
                    elif p == "X(Twitter)":
                        res = scrape_twitter(client, keyword, raw_limit)
                    elif p == "Facebook":
                        res = scrape_facebook(client, keyword, raw_limit)
                    else:
                        res = []
            
            all_raw_data.extend(res)

        if not all_raw_data:
            status_box.update(label="❌ Gagal mengambil data.", state="error", expanded=False)
            st.error("❌ Tidak ada data yang ditemukan dari platform yang dipilih.")
        else:
            df_raw = pd.DataFrame(all_raw_data)
            
            # 2. Jalankan Filter Berdasarkan Rentang Waktu
            status_box.write(f"⏳ Total {len(df_raw):,} data berhasil ditarik. Menerapkan filter rentang waktu: {filter_time}...")
            df_time_filtered = filter_by_time_range(df_raw, filter_time, start_date, end_date)
            
            if df_time_filtered.empty:
                status_box.update(label="⚠️ Tidak ada data dalam rentang waktu.", state="error", expanded=False)
                st.warning("⚠️ Ditemukan data dari API, tetapi tidak ada yang masuk dalam rentang waktu yang dipilih.")
            else:
                # 3. Hitung Skor Engagement (Likes + Comments + Shares/Views)
                status_box.write("⏳ Menghitung & mengurutkan skor engagement tertinggi...")
                df_time_filtered['Likes'] = pd.to_numeric(df_time_filtered['Likes'], errors='coerce').fillna(0)
                df_time_filtered['Comments'] = pd.to_numeric(df_time_filtered['Comments'], errors='coerce').fillna(0)
                df_time_filtered['Shares/Views'] = pd.to_numeric(df_time_filtered['Shares/Views'], errors='coerce').fillna(0)
                
                df_time_filtered['Engagement_Score'] = (
                    df_time_filtered['Likes'] + 
                    df_time_filtered['Comments'] + 
                    df_time_filtered['Shares/Views']
                )
                
                # 4. Urutkan berdasarkan Engagement Tertinggi
                df_sorted = df_time_filtered.sort_values(by='Engagement_Score', ascending=False)
                
                # 5. Filter Jumlah Postingan Terakhir (Top N) untuk Ditampilkan
                if max_items_selection == "-":
                    df_final = df_sorted.reset_index(drop=True)
                else:
                    df_final = df_sorted.head(int(max_items_selection)).reset_index(drop=True)
                
                # Simpan data tersaring ke memori Streamlit
                st.session_state["scraped_data"] = df_final
                status_box.update(label="✅ Analisa & penyaringan selesai!", state="complete", expanded=False)
                st.success(f"🎉 Berhasil memproses data! Dari {len(df_raw):,} raw data yang ditarik, {len(df_final)} postingan dengan engagement tertinggi ditampilkan.")


# ==========================================
# 6. DISPLAY MULTI-TAB REPORT
# ==========================================

if "scraped_data" in st.session_state:
    df = st.session_state["scraped_data"]

    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📊 METRIK & RINGKASAN", "📝 DETAIL POSTINGAN", "📥 UNDUH LAPORAN"])

    with tab1:
        st.subheader("Ringkasan Performa Per Platform (Engagement Tertinggi)")
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Data Ditampilkan", len(df))
        col_m2.metric("Total Likes", f"{int(df['Likes'].sum()):,}")
        col_m3.metric("Total Komentar", f"{int(df['Comments'].sum()):,}")
        col_m4.metric("Total Views/Shares", f"{int(df['Shares/Views'].sum()):,}")

        st.markdown("### Visualisasi Interaksi")
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            fig_likes = px.bar(
                df, x="Platform", y="Likes", color="Platform",
                title="Total Likes Per Platform", text_auto=True
            )
            st.plotly_chart(fig_likes, use_container_width=True)

        with col_chart2:
            fig_comments = px.pie(
                df, names="Platform", values="Comments",
                title="Distribusi Komentar Per Platform"
            )
            st.plotly_chart(fig_comments, use_container_width=True)

    with tab2:
        st.subheader("Detail Posting Media Sosial (Urutan Engagement Tertinggi)")
        st.dataframe(
            df[["Platform", "Author", "Followers", "Account_Created", "Content", "Likes", "Comments", "Shares/Views", "Engagement_Score", "Timestamp", "Url"]],
            use_container_width=True
        )

    with tab3:
        st.subheader("Unduh Laporan Data")
        
        csv_buffer = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Unduh Data sebagai CSV",
            data=csv_buffer,
            file_name=f"analisa_sosmed_{keyword.replace('@','').replace('#','')}.csv",
            mime="text/csv",
            use_container_width=True
        )

        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Data Postingan', index=False)
            excel_data = excel_buffer.getvalue()

        st.download_button(
            label="📊 Unduh Data sebagai Excel (.xlsx)",
            data=excel_data,
            file_name=f"analisa_sosmed_{keyword.replace('@','').replace('#','')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
