import streamlit as st
import pandas as pd
import plotly.express as px
from apify_client import ApifyClient
from datetime import datetime
import io

# ==========================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==========================================
st.set_page_config(
    page_title="Social Media Analyzer Pro",
    page_icon="📊",
    layout="centered"
)

st.title("📊 Social Media Analyzer Pro")
st.caption("Sistem Analisis Media Sosial Profesional bertenaga Apify API.")

# ==========================================
# 2. FORM INPUT UTAMA
# ==========================================

# KOLOM ATAS: Input Tema / Hashtag / Nama Akun
keyword = st.text_input("Tema / Hashtag / Nama Akun:", value="metrologi")
st.info("💡 **Tips Input:** Gunakan `@` untuk Akun (contoh: @jokowi), `#` untuk Hashtag (contoh: #metrologi), atau ketik langsung untuk Topik (contoh: metrologi).")

# KOLOM KEDUA: Filter (Platform, Jumlah Postingan, Rentang Waktu)
col1, col2, col3 = st.columns(3)

with col1:
    platforms = st.multiselect("Platform:", ["FB", "IG", "TikTok", "X"], default=["IG"])

with col2:
    max_items = st.selectbox("Jumlah Postingan:", [10, 20, 50, 100, 500, 1000], index=0)

with col3:
    filter_time = st.selectbox(
        "Rentang Waktu:", 
        ["1 Hari", "1 Minggu", "1 Bulan", "3 Bulan", "6 Bulan", "1 Tahun", "5 Tahun", "Custom"], 
        index=2
    )

# Kondisi jika memilih rentang waktu "Custom"
if filter_time == "Custom":
    col_date1, col_date2 = st.columns(2)
    with col_date1:
        start_date = st.date_input("Waktu Range Awal")
    with col_date2:
        end_date = st.date_input("Waktu Range Akhir")

# KOLOM BAWAH: Token untuk Menjalankan Program
program_token = st.text_input("Token Program:", type="password", placeholder="Masukkan token program...")

# TOMBOL ANALISA DI BAWAHNYA
btn_analyze = st.button("ANALISA")


# ==========================================
# 3. FUNGSI SCRAPER PER PLATFORM
# ==========================================

def scrape_instagram(client, keyword, max_items):
    clean_kw = keyword.replace("#", "").replace("@", "").strip()
    results = []
    
    try:
        if keyword.startswith("@"):
            run_input = {"usernames": [clean_kw], "resultsLimit": int(max_items)}
            run = client.actor("apify/instagram-scraper").call(run_input=run_input)
        elif keyword.startswith("#"):
            run_input = {"hashtags": [clean_kw], "resultsLimit": int(max_items)}
            run = client.actor("apify/instagram-hashtag-scraper").call(run_input=run_input)
        else:
            run_input = {"hashtags": [clean_kw.replace(" ", "")], "resultsLimit": int(max_items)}
            run = client.actor("apify/instagram-hashtag-scraper").call(run_input=run_input)

        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        
        for item in dataset_items:
            results.append({
                "Platform": "IG",
                "Author": item.get("ownerUsername") or item.get("owner", {}).get("username") or clean_kw,
                "Content": item.get("caption") or "",
                "Likes": item.get("likesCount", 0),
                "Comments": item.get("commentsCount", 0),
                "Shares/Views": item.get("videoViewCount") or item.get("videoPlayCount") or item.get("playsCount") or 0,
                "Url": item.get("url") or item.get("postUrl") or f"https://instagram.com/p/{item.get('shortCode', '')}",
                "Timestamp": item.get("timestamp") or item.get("takenAt") or str(datetime.now())
            })
    except Exception as e:
        st.warning(f"Kendala pada platform IG: {str(e)}")
    return results

def scrape_tiktok(client, keyword, max_items):
    results = []
    clean_kw = keyword.replace("#", "").replace("@", "").strip()
    try:
        if keyword.startswith("@"):
            run_input = {"profiles": [clean_kw], "resultsPerPage": int(max_items)}
        elif keyword.startswith("#"):
            run_input = {"hashtags": [clean_kw], "resultsPerPage": int(max_items)}
        else:
            run_input = {"searchQueries": [clean_kw], "resultsPerPage": int(max_items)}

        run = client.actor("clockworks/free-tiktok-scraper").call(run_input=run_input)
        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        
        for item in dataset_items:
            results.append({
                "Platform": "TikTok",
                "Author": item.get("authorMeta", {}).get("name") or item.get("author", "N/A"),
                "Content": item.get("text") or item.get("desc") or "",
                "Likes": item.get("diggCount") or item.get("likesCount", 0),
                "Comments": item.get("commentCount", 0),
                "Shares/Views": item.get("playCount") or item.get("shareCount", 0),
                "Url": item.get("webVideoUrl") or item.get("videoUrl") or "",
                "Timestamp": str(datetime.now())
            })
    except Exception as e:
        st.warning(f"Kendala pada platform TikTok: {str(e)}")
    return results

def scrape_twitter(client, keyword, max_items):
    results = []
    clean_kw = keyword.replace("#", "").replace("@", "").strip()
    try:
        if keyword.startswith("@"):
            search_query = f"from:{clean_kw}"
        elif keyword.startswith("#"):
            search_query = f"#{clean_kw}"
        else:
            search_query = clean_kw

        run_input = {"searchTerms": [search_query], "maxItems": int(max_items)}
        run = client.actor("apify/twitter-scraper").call(run_input=run_input)
        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        
        for item in dataset_items:
            results.append({
                "Platform": "X",
                "Author": item.get("author", {}).get("userName") or "N/A",
                "Content": item.get("full_text") or item.get("text") or "",
                "Likes": item.get("likeCount", 0),
                "Comments": item.get("replyCount", 0),
                "Shares/Views": item.get("retweetCount", 0),
                "Url": item.get("url") or "",
                "Timestamp": item.get("createdAt") or str(datetime.now())
            })
    except Exception as e:
        st.warning(f"Kendala pada platform X: {str(e)}")
    return results

def scrape_facebook(client, keyword, max_items):
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
            "resultsLimit": int(max_items)
        }
        run = client.actor("apify/facebook-posts-scraper").call(run_input=run_input)
        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        
        for item in dataset_items:
            results.append({
                "Platform": "FB",
                "Author": item.get("user", {}).get("name") or "N/A",
                "Content": item.get("text") or "",
                "Likes": item.get("likes", 0),
                "Comments": item.get("comments", 0),
                "Shares/Views": item.get("shares", 0),
                "Url": item.get("url") or "",
                "Timestamp": item.get("time") or str(datetime.now())
            })
    except Exception as e:
        st.warning(f"Kendala pada platform FB: {str(e)}")
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
        # Token Apify permanen dari Streamlit Secrets
        APIFY_PERMANENT_TOKEN = st.secrets["APIFY_API_TOKEN"]
        client = ApifyClient(APIFY_PERMANENT_TOKEN)
        all_data = []

        status_box = st.status("🔍 Menganalisa data dari media sosial...", expanded=True)

        for p in platforms:
            status_box.write(f"⏳ Mengambil data dari **{p}**...")
            if p == "IG":
                res = scrape_instagram(client, keyword, max_items)
            elif p == "TikTok":
                res = scrape_tiktok(client, keyword, max_items)
            elif p == "X":
                res = scrape_twitter(client, keyword, max_items)
            elif p == "FB":
                res = scrape_facebook(client, keyword, max_items)
            else:
                res = []
            
            all_data.extend(res)

        status_box.update(label="✅ Analisa selesai!", state="complete", expanded=False)

        if not all_data:
            st.error("❌ Tidak ada data yang ditemukan berdasarkan filter Anda.")
        else:
            df = pd.DataFrame(all_data)
            st.session_state["scraped_data"] = df
            st.success(f"🎉 Berhasil menganalisa {len(df)} data postingan!")

# ==========================================
# 5. DISPLAY MULTI-TAB REPORT
# ==========================================

if "scraped_data" in st.session_state:
    df = st.session_state["scraped_data"]

    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📊 METRIK & RINGKASAN", "📝 DETAIL POSTINGAN", "📥 UNDUH LAPORAN"])

    with tab1:
        st.subheader("Ringkasan Performa Per Platform")
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Total Postingan", len(df))
        col_m2.metric("Total Likes", f"{df['Likes'].sum():,}")
        col_m3.metric("Total Komentar", f"{df['Comments'].sum():,}")
        col_m4.metric("Total Views/Shares", f"{df['Shares/Views'].sum():,}")

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
        st.subheader("Detail Posting Media Sosial")
        st.dataframe(
            df[["Platform", "Author", "Content", "Likes", "Comments", "Shares/Views", "Url"]],
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
