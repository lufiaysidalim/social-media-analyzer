import streamlit as st
import pandas as pd
import plotly.express as px
from apify_client import ApifyClient
from datetime import datetime, timedelta, timezone
import io

# ==========================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==========================================
st.set_page_config(
    page_title="Social Media Analyzer Pro",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Social Media Analyzer Pro")
st.caption("Sistem Analisis Media Sosial Profesional bertenaga Apify API dengan Filter Waktu & Engagement Tinggi.")

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
    # DEFAULT DINAIKKAN MENJADI 500.000 POSTINGAN
    raw_limit = st.number_input("Batas Tarik Raw Data:", min_value=1000, max_value=5000000, value=500000, step=50000)

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
# 3. FUNGSI BANTUAN & SCRAPER PER PLATFORM
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


def scrape_instagram(client, keyword, scrape_limit):
    clean_kw = keyword.replace("#", "").replace("@", "").strip()
    results = []
    try:
        if keyword.startswith("@"):
            run_input = {"usernames": [clean_kw], "resultsLimit": scrape_limit}
            run = client.actor("apify/instagram-scraper").call(run_input=run_input)
        else:
            run_input = {
                "hashtags": [clean_kw.replace(" ", "")], 
                "resultsLimit": scrape_limit,
                "resultsType": "top"  # Mengambil postingan populer/top engagement
            }
            run = client.actor("apify/instagram-hashtag-scraper").call(run_input=run_input)

        dataset_id = get_dataset_id(run)
        
        # PERBAIKAN: Gunakan iterate_items() untuk membaca seluruh ratusan ribu baris data tanpa terpotong limit 1000
        for item in client.dataset(dataset_id).iterate_items():
            results.append({
                "Platform": "Instagram",
                "Author": item.get("ownerUsername") or item.get("owner", {}).get("username") or clean_kw,
                "Followers": item.get("owner", {}).get("followersCount", "N/A"),
                "Account_Created": "N/A", 
                "Content": item.get("caption") or "",
                "Likes": item.get("likesCount", 0) or 0,
                "Comments": item.get("commentsCount", 0) or 0,
                "Shares/Views": item.get("videoViewCount") or item.get("videoPlayCount") or item.get("playsCount") or 0,
                "Url": item.get("url") or item.get("postUrl") or f"https://instagram.com/p/{item.get('shortCode', '')}",
                "Timestamp": item.get("timestamp") or item.get("takenAt") or str(datetime.now(timezone.utc))
            })
    except Exception as e:
        st.warning(f"Kendala pada platform Instagram: {str(e)}")
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
        
        # PERBAIKAN: Iterate seluru item dataset
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
# 4. EKSEKUSI PENCARIAN & LAPORAN
# ==========================================

if btn_analyze:
    if program_token != "ANALYZER2026":
        st.error("❌ Token Program salah! Masukkan token yang valid (ANALYZER2026).")
    elif not platforms:
        st.error("❌ Silakan pilih minimal satu platform media sosial!")
    else:
        try:
            APIFY_PERMANENT_TOKEN = st.secrets["APIFY_API_TOKEN"]
        except Exception:
            APIFY_PERMANENT_TOKEN = ""

        if not APIFY_PERMANENT_TOKEN:
            st.error("❌ APIFY_API_TOKEN belum disetting di Streamlit Secrets.")
        else:
            client = ApifyClient(APIFY_PERMANENT_TOKEN)
            all_raw_data = []

            status_box = st.status(f"🔍 Mengambil {raw_limit:,} data mentah untuk database awal...", expanded=True)

            # 1. Jalankan Scrape data mentah sebanyak input `raw_limit`
            for p in platforms:
                status_box.write(f"⏳ Mengekstrak maksimal {raw_limit:,} data dari **{p}**...")
                if p == "Instagram":
                    res = scrape_instagram(client, keyword, raw_limit)
                elif p == "TikTok":
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
# 5. DISPLAY MULTI-TAB REPORT
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
