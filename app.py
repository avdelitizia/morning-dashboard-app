import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone
import time

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
INDEX_MAP = {"SPY": "S&P 500", "QQQ": "Nasdaq", "^DJI": "DJIA", "^VIX": "VIX"}

AI_KEYWORDS = [
    "nvidia", "data center", "ai capex", "cloud spending", "infrastructure",
    "gpu", "compute", "blackwell", "ai investment", "hyperscaler",
    "microsoft azure", "google cloud", "aws", "chip"
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

    all_news.sort(key=lambda x: x["published"], reverse=True)

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


def render_summary(prices, news):
    nvda_p = prices.get("NVDA", {})
    sofi_p = prices.get("SOFI", {})
    spy_p  = prices.get("SPY", {})
    qqq_p  = prices.get("QQQ", {})
    dia_p  = prices.get("^DJI", {})
    vix_p  = prices.get("^VIX", {})

    HOLDINGS_SET = {"NVDA", "SOFI"}
    nvda_news = [a for a in news if a["primary"] == "NVDA" and not (HOLDINGS_SET - {"NVDA"}) & set(a["tickers"])]
    sofi_news = [a for a in news if a["primary"] == "SOFI" and not (HOLDINGS_SET - {"SOFI"}) & set(a["tickers"])]
    ai_news   = [a for a in news if any(k in a["title"].lower() for k in AI_KEYWORDS)]

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
    <div style="background:#161b22;border:1px solid #30363d;border-radius:12px 12px 0 0;
                padding:20px 28px 16px;border-bottom:1px solid #30363d;
                font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
      <div style="display:flex;align-items:center;gap:10px;">
        <span style="font-size:20px;">⚡</span>
        <span style="color:#e6edf3;font-size:18px;font-weight:700;">Today's Summary</span>
        <span style="color:#6e7681;font-size:13px;">Key data at a glance</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 4 boxes via st.columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #30363d;border-left:1px solid #30363d;
                    padding:14px;min-height:130px;
                    font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
          <span style="background:#76b900;color:#000;padding:2px 8px;border-radius:4px;
                       font-size:11px;font-weight:700;">NVDA</span>
          <div style="color:#e6edf3;font-size:20px;font-weight:700;margin:8px 0 2px;">
            ${nvda_p.get("price", 0):,.2f}
          </div>
          {chg_span(nvda_p)}
          <ul style="margin:8px 0 0;padding-left:16px;color:#c9d1d9;font-size:12px;line-height:1.6;">
            {make_bullets(nvda_news)}
          </ul>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #30363d;
                    padding:14px;min-height:130px;
                    font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
          <span style="background:#0a84ff;color:#fff;padding:2px 8px;border-radius:4px;
                       font-size:11px;font-weight:700;">SOFI</span>
          <div style="color:#e6edf3;font-size:20px;font-weight:700;margin:8px 0 2px;">
            ${sofi_p.get("price", 0):,.2f}
          </div>
          {chg_span(sofi_p)}
          <ul style="margin:8px 0 0;padding-left:16px;color:#c9d1d9;font-size:12px;line-height:1.6;">
            {make_bullets(sofi_news)}
          </ul>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        spy_chg  = spy_p.get("change_pct", 0)
        qqq_chg  = qqq_p.get("change_pct", 0)
        dia_chg  = dia_p.get("change_pct", 0)
        vix_val  = vix_p.get("price", 0)
        def row(label, chg):
            c = "#3fb950" if chg >= 0 else "#f85149"
            a = "▲" if chg >= 0 else "▼"
            return (f'<div style="display:flex;justify-content:space-between;margin-bottom:5px;">'
                    f'<span style="color:#6e7681;">{label}</span>'
                    f'<span style="color:{c};font-weight:600;">{a} {abs(chg):.2f}%</span></div>')
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #30363d;
                    padding:14px;min-height:130px;
                    font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
          <span style="background:#6e7681;color:#fff;padding:2px 8px;border-radius:4px;
                       font-size:11px;font-weight:700;">MACRO</span>
          <div style="margin-top:12px;font-size:13px;">
            {row("S&amp;P 500", spy_chg)}
            {row("Nasdaq", qqq_chg)}
            {row("Dow Jones", dia_chg)}
            <div style="display:flex;justify-content:space-between;margin-top:2px;">
              <span style="color:#6e7681;">VIX</span>
              <span style="color:#e6edf3;font-weight:600;">{vix_val:.2f}</span>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #30363d;border-right:1px solid #30363d;
                    padding:14px;min-height:130px;
                    font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
          <span style="background:#8b5cf6;color:#fff;padding:2px 8px;border-radius:4px;
                       font-size:11px;font-weight:700;">AI CAPEX</span>
          <ul style="margin:8px 0 0;padding-left:16px;color:#c9d1d9;font-size:12px;line-height:1.6;">
            {make_bullets(ai_news)}
          </ul>
        </div>
        """, unsafe_allow_html=True)

    # Also in the news
    other_items = news[5:20]
    if other_items:
        bullets = "".join(f"<li>{a['title']}</li>" for a in other_items)
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #30363d;border-top:none;
                    border-radius:0 0 12px 12px;padding:16px 28px 20px;margin-bottom:24px;
                    font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
          <div style="color:#6e7681;font-size:11px;font-weight:700;letter-spacing:0.1em;
                      margin-bottom:8px;">ALSO IN THE NEWS</div>
          <ul style="margin:0;padding-left:18px;color:#8b949e;font-size:13px;line-height:1.8;">
            {bullets}
          </ul>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:#161b22;border:1px solid #30363d;border-top:none;border-radius:0 0 12px 12px;height:12px;margin-bottom:24px;"></div>', unsafe_allow_html=True)


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

    # Table header
    st.markdown("""
    <div style="background:#161b22;border:1px solid #30363d;border-radius:8px 8px 0 0;
                overflow:hidden;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
          <tr style="background:#0d1117;border-bottom:1px solid #30363d;">
            <th style="padding:10px 14px;text-align:left;color:#6e7681;font-weight:600;width:100px;">TICKER</th>
            <th style="padding:10px 14px;text-align:left;color:#6e7681;font-weight:600;">DATE</th>
            <th style="padding:10px 14px;text-align:left;color:#6e7681;font-weight:600;">EPS EST.</th>
          </tr>
        </thead>
      </table>
    </div>
    """, unsafe_allow_html=True)

    # One row per entry
    for i, e in enumerate(earnings_data):
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
        radius = "border-radius:0 0 8px 8px;" if i == len(earnings_data) - 1 else ""
        border_bottom = "" if i == len(earnings_data) - 1 else "border-bottom:1px solid #21262d;"

        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #30363d;border-top:none;{radius}
                    font-family:system-ui,-apple-system,'Segoe UI',sans-serif;">
          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <tr style="{border_bottom}">
              <td style="padding:10px 14px;width:100px;">{badge}</td>
              <td style="padding:10px 14px;color:#e6edf3;">{date_str}</td>
              <td style="padding:10px 14px;color:{eps_color};font-weight:600;">{eps_str}</td>
            </tr>
          </table>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)


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

    render_header(now)
    render_market_snapshot(prices)
    st.markdown("<br>", unsafe_allow_html=True)
    render_summary(prices, news)
    render_news(news)
    st.markdown("<br>", unsafe_allow_html=True)
    render_earnings(earnings)
    render_footer()


if __name__ == "__main__":
    main()
