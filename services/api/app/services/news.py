import html
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import httpx

WIB_TZ = timezone(timedelta(hours=7))
MAX_AGE_SECONDS = 7 * 24 * 3600  # Paling lama 1 minggu (7 hari)

MONTHS_ID = [
    "", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
]

# Category definitions for Indonesian financial, commodity, crypto & tech news
NEWS_CATEGORIES = {
    "all": {
        "id": "all",
        "label": "Semua Berita",
        "query": "(kripto OR bitcoin OR IHSG OR saham OR \"harga emas\" OR ekonomi OR teknologi AI) Indonesia when:7d",
        "badge": "TERKINI",
        "direct_feeds": [
            ("CNBC Indonesia Market", "https://www.cnbcindonesia.com/market/rss"),
            ("CNBC Indonesia Tech", "https://www.cnbcindonesia.com/tech/rss"),
            ("Antara Ekonomi", "https://www.antaranews.com/rss/ekonomi.xml"),
            ("Antara Tekno", "https://www.antaranews.com/rss/tekno.xml"),
        ],
    },
    "crypto": {
        "id": "crypto",
        "label": "Crypto & Web3",
        "query": "(kripto OR bitcoin OR solana OR ethereum OR aset kripto OR blockchain) Indonesia when:7d",
        "badge": "CRYPTO",
        "direct_feeds": [
            ("CNBC Indonesia Market", "https://www.cnbcindonesia.com/market/rss"),
            ("CNBC Indonesia Tech", "https://www.cnbcindonesia.com/tech/rss"),
        ],
    },
    "saham": {
        "id": "saham",
        "label": "Saham & IHSG",
        "query": "(IHSG OR saham BEI OR bursa efek indonesia OR emiten OR dividen saham) when:7d",
        "badge": "SAHAM",
        "direct_feeds": [
            ("CNBC Indonesia Market", "https://www.cnbcindonesia.com/market/rss"),
            ("Antara Ekonomi", "https://www.antaranews.com/rss/ekonomi.xml"),
        ],
    },
    "emas": {
        "id": "emas",
        "label": "Emas & Komoditas",
        "query": "(\"harga emas\" OR \"emas antam\" OR logam mulia OR emas pegadaian OR XAU) when:7d",
        "badge": "EMAS",
        "direct_feeds": [
            ("CNBC Indonesia Market", "https://www.cnbcindonesia.com/market/rss"),
            ("Antara Ekonomi", "https://www.antaranews.com/rss/ekonomi.xml"),
        ],
    },
    "ekonomi": {
        "id": "ekonomi",
        "label": "Ekonomi & Makro",
        "query": "(ekonomi indonesia OR bank indonesia OR nilai tukar rupiah OR inflasi OR suku bunga BI) when:7d",
        "badge": "EKONOMI",
        "direct_feeds": [
            ("CNBC Indonesia Market", "https://www.cnbcindonesia.com/market/rss"),
            ("CNBC Indonesia News", "https://www.cnbcindonesia.com/news/rss"),
            ("Antara Ekonomi", "https://www.antaranews.com/rss/ekonomi.xml"),
        ],
    },
    "teknologi": {
        "id": "teknologi",
        "label": "Teknologi & AI",
        "query": "(teknologi AI OR kecerdasan buatan OR startup digital OR semikonduktor OR siber) Indonesia when:7d",
        "badge": "TEKNOLOGI",
        "direct_feeds": [
            ("CNBC Indonesia Tech", "https://www.cnbcindonesia.com/tech/rss"),
            ("Antara Tekno", "https://www.antaranews.com/rss/tekno.xml"),
        ],
    },
}

# Curated high-resolution financial & tech thumbnails per category (used when RSS item has no <enclosure>)
CATEGORY_THUMBNAILS: dict[str, list[str]] = {
    "crypto": [
        "https://images.unsplash.com/photo-1518546305927-5a555bb7020d?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1621761191319-c6fb62004040?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1642790106117-e829e14a795f?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1605792657660-596af9009e82?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1622630998477-20aa696ecb05?auto=format&fit=crop&w=800&q=80",
    ],
    "saham": [
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1535320903710-d993d3d77d29?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1642543492481-44e81e3914a7?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=800&q=80",
    ],
    "emas": [
        "https://images.unsplash.com/photo-1610375461246-83df859d849d?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1589758438368-0ad531db3366?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1624365168968-f283d506c6b6?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1573408301185-9146fe634ad0?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&w=800&q=80",
    ],
    "ekonomi": [
        "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1580519542036-c47de6196ba5?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1444653614773-995cb1ef9efa?auto=format&fit=crop&w=800&q=80",
    ],
    "teknologi": [
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=800&q=80",
    ],
}

# In-memory TTL cache per category so UI tab switching is fast
_NEWS_CACHE: dict[str, dict] = {}
_CACHE_TTL_SEC = 180  # 3 minutes


def _clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_image_from_item(item: ET.Element, desc_raw: str) -> str | None:
    # 1. Check <enclosure url="..." type="image/..." />
    enclosure = item.find("enclosure")
    if enclosure is not None:
        enc_url = (enclosure.get("url") or "").strip()
        if enc_url.startswith("http"):
            return enc_url

    # 2. Check media:content or media:thumbnail namespaces
    for child in item:
        tag_lower = child.tag.lower()
        if "content" in tag_lower or "thumbnail" in tag_lower:
            m_url = (child.get("url") or "").strip()
            if m_url.startswith("http"):
                return m_url

    # 3. Check <img src="..."> inside description HTML
    if desc_raw:
        img_match = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', desc_raw, re.IGNORECASE)
        if img_match:
            found_url = img_match.group(1).strip()
            if not any(
                skip in found_url.lower()
                for skip in [
                    "1x1",
                    "pixel",
                    "tracker",
                    "lh3.googleusercontent.com/J6_coFbogxhRI9iM864NL_liGXvsQp2AupsKei7z0cNNfDvGUmWUy20nuUhkREQyrpY4bEeIBuc=s0-w300",
                ]
            ):
                return found_url

    return None


def _pick_fallback_thumbnail(category: str, title: str) -> str:
    pool = CATEGORY_THUMBNAILS.get(category) or CATEGORY_THUMBNAILS["ekonomi"]
    idx = sum(ord(ch) for ch in title) % len(pool)
    return pool[idx]


def _classify_article_tags(title: str, summary: str, category: str) -> dict:
    """
    Classify article into rich Indonesian market status & topic tags:
    Primary status (`sentiment`):
      - BAHAYA (🚨 Bahaya / Risiko Tinggi)
      - WASPADA (⚠️ Waspada / Tekanan Pasar)
      - PELUANG_CUAN (🚀 Peluang Cuan / Katalis Kuat)
      - POSITIF (📈 Positif / Menguat)
      - NETRAL (⚖️ Netral / Informasi Pasar)
    Plus contextual topic tags (`tags` list).
    """
    text = f"{title} {summary}".lower()

    danger_words = [
        "bahaya", "scam", "rug pull", "rugpull", "bobol", "diretas", "hack", "peretasan",
        "penipuan", "bodong", "ilegal", "dilarang", "sanksi", "pailit", "bangkrut",
        "anjlok parah", "krisis", "perang", "delisting", "likuidasi", "gembok", "suspen",
        "suspensi", "darurat", "kerugian besar", "jebakan", "manipulasi", "kejahatan",
    ]
    caution_words = [
        "waspada", "hati-hati", "turun", "anjlok", "melemah", "rugi", "koreksi",
        "bearish", "merah", "jatuh", "tertekan", "defisit", "inflasi", "dump",
        "longsor", "phk", "terjun", "volatilitas", "gejolak", "aksi jual", "outflow",
        "ketidakpastian", "tarif", "perang dagang", "utang", "beban", "rawan",
    ]
    strong_bull_words = [
        "rekor", "melonjak", "meroket", "terbang", "cuan", "untung besar", "all time high",
        "ath", "reli", "breakout", "dividen jumbo", "laba melonjak", "surplus besar",
        "akumulasi", "peluang", "prospek cerah", "bullish",
    ]
    positive_words = [
        "naik", "menguat", "positif", "tumbuh", "melambung", "hijau", "surplus",
        "optimis", "apresiasi", "beli", "ekspansi", "inovasi", "kerjasama", "adopsi",
        "stabil", "pulih", "bangkit", "dukung", "resmi",
    ]

    danger_hits = sum(1 for w in danger_words if w in text)
    caution_hits = sum(1 for w in caution_words if w in text)
    strong_bull_hits = sum(1 for w in strong_bull_words if w in text)
    positive_hits = sum(1 for w in positive_words if w in text)

    tags: list[dict] = []

    # 1. Determine Primary Status Tag
    if danger_hits > 0:
        sentiment = "BAHAYA"
        sentiment_label = "🚨 BAHAYA"
        tags.append({"id": "BAHAYA", "label": "🚨 Bahaya & Risiko Tinggi", "tone": "danger"})
    elif caution_hits > (positive_hits + strong_bull_hits):
        sentiment = "WASPADA"
        sentiment_label = "⚠️ WASPADA"
        tags.append({"id": "WASPADA", "label": "⚠️ Waspada Tekanan Pasar", "tone": "warning"})
    elif strong_bull_hits > 0 and strong_bull_hits >= caution_hits:
        sentiment = "PELUANG_CUAN"
        sentiment_label = "🚀 PELUANG CUAN"
        tags.append({"id": "PELUANG_CUAN", "label": "🚀 Katalis Bullish", "tone": "emerald"})
    elif positive_hits > caution_hits:
        sentiment = "POSITIF"
        sentiment_label = "📈 POSITIF"
        tags.append({"id": "POSITIF", "label": "📈 Sentimen Positif", "tone": "success"})
    else:
        sentiment = "NETRAL"
        sentiment_label = "⚖️ NETRAL"
        tags.append({"id": "NETRAL", "label": "⚖️ Netral / Info Pasar", "tone": "neutral"})

    # 2. Contextual Topic Tags (up to 3 additional tags)
    topic_rules = [
        (
            "REGULASI_PAJAK",
            "🏛️ Regulasi & Pajak",
            "info",
            ["pajak", "ojk", "bappebti", "aturan", "regulasi", "kemenkeu", "djp", "undang-undang", "kebijakan", "hukum", "pengawasan"],
        ),
        (
            "MONETER_BI",
            "🏦 Suku Bunga & BI",
            "info",
            ["bank indonesia", "suku bunga", "bi rate", "the fed", "inflasi", "rupiah", "kurs", "moneter", "cadangan devisa"],
        ),
        (
            "KEAMANAN_SIBER",
            "🛡️ Keamanan & Siber",
            "danger",
            ["siber", "keamanan", "hack", "bobol", "data", "privasi", "penipuan", "scam", "gembok", "perlindungan"],
        ),
        (
            "DIVIDEN_EMITEN",
            "💸 Emiten & Dividen",
            "emerald",
            ["dividen", "emiten", "laba", "kuartal", "ipo", "saham", "buyback", "rups", "bei", "ihsg"],
        ),
        (
            "LOGAM_MULIA",
            "🪙 Harga Emas / Safe Haven",
            "amber",
            ["emas", "antam", "pegadaian", "logam mulia", "xau", "safe haven", "komoditas"],
        ),
        (
            "WHALE_INSTITUSI",
            "🐋 Aksi Institusi & Asing",
            "purple",
            ["whale", "institusi", "asing", "investor asing", "etf", "blackrock", "dana", "akumulasi", "inflow", "outflow"],
        ),
        (
            "INOVASI_AI",
            "🤖 AI & Inovasi Digital",
            "purple",
            ["ai", "kecerdasan buatan", "teknologi", "chip", "semikonduktor", "digital", "startup", "aplikasi", "robot", "cloud"],
        ),
        (
            "GEOPOLITIK_GLOBAL",
            "🌍 Geopolitik & Global",
            "warning",
            ["global", "perang", "timur tengah", "china", "amerika", "as", "tarif", "ekspor", "impor", "dunia", "lintas negara"],
        ),
    ]

    for tag_id, tag_label, tag_tone, keywords in topic_rules:
        if any(k in text for k in keywords):
            tags.append({"id": tag_id, "label": tag_label, "tone": tag_tone})
        if len(tags) >= 3:
            break

    # Guarantee at least 2 tags on every article for rich UI display
    if len(tags) == 1:
        fallback_topic_by_cat = {
            "crypto": {"id": "ASET_KRIPTO", "label": "⚡ Pasar Aset Kripto", "tone": "amber"},
            "saham": {"id": "BURSA_SAHAM", "label": "📊 Bursa Efek Indonesia", "tone": "emerald"},
            "emas": {"id": "LOGAM_MULIA", "label": "🪙 Harga Emas / Safe Haven", "tone": "amber"},
            "ekonomi": {"id": "MAKRO_EKONOMI", "label": "🏦 Makroekonomi RI", "tone": "info"},
            "teknologi": {"id": "INOVASI_AI", "label": "🤖 AI & Inovasi Digital", "tone": "purple"},
        }
        tags.append(
            fallback_topic_by_cat.get(
                category,
                {"id": "RISET_PASAR", "label": "📰 Riset Pasar Terkini", "tone": "info"},
            )
        )

    return {
        "sentiment": sentiment,
        "sentiment_label": sentiment_label,
        "tags": tags,
    }


def _detect_category_from_text(title: str, summary: str = "") -> str:
    t = f"{title} {summary}".lower()
    if any(k in t for k in ["kripto", "crypto", "bitcoin", "btc", "solana", "ethereum", "eth", "blockchain", "token", "altcoin", "web3", "bappebti", "indodax"]):
        return "crypto"
    if any(k in t for k in ["emas", "antam", "logam mulia", "pegadaian", "xau", "bullion"]):
        return "emas"
    if any(k in t for k in ["ihsg", "saham", "bei", "emiten", "bursa efek", "dividen", "idx", "lq45", "ipo"]):
        return "saham"
    if any(k in t for k in ["ai", "teknologi", "kecerdasan buatan", "aplikasi", "chip", "semikonduktor", "siber", "inovasi", "digital", "startup", "gadget", "cloud", "robot"]):
        return "teknologi"
    return "ekonomi"


def _matches_category(cat_key: str, resolved_cat: str, title: str, summary: str) -> bool:
    if cat_key == "all":
        return True
    if resolved_cat == cat_key:
        return True
    text = f"{title} {summary}".lower()
    keywords = {
        "crypto": ["kripto", "crypto", "bitcoin", "btc", "solana", "ethereum", "blockchain", "aset digital", "web3"],
        "saham": ["ihsg", "saham", "bei", "emiten", "bursa", "dividen", "idx", "wall street", "indeks"],
        "emas": ["emas", "antam", "logam mulia", "pegadaian", "komoditas", "xau"],
        "ekonomi": ["ekonomi", "bank indonesia", "rupiah", "inflasi", "suku bunga", "pajak", "apbn", "fiskal", "impor", "ekspor", "investasi", "keuangan"],
        "teknologi": ["teknologi", "ai", "kecerdasan buatan", "digital", "startup", "siber", "internet", "aplikasi", "data", "chip"],
    }
    return any(k in text for k in keywords.get(cat_key, []))


def _parse_pub_date(pub_str: str, now_ts: int) -> tuple[str, int, str]:
    dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    if pub_str:
        try:
            parsed = parsedate_to_datetime(pub_str)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            dt = parsed
        except Exception:
            pass

    ts = int(dt.timestamp())
    if ts > now_ts:
        ts = now_ts
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)

    dt_wib = dt.astimezone(WIB_TZ)
    formatted_wib = f"{dt_wib.day:02d} {MONTHS_ID[dt_wib.month]} {dt_wib.year}, {dt_wib.strftime('%H:%M')} WIB"
    return dt.isoformat(), ts, formatted_wib


def _format_relative_time_id(timestamp_sec: int, now_sec: int) -> str:
    diff = max(0, now_sec - timestamp_sec)
    if diff < 60:
        return "Baru saja"
    if diff < 3600:
        return f"{diff // 60} menit lalu"
    if diff < 86400:
        return f"{diff // 3600} jam lalu"
    days = diff // 86400
    return f"{days} hari lalu"


def fetch_indonesian_news(
    category: str = "all",
    search_query: str | None = None,
    limit: int = 24,
    force_refresh: bool = False,
) -> dict:
    cat_key = (category or "all").lower().strip()
    if cat_key not in NEWS_CATEGORIES:
        cat_key = "all"

    cat_meta = NEWS_CATEGORIES[cat_key]
    custom_q = (search_query or "").strip()
    cache_key = f"{cat_key}:{custom_q.lower()}:{limit}"

    now_ts = int(time.time())
    if not force_refresh and cache_key in _NEWS_CACHE:
        cached = _NEWS_CACHE[cache_key]
        if now_ts - cached["fetched_ts"] < _CACHE_TTL_SEC:
            return cached["payload"]

    cutoff_ts = now_ts - MAX_AGE_SECONDS  # Batas maksimal 7 hari (1 minggu) terakhir

    effective_query = f"{cat_meta['query']} {custom_q}".strip() if custom_q else cat_meta["query"]
    encoded_q = urllib.parse.quote(effective_query)
    google_rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=id&gl=ID&ceid=ID:id"

    feed_sources: list[tuple[str, str, bool]] = []
    # 1. Direct Indonesian media RSS feeds (have native high-res <enclosure> thumbnails)
    if not custom_q:
        for pub_name, feed_url in cat_meta.get("direct_feeds", []):
            feed_sources.append((pub_name, feed_url, True))
    # 2. Google News Indonesia RSS feed (7-day window)
    feed_sources.append(("Media Finansial Indonesia", google_rss_url, False))

    articles: list[dict] = []
    seen_titles: set[str] = set()
    source_status = "live_rss_id"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    }

    with httpx.Client(timeout=8.0, follow_redirects=True, headers=headers) as client:
        for default_publisher, feed_url, is_direct_feed in feed_sources:
            try:
                resp = client.get(feed_url)
                if resp.status_code != 200:
                    continue
                root = ET.fromstring(resp.content)
                channel = root.find("channel")
                items = channel.findall("item") if channel is not None else []

                for item in items:
                    raw_title = (item.findtext("title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    pub_date_raw = (item.findtext("pubDate") or "").strip()
                    desc_raw = (item.findtext("description") or "").strip()

                    if not raw_title or not link or not pub_date_raw:
                        continue

                    pub_iso, pub_ts, formatted_wib = _parse_pub_date(pub_date_raw, now_ts)
                    # Filter: Paling lama seminggu (7 hari)
                    if pub_ts < cutoff_ts:
                        continue

                    source_el = item.find("source")
                    publisher = (source_el.text or "").strip() if source_el is not None else ""
                    publisher_url = (source_el.get("url") or "").strip() if source_el is not None else ""

                    clean_title = raw_title
                    if not is_direct_feed and " - " in raw_title:
                        parts = raw_title.rsplit(" - ", 1)
                        clean_title = parts[0].strip()
                        if not publisher:
                            publisher = parts[1].strip()

                    if not publisher:
                        publisher = default_publisher

                    norm_title = re.sub(r"[^a-z0-9]+", "", clean_title.lower())
                    if not norm_title or norm_title in seen_titles:
                        continue

                    clean_desc = _clean_html(desc_raw)
                    resolved_cat = _detect_category_from_text(clean_title, clean_desc)

                    # If coming from a general direct feed (like CNBC Market), ensure it matches the selected category
                    if is_direct_feed and not _matches_category(cat_key, resolved_cat, clean_title, clean_desc):
                        continue

                    if cat_key != "all":
                        resolved_cat = cat_key

                    seen_titles.add(norm_title)

                    clean_desc_clean = clean_desc.strip()
                    test_desc = re.sub(re.escape(clean_title), "", clean_desc_clean, flags=re.IGNORECASE).strip()
                    if publisher:
                        test_desc = re.sub(re.escape(publisher), "", test_desc, flags=re.IGNORECASE).strip()
                    test_desc = re.sub(r"^[\s\-\:\.\,]+|[\s\-\:\.\,]+$", "", test_desc).strip()

                    if not test_desc or len(test_desc) < 20:
                        cat_label = NEWS_CATEGORIES.get(resolved_cat, cat_meta)["label"]
                        clean_desc = (
                            f"Laporan {publisher} mengulas perkembangan seputar '{clean_title}' "
                            f"dan implikasinya terhadap tren pasar {cat_label}."
                        )

                    # Extract native RSS thumbnail or fallback to topic-matched high-res thumbnail
                    native_thumb = _extract_image_from_item(item, desc_raw)
                    image_url = native_thumb or _pick_fallback_thumbnail(resolved_cat, clean_title)

                    tag_info = _classify_article_tags(clean_title, clean_desc, resolved_cat)

                    articles.append(
                        {
                            "id": f"news-{resolved_cat}-{len(articles) + 1}-{abs(hash(link)) % 100000}",
                            "title": clean_title,
                            "summary": clean_desc[:240] + ("..." if len(clean_desc) > 240 else ""),
                            "url": link,
                            "image_url": image_url,
                            "has_native_thumbnail": bool(native_thumb),
                            "publisher": publisher,
                            "publisher_url": publisher_url or link,
                            "category": resolved_cat,
                            "category_label": NEWS_CATEGORIES.get(resolved_cat, cat_meta)["label"],
                            "sentiment": tag_info["sentiment"],
                            "sentiment_label": tag_info["sentiment_label"],
                            "tags": tag_info["tags"],
                            "published_at": pub_iso,
                            "published_ts": pub_ts,
                            "formatted_date": formatted_wib,
                            "relative_time": _format_relative_time_id(pub_ts, now_ts),
                        }
                    )
            except Exception:
                continue

    # Urutkan dari yang paling baru ke yang paling lama (strictly newest -> oldest)
    articles.sort(key=lambda x: x["published_ts"], reverse=True)
    articles = articles[:limit]

    payload = {
        "category": cat_key,
        "category_label": cat_meta["label"],
        "search_query": custom_q or None,
        "max_age_days": 7,
        "sort_order": "newest_first",
        "total": len(articles),
        "source_status": source_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "categories": [
            {
                "id": k,
                "label": v["label"],
                "badge": v["badge"],
            }
            for k, v in NEWS_CATEGORIES.items()
        ],
        "articles": articles,
    }

    if articles:
        _NEWS_CACHE[cache_key] = {
            "fetched_ts": now_ts,
            "payload": payload,
        }

    return payload
