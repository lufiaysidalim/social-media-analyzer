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
    layout="wide"
)

# Header Utama
st.title("📊 Social Media Analyzer Pro (& Multi-Tab Report)")
st.caption("Sistem Analisis Media Sosial Profesional bertenaga Apify API & Google Drive Integration.")

# ==========================================
# 2. SIDEBAR & INTEGRASI API
# ==========================================
st.sidebar.header("⚙️ Pengaturan & API Key")

# Mengambil token dari Streamlit Secrets atau Input Manual
default_apify_token = st.secrets.get("APIFY_TOKEN", "") if hasattr(st, "secrets") else ""
apify_token = st.sidebar.text_input("Apify API Token:", value=default_apify_token, type="password")

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tips Pencarian Instagram:**\n- Gunakan `@nama_akun` untuk mengambil pos dari akun tertentu.\n- Gunakan `kata_kunci` atau `#hashtag` untuk mencari postingan berdasarkan topik.")

# ==========================================
# 3. FORM INPUT UTAMA
# ==========================================
col1, col2, col3 = st.columns([2, 1.5, 1.5])

with col1:
    keyword = st.text_input("Topik / Hashtag / Nama Akun:", value="metrologi")

with col2:
    platforms = st.multiselect("Platform:", ["Instagram", "YouTube", "TikTok", "Twitter/X"], default=["Instagram"])

with col3:
    max_items = st.selectbox("Jumlah Post Per Platform:", [5, 10, 20, 50, 100], index=1)

col_f1, col_f2 = st.columns(2)
with col_f1:
    filter_time = st.selectbox("Rentang Waktu Filter:", ["1 Minggu", "1 Bulan", "3 Bulan", "6 Bulan", "1 Tahun"], index=1)

with col_f2:
    security_token = st.text_input("Token Akses Keamanan (Khusus Pengguna Berizin):", type="password")

# ==========================================
# 4. FUNGSI SCRAPER PER PLATFORM
# ==========================================

def scrape_instagram(client, keyword, max_items):
    """
    Fungsi Scraper Instagram dengan perbaikan Actor Apify:
    - Akun (@username) -> apify/instagram-post-scraper
    - Hashtag/Topik -> apify/instagram-hashtag-scraper
    """
    clean_kw = keyword.replace("#", "").replace("@", "").strip()
    results = []

    # OPSI A: Jika pencarian berawalan '@' (Target Profil Akun)
    if keyword.startswith("@"):
        try:
            run_input = {
                "username": [clean_kw],
                "resultsLimit": int(max_items)
            }
            run = client.actor("apify/instagram-post-scraper").call(run_input=run_input)
            dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
            
            for item in dataset_items:
                results.append({
                    "Platform": "Instagram",
                    "Author": item.get("ownerUsername") or clean_kw,
                    "Content": item.get("caption") or "",
                    "Likes": item.get("likesCount", 0),
                    "Comments": item.get("commentsCount", 0),
                    "Shares/Views": item.get("videoViewCount") or item.get("videoPlayCount") or 0,
                    "Url": item.get("url") or f"https://instagram.com/p/{item.get('shortCode', '')}",
                    "Timestamp": item.get("timestamp") or str(datetime.now())
                })
            return results
        except Exception as e:
            st.warning(f"Metode Profile Scraper gagal: {str(e)}. Mengalihkan ke Hashtag Scraper...")

    # OPSI B: Jika pencarian berupa Hashtag / Topik (Default)
    try:
        run_input = {
            "hashtags": [clean_kw],
            "resultsLimit": int(max_items),
            "resultsType": "posts"
        }
        # Gunakan actor khusus hashtag
        run = client.actor("apify/instagram-hashtag-scraper").call(run_input=run_input)
        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        
        for item in dataset_items:
            results.append({
                "Platform": "Instagram",
                "Author": item.get("ownerUsername") or item.get("owner", {}).get("username") or "N/A",
                "Content": item.get("caption") or "",
                "Likes": item.get("likesCount", 0),
                "Comments": item.get("commentsCount", 0),
                "Shares/Views": item.get("videoPlayCount") or item.get("playsCount") or 0,
                "Url": item.get("url") or item.get("postUrl") or "",
                "Timestamp": item.get("timestamp") or item.get("takenAt") or str(datetime.now())
            })
            
    except Exception as e1:
        # Fallback jika Hashtag Scraper gagal/kosong, coba via Profile Scraper
        try:
            run_input = {
                "username": [clean_kw],
                "resultsLimit": int(max_items)
            }
            run = client.actor("apify/instagram-post-scraper").call(run_input=run_input)
            dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
            
            for item in dataset_items:
                results.append({
                    "Platform": "Instagram",
                    "Author": item.get("ownerUsername") or clean_kw,
                    "Content": item.get("caption") or "",
                    "Likes": item.get("likesCount", 0),
                    "Comments": item.get("commentsCount", 0),
                    "Shares/Views": item.get("videoViewCount") or 0,
                    "Url": item.get("url") or "",
                    "Timestamp": item.get("timestamp") or str(datetime.now())
                })
        except Exception as e2:
            st.warning(f"Kendala pada platform Instagram: {str(e1)}")

    return results


def scrape_youtube(client, keyword, max_items):
    results = []
    try:
        run_input = {
            "searchKeywords": keyword,
            "maxResults": int(max_items)
        }
        run = client.actor("apify/youtube-scraper").call(run_input=run_input)
        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        
        for item in dataset_items:
            results.append({
                "Platform": "YouTube",
                "Author": item.get("channelName") or item.get("channelUrl") or "N/A",
                "Content": f"{item.get('title', '')}\n{item.get('text', '') or item.get('description', '')}",
                "Likes": item.get("likes", 0),
                "Comments": item.get("commentsCount", 0),
                "Shares/Views": item.get("viewCount", 0),
                "Url": item.get("url") or item.get("videoUrl") or "",
                "Timestamp": item.get("date") or str(datetime.now())
            })
    except Exception as e:
        st.warning(f"Kendala pada platform YouTube: {str(e)}")
    return results


def scrape_tiktok(client, keyword, max_items):
    results = []
    clean_kw = keyword.replace("#", "").replace("@", "").strip()
    try:
        run_input = {
            "hashtags": [clean_kw],
            "resultsPerPage": int(max_items)
        }
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
    try:
        run_input = {
            "searchTerms": [keyword],
            "maxItems": int(max_items)
        }
        run = client.actor("apify/twitter-scraper").call(run_input=run_input)
        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        
        for item in dataset_items:
            results.append({
                "Platform": "Twitter/X",
                "Author": item.get("author", {}).get("userName") or "N/A",
                "Content": item.get("full_text") or item.get("text") or "",
                "Likes": item.get("likeCount", 0),
                "Comments": item.get("replyCount", 0),
                "Shares/Views": item.get("retweetCount", 0),
                "Url": item.get("url") or "",
                "Timestamp": item.get("createdAt") or str(datetime.now())
            })
    except Exception as e:
        st.warning(f"Kendala pada platform Twitter/X: {str(e)}")
    return results

# ==========================================
# 5. EKSEKUSI PENCARIAN & LAPORAN
# ==========================================

btn_analyze = st.button("🚀 ANALISA DATA RIIL & BUAT LAPORAN", use_container_width=True)

if btn_analyze:
    if not apify_token:
        st.error("❌ Mohon masukkan Apify API Token pada sidebar atau tentukan di Streamlit Secrets!")
    elif not platforms:
        st.error("❌ Silakan pilih minimal satu platform media sosial!")
    else:
        client = ApifyClient(apify_token)
        all_data = []

        status_box = st.status("🔍 Mengambil data riil dari media sosial...", expanded=True)

        for p in platforms:
            status_box.write(f"⏳ Mengambil data riil dari **{p}**...")
            if p == "Instagram":
                res = scrape_instagram(client, keyword, max_items)
            elif p == "YouTube":
                res = scrape_youtube(client, keyword, max_items)
            elif p == "TikTok":
                res = scrape_tiktok(client, keyword, max_items)
            elif p == "Twitter/X":
                res = scrape_twitter(client, keyword, max_items)
            else:
                res = []
            
            all_data.extend(res)

        status_box.update(label="✅ Pengambilan data selesai!", state="complete", expanded=False)

        if not all_data:
            st.error("❌ Tidak ada data riil yang ditemukan dari platform yang dipilih.")
        else:
            df = pd.DataFrame(all_data)
            st.session_state["scraped_data"] = df
            st.success(f"🎉 Berhasil mengambil {len(df)} data postingan!")

# ==========================================
# 6. DISPLAY MULTI-TAB REPORT
# ==========================================

if "scraped_data" in st.session_state:
    df = st.session_state["scraped_data"]

    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📊 METRIK & RINGKASAN", "📝 DETAIL POSTINGAN", "📥 UNDUH LAPORAN"])

    with tab1:
        st.subheader("Ringkasan Performa Per Platform")
        
        # Summary Metrics
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
        
        # Download CSV
        csv_buffer = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Unduh Data sebagai CSV",
            data=csv_buffer,
            file_name=f"social_media_report_{keyword}.csv",
            mime="text/csv",
            use_container_width=True
        )

        # Download Excel
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Data Postingan', index=False)
        excel_data = excel_buffer.getvalue()

        st.download_button(
            label="📊 Unduh Data sebagai Excel (.xlsx)",
            data=excel_data,
            file_name=f"social_media_report_{keyword}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
