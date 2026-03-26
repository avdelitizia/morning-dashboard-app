import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import urllib.request

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Morning Briefing",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.stApp { background-color: #0d1117; }
[data-testid="stAppViewContainer"] { background-color: #0d1117; }
[data-testid="stHeader"] { background-color: #0d1117; border-bottom: none; }
section[data-testid="stSidebar"] { background-color: #161b22; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 920px; }
#MainMenu, footer { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
.stSpinner > div { color: #58a6ff; }
.stButton > button {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 13px;
    font-family: system-ui, -apple-system, sans-serif;
}
.stButton > button:hover {
    background-color: #30363d;
    border-color: #58a6ff;
    color: #58a6ff;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
HOLDINGS = ["NVDA", "SOFI"]
NVDA_COMPS = ["AMD", "INTC", "AVGO", "TSM", "MRVL"]
SOFI_COMPS = ["HOOD", "LC", "PYPL", "SQ", "NU", "AFRM", "ALLY", "UPST"]
ALL_TRACKED = HOLDINGS + NVDA_COMPS + SOFI_COMPS
INDEX_MAP = {"SPY": "S&P 500", "QQQ": "Nasdaq", "^DJI": "DJIA", "^VIX": "VIX",
             "^TNX": "10-Yr", "^IRX": "3-Mo", "DX-Y.NYB": "DXY"}

AI_KEYWORDS = [
    "nvidia", "data center", "ai capex", "cloud spending", "infrastructure",
    "gpu", "compute", "blackwell", "ai investment", "hyperscaler",
    "microsoft azure", "google cloud", "aws", "chip"
]

COMPANY_NAMES = {
    "NVDA": "Nvidia", "SOFI": "SoFi", "AMD": "AMD", "INTC": "Intel",
    "AVGO": "Broadcom", "TSM": "TSMC", "MRVL": "Marvell", "HOOD": "Robinhood",
    "LC": "LendingClub", "PYPL": "PayPal", "SQ": "Block", "NU": "Nubank",
    "AFRM": "Affirm", "ALLY": "Ally Financial", "UPST": "Upstart",
}

SECTOR_MAP = {
    "NVDA": "Semiconductors", "AMD": "Semiconductors", "INTC": "Semiconductors",
    "AVGO": "Semiconductors", "TSM": "Semiconductors", "MRVL": "Semiconductors",
    "SOFI": "Fintech", "HOOD": "Fintech", "LC": "Fintech", "PYPL": "Fintech",
    "SQ": "Fintech", "NU": "Fintech", "AFRM": "Fintech", "ALLY": "Fintech",
    "UPST": "Fintech",
}

CREDIBLE_PUBLISHERS = [
    "reuters", "bloomberg", "cnbc", "wall street journal", "wsj", "financial times",
    "barron", "marketwatch", "seeking alpha", "the street", "motley fool", "benzinga",
    "yahoo finance", "forbes", "business insider", "associated press", "ap news",
    "investor's business daily", "ibd", "morningstar",
]

IMPACT_KEYWORDS = [
    "earnings", "revenue", "guidance", "beats", "misses", "acquisition", "merger",
    "analyst", "price target", "upgrade", "downgrade", "sec", "lawsuit", "settlement",
    "partnership", "contract", "deal", "dividend", "buyback", "ipo", "ceo", "cfo",
    "quarterly results", "annual results", "forecast", "outlook", "investigation",
    "fda", "regulatory", "raised", "lowered", "record", "first quarter", "second quarter",
    "third quarter", "fourth quarter", "q1", "q2", "q3", "q4", "full year",
]

COMPANY_NAME_KEYWORDS = {
    "NVDA": ["nvidia", "nvda"],
    "SOFI": ["sofi", "social finance"],
    "AMD": ["amd", "advanced micro"],
    "INTC": ["intel"],
    "AVGO": ["broadcom"],
    "TSM": ["tsmc", "taiwan semiconductor"],
    "MRVL": ["marvell"],
    "HOOD": ["robinhood"],
    "LC": ["lendingclub", "lending club"],
    "PYPL": ["paypal"],
    "SQ": ["block", "square"],
    "NU": ["nubank"],
    "AFRM": ["affirm"],
    "ALLY": ["ally"],
    "UPST": ["upstart"],
}

# ── Economic Calendar ─────────────────────────────────────────────────────────
# Sources:
#   FOMC dates  → https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
#   CPI dates   → https://www.bls.gov/schedule/news_release/cpi.htm
#   Jobs dates  → https://www.bls.gov/schedule/news_release/empsit.htm
#
# CONFIDENCE KEY:
#   HIGH   = official source confirmed / strict formula (first Friday, 2nd Wednesday)
#   VERIFY = pattern-based for 2026 — please cross-check at the URLs above
#
ECONOMIC_CALENDAR = [
    # ── FOMC Meeting Decision Dates (2nd day of each meeting) ──────────────────
    # Source: federalreserve.gov/monetarypolicy/fomccalendars.htm
    # * = press conference follows
    {"date": "2026-04-29", "type": "FOMC", "label": "Fed Rate Decision",                    "confidence": "HIGH"},
    {"date": "2026-06-17", "type": "FOMC", "label": "Fed Rate Decision + Press Conference", "confidence": "HIGH"},
    {"date": "2026-07-29", "type": "FOMC", "label": "Fed Rate Decision",                    "confidence": "HIGH"},
    {"date": "2026-09-16", "type": "FOMC", "label": "Fed Rate Decision + Press Conference", "confidence": "HIGH"},
    {"date": "2026-10-28", "type": "FOMC", "label": "Fed Rate Decision",                    "confidence": "HIGH"},
    {"date": "2026-12-09", "type": "FOMC", "label": "Fed Rate Decision + Press Conference", "confidence": "HIGH"},

    # ── CPI Release Dates (BLS, ~2nd Wednesday each month) ────────────────────
    # 2026 — HIGH confidence (BLS strict schedule), verify at bls.gov
    {"date": "2026-04-10", "type": "CPI",   "label": "CPI Inflation Report",     "confidence": "HIGH"},
    {"date": "2026-05-13", "type": "CPI",   "label": "CPI Inflation Report",     "confidence": "HIGH"},
    {"date": "2026-06-10", "type": "CPI",   "label": "CPI Inflation Report",     "confidence": "HIGH"},
    {"date": "2026-07-15", "type": "CPI",   "label": "CPI Inflation Report",     "confidence": "HIGH"},
    {"date": "2026-08-12", "type": "CPI",   "label": "CPI Inflation Report",     "confidence": "HIGH"},
    {"date": "2026-09-09", "type": "CPI",   "label": "CPI Inflation Report",     "confidence": "HIGH"},
    {"date": "2026-10-14", "type": "CPI",   "label": "CPI Inflation Report",     "confidence": "HIGH"},
    {"date": "2026-11-12", "type": "CPI",   "label": "CPI Inflation Report",     "confidence": "HIGH"},
    {"date": "2026-12-09", "type": "CPI",   "label": "CPI Inflation Report",     "confidence": "HIGH"},

    # ── Jobs Report / Employment Situation (BLS, 1st Friday each month) ───────
    # 2026 — HIGH confidence (strict first-Friday rule)
    {"date": "2026-04-03", "type": "JOBS",  "label": "Jobs Report",              "confidence": "HIGH"},
    {"date": "2026-05-01", "type": "JOBS",  "label": "Jobs Report",              "confidence": "HIGH"},
    {"date": "2026-06-05", "type": "JOBS",  "label": "Jobs Report",              "confidence": "HIGH"},
    {"date": "2026-07-02", "type": "JOBS",  "label": "Jobs Report",              "confidence": "HIGH"},
    {"date": "2026-08-07", "type": "JOBS",  "label": "Jobs Report",              "confidence": "HIGH"},
    {"date": "2026-09-04", "type": "JOBS",  "label": "Jobs Report",              "confidence": "HIGH"},
    {"date": "2026-10-02", "type": "JOBS",  "label": "Jobs Report",              "confidence": "HIGH"},
    {"date": "2026-11-06", "type": "JOBS",  "label": "Jobs Report",              "confidence": "HIGH"},
    {"date": "2026-12-04", "type": "JOBS",  "label": "Jobs Report",              "confidence": "HIGH"},
]

def importance_score(article):
    score = 0
    title_lower = article["title"].lower()
    publisher_lower = article.get("publisher", "").lower()

    # Publisher credibility (+3)
    if any(p in publisher_lower for p in CREDIBLE_PUBLISHERS):
        score += 3

    # High-impact keyword in title (+2 each, max +6)
    hits = sum(1 for k in IMPACT_KEYWORDS if k in title_lower)
    score += min(hits * 2, 6)

    # Company name explicitly in title (+3)
    primary = article.get("primary", "")
    names = COMPANY_NAME_KEYWORDS.get(primary, [])
    if any(n in title_lower for n in names):
        score += 3

    # Slight recency boost — newer articles within same score tier rank higher
    # Normalize published timestamp to 0-1 range within 48h window
    age_hours = (time.time() - article.get("published", 0)) / 3600
    recency_boost = max(0, (48 - age_hours) / 48)
    score += recency_boost

    return score

BULLISH_WORDS = [
    "beat", "beats", "surges", "surge", "record", "raises", "raised", "upgrade",
    "upgraded", "growth", "profit", "strong", "outperform", "rally", "gains",
    "gain", "rises", "rise", "jumps", "jump", "tops", "exceeds", "positive",
    "buy", "bullish", "boosts", "boost", "expands", "expansion", "wins", "win",
    "breakthrough", "higher", "increases", "increased", "milestone", "deal",
]
BEARISH_WORDS = [
    "miss", "misses", "missed", "falls", "fall", "drops", "drop", "cut", "cuts",
    "downgrade", "downgraded", "loss", "losses", "decline", "declines", "weak",
    "sell", "bearish", "warning", "warns", "concern", "risk", "risks", "lawsuit",
    "investigation", "recall", "layoffs", "lays off", "lower", "decreases",
    "decreased", "slows", "slowdown", "disappoints", "disappointing", "plunges",
    "plunge", "crashes", "crash", "fears", "trouble", "default", "tariff", "tariffs",
]

def article_sentiment(title):
    t = title.lower()
    bull = sum(1 for w in BULLISH_WORDS if w in t)
    bear = sum(1 for w in BEARISH_WORDS if w in t)
    if bull > bear:
        return ("Bullish", "#3fb950", "#0d2818")
    elif bear > bull:
        return ("Bearish", "#f85149", "#2d0f0e")
    return ("Neutral", "#8b949e", "#21262d")

def article_label(article):
    primary = article.get("primary", "")
    name = COMPANY_NAMES.get(primary, "")
    sector = SECTOR_MAP.get(primary, "Market")
    return name if name else sector

MACRO_KEYWORDS = [
    "federal reserve", "fed rate", "interest rate", "inflation", "cpi", "pce",
    "treasury yield", "bond yield", "recession", "gdp", "unemployment", "jobs report",
    "fomc", "jerome powell", "rate cut", "rate hike", "monetary policy", "tariff",
    "trade war", "economy", "economic outlook", "consumer spending", "retail sales"
]

# ── Badge Helpers ─────────────────────────────────────────────────────────────
def ticker_badge(symbol):
    if symbol == "NVDA":
        style = "background:#76b900;color:#000;"
    elif symbol == "SOFI":
        style = "background:#0a84ff;color:#fff;"
    else:
        style = "background:#30363d;color:#c9d1d9;"
    return (
        f'<span style="{style}padding:2px 7px;border-radius:4px;'
        f'font-size:11px;font-weight:700;margin-right:4px;'
        f'display:inline-block;">{symbol}</span>'
    )


def sentiment_badge(title):
    t = title.lower()
    bullish = [
        "beat", "beats", "surge", "surges", "rally", "rallies", "record",
        "rise", "rises", "gain", "gains", "boost", "upgraded", "soar",
        "strong", "growth", "top", "exceed", "exceeds", "outperform",
    ]
    bearish = [
        "miss", "misses", "fall", "falls", "decline", "declines", "drop",
        "drops", "cut", "warn", "loss", "losses", "weak", "downgrade",
        "concern", "risk", "slump",
    ]
    for w in bullish:
        if w in t:
            return '<span style="background:#238636;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;">BULLISH</span>'
    for w in bearish:
        if w in t:
            return '<span style="background:#da3633;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;">BEARISH</span>'
    return '<span style="background:#6e7681;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;">NEUTRAL</span>'


def category_label(tickers):
    if not tickers:
        return "MACRO"
    for t in tickers:
        if t in HOLDINGS:
            return "COMPANY"
    for t in tickers:
        if t in ALL_TRACKED:
            return "SECTOR"
    return "MACRO"


def pct_html(chg):
    color = "#3fb950" if chg >= 0 else "#f85149"
    arrow = "▲" if chg >= 0 else "▼"
    return f'<span style="color:{color};font-weight:600;">{arrow} {abs(chg):.2f}%</span>'


# ── Data Loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_prices():
    syms = ALL_TRACKED + list(INDEX_MAP.keys())
    data = {}
    for sym in syms:
        try:
            fi = yf.Ticker(sym).fast_info
            price = fi.last_price
            prev = fi.previous_close
            if price and prev and prev > 0:
                data[sym] = {
                    "price": price,
                    "prev_close": prev,
                    "change_pct": (price - prev) / prev * 100,
                }
        except Exception:
            pass
    return data


@st.cache_data(ttl=3600)
def load_fed_rate():
    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS"
        with urllib.request.urlopen(url, timeout=5) as resp:
            text = resp.read().decode()
        lines = [l for l in text.strip().split('\n') if l and not l.startswith('DATE')]
        last = lines[-1].split(',')
        return float(last[1]) if len(last) >= 2 else None
    except Exception:
        return None


@st.cache_data(ttl=600)
def load_news():
    all_news = []
    seen = set()
    cutoff = time.time() - 48 * 3600

    for sym in ALL_TRACKED:
        try:
            articles = yf.Ticker(sym).news or []
            for a in articles:
                # Support both old flat format and new nested content format
                content = a.get("content", a)
                title = content.get("title", "")
                if not title:
                    continue

                # URL
                canon = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
                url = canon.get("url", "") if isinstance(canon, dict) else ""
                if not url:
                    url = a.get("link", "")
                if not url or url in seen:
                    continue

                # Timestamp — new format uses ISO string, old uses unix int
                pub_raw = content.get("pubDate") or content.get("displayTime") or a.get("providerPublishTime", 0)
                if isinstance(pub_raw, str):
                    try:
                        ts = datetime.strptime(pub_raw, "%Y-%m-%dT%H:%M:%SZ").timestamp()
                    except Exception:
                        ts = 0
                else:
                    ts = float(pub_raw or 0)

                if ts < cutoff:
                    continue

                seen.add(url)

                # Publisher
                provider = content.get("provider", {})
                publisher = (
                    provider.get("displayName", "") if isinstance(provider, dict)
                    else a.get("publisher", "")
                )

                all_news.append({
                    "title": title,
                    "publisher": publisher,
                    "url": url,
                    "published": ts,
                    "tickers": [sym],   # tag with the ticker we fetched it for
                    "primary": sym,
                })
        except Exception:
            pass

    all_news.sort(key=importance_score, reverse=True)

    # Deduplicate by URL — merge tickers so cross-ticker articles are detected
    seen2 = {}
    deduped = []
    for a in all_news:
        if a["url"] not in seen2:
            seen2[a["url"]] = len(deduped)
            deduped.append(a)
        else:
            idx = seen2[a["url"]]
            deduped[idx]["tickers"] = list(set(deduped[idx]["tickers"] + a["tickers"]))
    return deduped


@st.cache_data(ttl=3600)
def load_earnings():
    from datetime import date as date_type
    results = []
    today = date_type.today()

    for sym in ALL_TRACKED:
        try:
            cal = yf.Ticker(sym).calendar
            if not cal:
                continue
            if isinstance(cal, dict):
                dates = cal.get("Earnings Date", [])
                if not isinstance(dates, list):
                    dates = [dates]
                # EPS: prefer Earnings Average, fall back to High
                eps = cal.get("Earnings Average") or cal.get("EPS Estimate") or cal.get("Earnings High")
                for d in dates:
                    if d and d >= today:
                        results.append({"ticker": sym, "date": d, "eps_est": eps})
                        break
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                row = cal.iloc[:, 0]
                d = row.get("Earnings Date")
                eps = row.get("EPS Estimate") or row.get("Earnings Average")
                if d:
                    results.append({"ticker": sym, "date": d, "eps_est": eps})
        except Exception:
            pass

    results.sort(key=lambda e: e["date"])
    return results[:12]


# ── Section Renderers ─────────────────────────────────────────────────────────
def render_header(now):
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#161b22 0%,#1c2128 50%,#0d1117 100%);
                border:1px solid #30363d;border-radius:12px;
                padding:32px 28px;margin-bottom:24px;text-align:center;
                font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
      <div style="color:#58a6ff;font-size:12px;font-weight:700;
                  letter-spacing:0.15em;margin-bottom:8px;">INVESTMENT DASHBOARD</div>
      <div style="color:#e6edf3;font-size:28px;font-weight:800;
                  letter-spacing:0.05em;margin-bottom:12px;">MORNING BRIEFING</div>
      <div style="color:#e6edf3;font-size:20px;font-weight:600;margin-bottom:6px;">
        {now.strftime("%Y-%m-%d")}
      </div>
      <div style="color:#6e7681;font-size:13px;">Updated at {now.strftime("%H:%M:%S")}</div>
      <div style="margin-top:16px;display:flex;justify-content:center;gap:12px;flex-wrap:wrap;">
        <span style="background:#76b900;color:#000;padding:4px 12px;
                     border-radius:6px;font-size:12px;font-weight:700;">NVDA</span>
        <span style="background:#0a84ff;color:#fff;padding:4px 12px;
                     border-radius:6px;font-size:12px;font-weight:700;">SOFI</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_market_snapshot(prices):
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;
                padding-bottom:10px;border-bottom:1px solid #30363d;
                font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
      <span style="font-size:20px;">📈</span>
      <h2 style="margin:0;color:#e6edf3;font-size:18px;font-weight:700;">Market Snapshot</h2>
      <span style="color:#6e7681;font-size:13px;">Live prices</span>
    </div>
    """, unsafe_allow_html=True)

    items = [
        ("NVDA", "NVDA", "#76b900", "#000"),
        ("SOFI", "SOFI", "#0a84ff", "#fff"),
        ("SPY", "S&P 500", "#30363d", "#c9d1d9"),
        ("QQQ", "Nasdaq", "#30363d", "#c9d1d9"),
        ("^DJI", "DJIA", "#30363d", "#c9d1d9"),
        ("^VIX", "VIX", "#30363d", "#c9d1d9"),
    ]
    cols = st.columns(6)
    for i, (sym, label, bg, fg) in enumerate(items):
        d = prices.get(sym, {})
        price = d.get("price", 0)
        chg = d.get("change_pct", 0)
        chg_color = "#3fb950" if chg >= 0 else "#f85149"
        arrow = "▲" if chg >= 0 else "▼"
        display_sym = "VIX" if sym == "^VIX" else "DJIA" if sym == "^DJI" else sym
        price_str = f"${price:,.2f}" if price else "—"
        with cols[i]:
            st.markdown(f"""
            <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                        padding:12px;text-align:center;margin-bottom:12px;
                        font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
              <div style="background:{bg};color:{fg};padding:2px 7px;border-radius:4px;
                          font-size:11px;font-weight:700;display:inline-block;margin-bottom:6px;">
                {display_sym}
              </div>
              <div style="color:#6e7681;font-size:11px;margin-bottom:4px;">{label}</div>
              <div style="color:#e6edf3;font-size:16px;font-weight:700;">{price_str}</div>
              <div style="color:{chg_color};font-size:12px;font-weight:600;">
                {arrow} {abs(chg):.2f}%
              </div>
            </div>
            """, unsafe_allow_html=True)


def render_summary(prices, news, fed_rate=None):
    nvda_p = prices.get("NVDA", {})
    sofi_p = prices.get("SOFI", {})
    spy_p  = prices.get("SPY", {})
    qqq_p  = prices.get("QQQ", {})
    dia_p  = prices.get("^DJI", {})
    vix_p  = prices.get("^VIX", {})

    HOLDINGS_SET = {"NVDA", "SOFI"}
    nvda_news  = [a for a in news if a["primary"] == "NVDA" and not (HOLDINGS_SET - {"NVDA"}) & set(a["tickers"])]
    sofi_news  = [a for a in news if a["primary"] == "SOFI" and not (HOLDINGS_SET - {"SOFI"}) & set(a["tickers"])]
    ai_news    = [a for a in news if any(k in a["title"].lower() for k in AI_KEYWORDS)]
    macro_news = [a for a in news if any(k in a["title"].lower() for k in MACRO_KEYWORDS)]

    tnx_val = prices.get("^TNX", {}).get("price")   # 10-yr yield
    irx_val = prices.get("^IRX", {}).get("price")   # 3-mo yield
    dxy_val = prices.get("DX-Y.NYB", {}).get("price")  # US dollar index

    def make_bullets(articles, n=3, max_len=100):
        items = articles[:n] if articles else []
        if not items:
            return '<li style="color:#6e7681;">No recent news</li>'
        return "".join(
            f'<li style="margin-bottom:5px;">{a["title"][:max_len]}{"…" if len(a["title"]) > max_len else ""}</li>'
            for a in items
        )

    def chg_span(p):
        chg = p.get("change_pct", 0)
        color = "#3fb950" if chg >= 0 else "#f85149"
        arrow = "▲" if chg >= 0 else "▼"
        return f'<span style="color:{color};font-weight:600;font-size:13px;">{arrow} {abs(chg):.2f}%</span>'

    # Section header
    st.markdown("""
    <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                padding:20px 28px 16px;margin-bottom:16px;
                font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
      <div style="display:flex;align-items:center;gap:10px;">
        <span style="font-size:20px;">⚡</span>
        <span style="color:#e6edf3;font-size:18px;font-weight:700;">Today's Summary</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    def rate_cell(label, val, suffix=""):
        val_str = f"{val:.2f}{suffix}" if val is not None else "—"
        return (f'<div style="display:flex;justify-content:space-between;padding:3px 0;">'
                f'<span style="color:#6e7681;font-size:12px;">{label}</span>'
                f'<span style="color:#e6edf3;font-weight:600;font-size:12px;">{val_str}</span></div>')

    # Row 1: NVDA + SOFI (flex so both cards stretch to equal height)
    st.markdown(f"""
    <div style="display:flex;gap:16px;margin-bottom:16px;
                font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
      <div style="flex:1;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
          <span style="background:#76b900;color:#000;padding:2px 8px;border-radius:4px;
                       font-size:11px;font-weight:700;">NVDA</span>
          <span style="color:#e6edf3;font-size:18px;font-weight:700;">${nvda_p.get("price", 0):,.2f}</span>
          {chg_span(nvda_p)}
        </div>
        <ul style="margin:0;padding-left:16px;color:#c9d1d9;font-size:12px;line-height:1.7;">
          {make_bullets(nvda_news)}
        </ul>
      </div>
      <div style="flex:1;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
          <span style="background:#0a84ff;color:#fff;padding:2px 8px;border-radius:4px;
                       font-size:11px;font-weight:700;">SOFI</span>
          <span style="color:#e6edf3;font-size:18px;font-weight:700;">${sofi_p.get("price", 0):,.2f}</span>
          {chg_span(sofi_p)}
        </div>
        <ul style="margin:0;padding-left:16px;color:#c9d1d9;font-size:12px;line-height:1.7;">
          {make_bullets(sofi_news)}
        </ul>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Row 2: MACRO + AI CAPEX (flex so both cards stretch to equal height)
    st.markdown(f"""
    <div style="display:flex;gap:16px;
                font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
      <div style="flex:1;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;">
        <span style="background:#6e7681;color:#fff;padding:2px 8px;border-radius:4px;
                     font-size:11px;font-weight:700;">MACRO</span>
        <div style="margin-top:10px;">
          {rate_cell("Fed Funds Rate", fed_rate, "%")}
          {rate_cell("10-Yr Treasury Yield", tnx_val, "%")}
          {rate_cell("3-Mo Treasury Yield", irx_val, "%")}
          {rate_cell("US Dollar Index (DXY)", dxy_val)}
        </div>
        <div style="border-top:1px solid #21262d;margin-top:10px;padding-top:8px;">
          <ul style="margin:0;padding-left:16px;color:#c9d1d9;font-size:12px;line-height:1.7;">
            {make_bullets(macro_news, n=2, max_len=100)}
          </ul>
        </div>
      </div>
      <div style="flex:1;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;">
        <span style="background:#8b5cf6;color:#fff;padding:2px 8px;border-radius:4px;
                     font-size:11px;font-weight:700;">AI CAPEX</span>
        <ul style="margin:8px 0 0;padding-left:16px;color:#c9d1d9;font-size:12px;line-height:1.7;">
          {make_bullets(ai_news)}
        </ul>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Also in the news
    other_items = news[5:20]
    if other_items:
        rows = ""
        for a in other_items:
            label = article_label(a)
            sentiment, s_color, s_bg = article_sentiment(a["title"])
            url = a.get("url", "#")
            rows += (
                f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
                f'style="display:flex;align-items:baseline;gap:6px;'
                f'padding:6px 0;border-bottom:1px solid #21262d;'
                f'text-decoration:none;cursor:pointer;">'
                f'<span style="background:#30363d;color:#c9d1d9;padding:1px 6px;border-radius:4px;'
                f'font-size:10px;font-weight:700;white-space:nowrap;">{label}</span>'
                f'<span style="background:{s_bg};color:{s_color};padding:1px 6px;border-radius:4px;'
                f'font-size:10px;font-weight:700;white-space:nowrap;">{sentiment}</span>'
                f'<span style="color:#8b949e;font-size:12px;line-height:1.5;">{a["title"]}</span>'
                f'</a>'
            )
        st.markdown(f"""
        <div style="margin-top:16px;background:#161b22;border:1px solid #30363d;
                    border-radius:8px;padding:16px 20px 8px;margin-bottom:24px;
                    font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
          <div style="color:#6e7681;font-size:11px;font-weight:700;letter-spacing:0.1em;
                      margin-bottom:4px;">ALSO IN THE NEWS</div>
          {rows}
        </div>
        """, unsafe_allow_html=True)


def render_news(news):
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;
                padding-bottom:10px;border-bottom:1px solid #30363d;
                font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
      <span style="font-size:20px;">📰</span>
      <h2 style="margin:0;color:#e6edf3;font-size:18px;font-weight:700;">Market & News</h2>
      <span style="color:#6e7681;font-size:13px;">Last 48 hours</span>
    </div>
    """, unsafe_allow_html=True)

    top5 = news[:5]
    if not top5:
        st.markdown(
            '<div style="color:#6e7681;font-size:13px;padding:16px;">No recent news found.</div>',
            unsafe_allow_html=True,
        )
        return

    for article in top5:
        title = article["title"]
        url = article["url"]
        publisher = article["publisher"]
        ts = article["published"]
        tickers = article["tickers"]

        time_str = (
            datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "Unknown"
        )

        # Build ticker badges (show only tracked tickers)
        tracked_tickers = [t for t in tickers if t in ALL_TRACKED][:3]
        if tracked_tickers:
            badges = "".join(ticker_badge(t) for t in tracked_tickers)
        else:
            badges = '<span style="background:#30363d;color:#c9d1d9;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:700;margin-right:4px;display:inline-block;">MACRO</span>'

        cat = category_label(tickers)
        sent = sentiment_badge(title)

        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                    padding:16px;margin-bottom:12px;
                    font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
          <div style="display:flex;justify-content:space-between;
                      align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:8px;">
            <div>{badges}</div>
            <div style="display:flex;gap:8px;align-items:center;">
              <span style="color:#8b949e;font-size:11px;text-transform:uppercase;
                           letter-spacing:0.05em;">{cat}</span>
              {sent}
            </div>
          </div>
          <div style="color:#e6edf3;font-weight:700;font-size:14px;
                      margin-bottom:6px;line-height:1.4;">{title}</div>
          <div style="color:#6e7681;font-size:11px;margin-bottom:8px;">
            🕐 {time_str} &nbsp;·&nbsp; {publisher}
          </div>
          <a href="{url}" target="_blank"
             style="color:#58a6ff;font-size:12px;text-decoration:none;">Read more →</a>
        </div>
        """, unsafe_allow_html=True)


def render_earnings(earnings_data):
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;
                padding-bottom:10px;border-bottom:1px solid #30363d;
                font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
      <span style="font-size:20px;">📅</span>
      <h2 style="margin:0;color:#e6edf3;font-size:18px;font-weight:700;">Earnings Calendar</h2>
      <span style="color:#6e7681;font-size:13px;">Upcoming</span>
    </div>
    """, unsafe_allow_html=True)

    if not earnings_data:
        st.markdown(
            '<div style="color:#6e7681;font-size:13px;padding:8px 0 24px;">No upcoming earnings data available.</div>',
            unsafe_allow_html=True,
        )
        return

    rows = ""
    for e in earnings_data:
        sym = e["ticker"]
        badge = ticker_badge(sym)
        try:
            date_str = e["date"].strftime("%Y-%m-%d")
        except Exception:
            try:
                date_str = pd.Timestamp(e["date"]).strftime("%Y-%m-%d")
            except Exception:
                date_str = str(e["date"])[:10]
        eps = e.get("eps_est")
        eps_str = f"${eps:.2f}" if eps is not None else "—"
        eps_color = "#3fb950" if eps and eps > 0 else "#8b949e"
        rows += f"""
          <tr style="border-bottom:1px solid #21262d;">
            <td style="padding:6px 12px;width:90px;">{badge}</td>
            <td style="padding:6px 12px;color:#e6edf3;font-size:12px;">{date_str}</td>
            <td style="padding:6px 12px;color:{eps_color};font-weight:600;font-size:12px;">{eps_str}</td>
          </tr>"""

    st.markdown(f"""
    <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                overflow:hidden;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;
                margin-bottom:24px;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#0d1117;border-bottom:1px solid #30363d;">
            <th style="padding:6px 12px;text-align:left;color:#6e7681;font-weight:600;font-size:11px;width:90px;">TICKER</th>
            <th style="padding:6px 12px;text-align:left;color:#6e7681;font-weight:600;font-size:11px;">DATE</th>
            <th style="padding:6px 12px;text-align:left;color:#6e7681;font-weight:600;font-size:11px;">EPS EST.</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """, unsafe_allow_html=True)


def render_economic_calendar(now):
    today = now.date()
    upcoming = []
    for e in ECONOMIC_CALENDAR:
        d = datetime.strptime(e["date"], "%Y-%m-%d").date()
        if d >= today:
            days_away = (d - today).days
            upcoming.append({**e, "days_away": days_away, "date_obj": d})
    upcoming.sort(key=lambda x: x["date_obj"])
    upcoming = upcoming[:12]  # show next 12 events

    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;
                padding-bottom:10px;border-bottom:1px solid #30363d;
                font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
      <span style="font-size:20px;">🏛️</span>
      <h2 style="margin:0;color:#e6edf3;font-size:18px;font-weight:700;">Economic Calendar</h2>
      <span style="color:#6e7681;font-size:13px;">Upcoming events</span>
    </div>
    """, unsafe_allow_html=True)

    if not upcoming:
        st.markdown('<div style="color:#6e7681;font-size:13px;padding:8px 0 24px;">No upcoming events.</div>', unsafe_allow_html=True)
        return

    TYPE_STYLES = {
        "FOMC": ("background:#d97706;color:#000;", "Fed Meeting"),
        "CPI":  ("background:#0a84ff;color:#fff;", "Inflation"),
        "JOBS": ("background:#3fb950;color:#000;", "Employment"),
    }

    rows = ""
    for e in upcoming:
        badge_style, _ = TYPE_STYLES.get(e["type"], ("background:#30363d;color:#c9d1d9;", ""))
        date_fmt = e["date_obj"].strftime("%b %d, %Y")
        days = e["days_away"]
        days_str = "Today" if days == 0 else f"In {days}d"
        days_color = "#f85149" if days <= 3 else "#e6edf3" if days <= 14 else "#6e7681"
        verify = ""
        rows += f"""
          <tr style="border-bottom:1px solid #21262d;">
            <td style="padding:6px 12px;">
              <span style="{badge_style}padding:1px 7px;border-radius:4px;font-size:10px;font-weight:700;">{e["type"]}</span>
            </td>
            <td style="padding:6px 12px;color:#e6edf3;font-size:12px;">{e["label"]}{verify}</td>
            <td style="padding:6px 12px;color:#e6edf3;font-size:12px;">{date_fmt}</td>
            <td style="padding:6px 12px;color:{days_color};font-size:12px;font-weight:600;text-align:right;">{days_str}</td>
          </tr>"""

    st.markdown(f"""
    <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                overflow:hidden;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;
                margin-bottom:8px;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#0d1117;border-bottom:1px solid #30363d;">
            <th style="padding:6px 12px;text-align:left;color:#6e7681;font-weight:600;font-size:11px;width:70px;">TYPE</th>
            <th style="padding:6px 12px;text-align:left;color:#6e7681;font-weight:600;font-size:11px;">EVENT</th>
            <th style="padding:6px 12px;text-align:left;color:#6e7681;font-weight:600;font-size:11px;">DATE</th>
            <th style="padding:6px 12px;text-align:right;color:#6e7681;font-weight:600;font-size:11px;">COUNTDOWN</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <div style="margin-bottom:24px;"></div>
    """, unsafe_allow_html=True)


def render_footer():
    st.markdown("""
    <div style="border-top:1px solid #21262d;padding-top:16px;text-align:center;margin-top:8px;
                font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
      <p style="color:#6e7681;font-size:11px;margin:0;line-height:1.6;">
        Morning Briefing Dashboard &nbsp;|&nbsp;
        Data via Yahoo Finance (yfinance) &nbsp;|&nbsp;
        Not financial advice
      </p>
    </div>
    """, unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    est = timezone(timedelta(hours=-4))  # EDT (UTC-4); becomes -5 in winter (EST)
    now = datetime.now(est)

    # Refresh button top-right
    st.markdown('<div style="height:40px;"></div>', unsafe_allow_html=True)
    _, btn_col = st.columns([6, 2])
    with btn_col:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("Loading market data..."):
        prices = load_prices()
        news = load_news()
        earnings = load_earnings()
        fed_rate = load_fed_rate()

    render_header(now)
    render_market_snapshot(prices)
    st.markdown("<br>", unsafe_allow_html=True)
    render_summary(prices, news, fed_rate)
    render_news(news)
    st.markdown("<br>", unsafe_allow_html=True)
    render_earnings(earnings)
    render_economic_calendar(now)
    render_footer()


if __name__ == "__main__":
    main()
