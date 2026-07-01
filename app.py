from __future__ import annotations

import html
import os
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

import config
from core import (
    RECOMMENDATION_BUY,
    RECOMMENDATION_NEGATIVE,
    RECOMMENDATION_STRONG_BUY,
    RECOMMENDATION_WATCH,
    add_favorite,
    analyze_symbol_news,
    article_message,
    calculate_statistics,
    daily_openai_status,
    development_dashboard,
    enrich_article_for_display,
    export_all_development_txt,
    export_pending_development_txt,
    favorite_rows,
    fetch_news,
    format_saudi_time,
    generate_daily_development_review,
    is_favorite,
    is_positive,
    load_account,
    load_control,
    load_daily_reviews,
    load_favorites,
    load_improvements,
    load_json,
    mark_improvement_status,
    process_articles,
    record_signals_batch,
    remove_favorite,
    save_account,
    save_json,
    set_favorite_reviewed,
    signal_mismatch_reason,
    signal_recommendation,
    signal_result,
    telegram_send,
    update_control,
    update_signal_outcomes,
    usage_totals,
)
from monitor_worker import run as run_monitor_worker

RIYADH = ZoneInfo("Asia/Riyadh")

st.set_page_config(
    page_title="برق — Sprint 10",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def start_background_worker():
    thread = threading.Thread(
        target=run_monitor_worker,
        daemon=True,
        name="barq-monitor-worker",
    )
    thread.start()
    return thread


if os.getenv("BARQ_DISABLE_WORKER") != "1":
    start_background_worker()

st.markdown(
    """
    <style>
    :root {
      --bg:#f6f8fc;
      --panel:#ffffff;
      --panel-2:#fbfcfe;
      --line:#e5eaf2;
      --line-strong:#d9e0eb;
      --text:#121a2d;
      --muted:#748096;
      --blue:#1268e8;
      --blue-soft:#edf4ff;
      --green:#10a857;
      --green-soft:#eaf8f0;
      --red:#e74848;
      --red-soft:#fff0f0;
      --orange:#ee9815;
      --orange-soft:#fff5e4;
      --purple:#6d55d9;
      --shadow:0 10px 30px rgba(31,48,79,.055);
      --shadow-soft:0 4px 16px rgba(31,48,79,.04);
      --radius:18px;
    }

    * { box-sizing:border-box; }

    html, body, [class*="css"] {
      direction:rtl;
      text-align:right;
      font-family:"Segoe UI",Tahoma,Arial,sans-serif;
    }

    body { background:var(--bg); }

    .stApp {
      background:
        radial-gradient(circle at 82% -15%, rgba(18,104,232,.06), transparent 34%),
        var(--bg);
      color:var(--text);
    }

    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    #MainMenu,
    footer { display:none!important; }

    .block-container {
      max-width:1420px;
      padding:22px 30px 92px;
    }

    h1,h2,h3,h4,p,label,span,div { color:var(--text); }
    h2, h3 { letter-spacing:-.2px; }

    /* Sidebar */
    [data-testid="stAppViewContainer"] {
      direction:rtl!important;
    }

    [data-testid="stAppViewContainer"] > .main {
      order:1;
    }

    [data-testid="stSidebar"] {
      order:2;
      background:#fff;
      border-left:0;
      border-right:1px solid var(--line);
      box-shadow:8px 0 30px rgba(30,45,75,.025);
    }

    [data-testid="stSidebarCollapsedControl"] {
      left:auto!important;
      right:10px!important;
    }

    [data-testid="stSidebar"] > div:first-child {
      padding:20px 14px 24px;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label {
      width:100%;
      min-height:48px;
      padding:0 14px;
      margin:3px 0;
      border-radius:12px;
      transition:.18s ease;
      font-weight:800;
      color:#243047!important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
      background:#f6f8fb;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
      background:var(--blue-soft);
      color:var(--blue)!important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p {
      color:var(--blue)!important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] input {
      display:none!important;
    }

    .brand {
      display:flex;
      align-items:center;
      justify-content:flex-start;
      gap:9px;
      font-size:29px;
      font-weight:950;
      letter-spacing:-1px;
      padding:4px 10px 16px;
    }

    .brand .bolt {
      color:#ffae00!important;
      font-size:34px;
      filter:drop-shadow(0 4px 7px rgba(255,174,0,.22));
    }

    .sidebar-card {
      border:1px solid var(--line);
      background:var(--panel-2);
      border-radius:14px;
      padding:12px;
      margin-top:16px;
    }

    .sidebar-card .small {
      font-size:10px;
      color:var(--muted)!important;
      margin-bottom:5px;
    }

    .sidebar-card .strong {
      font-weight:900;
      font-size:12px;
    }

    /* Top */
    .top-shell {
      display:flex;
      align-items:flex-start;
      justify-content:space-between;
      gap:18px;
      padding:4px 2px 18px;
      border-bottom:1px solid var(--line);
      margin-bottom:18px;
    }

    .top-title-wrap {
      display:flex;
      gap:12px;
      align-items:center;
    }

    .page-icon {
      width:43px;
      height:43px;
      display:grid;
      place-items:center;
      border-radius:13px;
      background:var(--blue-soft);
      color:var(--blue)!important;
      font-size:21px;
      font-weight:900;
    }

    .page-title {
      font-size:27px;
      line-height:1.1;
      font-weight:950;
      margin:0;
      letter-spacing:-.7px;
    }

    .page-sub {
      color:var(--muted)!important;
      font-size:12px;
      margin-top:6px;
    }

    .top-meta {
      display:flex;
      align-items:center;
      gap:9px;
      flex-wrap:wrap;
      justify-content:flex-end;
    }

    .live {
      display:inline-flex;
      align-items:center;
      gap:7px;
      color:var(--green)!important;
      font-weight:900;
      font-size:11px;
      padding:8px 11px;
      border:1px solid #cdeed9;
      border-radius:999px;
      background:#f2fbf5;
    }

    .live.off {
      color:var(--muted)!important;
      background:#fff;
      border-color:var(--line);
    }

    .dot {
      width:7px;
      height:7px;
      border-radius:50%;
      background:currentColor;
      display:inline-block;
    }

    .last-update {
      font-size:10px;
      color:var(--muted)!important;
      padding:8px 10px;
      border-radius:999px;
      border:1px solid var(--line);
      background:#fff;
    }

    /* Metrics */
    .metrics-2,
    .metrics-4 {
      display:grid;
      gap:14px;
      margin:14px 0 20px;
    }

    .metrics-2 { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .metrics-4 { grid-template-columns:repeat(4,minmax(0,1fr)); }

    .metric-card {
      position:relative;
      overflow:hidden;
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:var(--radius);
      padding:20px 20px 18px;
      min-height:128px;
      box-shadow:var(--shadow);
    }

    .metric-card::before {
      content:"";
      position:absolute;
      inset:auto -28px -46px auto;
      width:105px;
      height:105px;
      border-radius:50%;
      opacity:.5;
      background:var(--blue-soft);
    }

    .metric-card.positive::before { background:var(--green-soft); }
    .metric-card.negative::before { background:var(--red-soft); }
    .metric-card.pending::before { background:var(--orange-soft); }

    .metric-card .metric-icon {
      width:38px;
      height:38px;
      display:grid;
      place-items:center;
      border-radius:50%;
      background:var(--blue-soft);
      color:var(--blue)!important;
      font-weight:950;
      font-size:17px;
      margin-bottom:10px;
    }

    .metric-card.positive .metric-icon { background:var(--green-soft); color:var(--green)!important; }
    .metric-card.negative .metric-icon { background:var(--red-soft); color:var(--red)!important; }
    .metric-card.pending .metric-icon { background:var(--orange-soft); color:var(--orange)!important; }

    .metric-card .label {
      color:#4c5870!important;
      font-size:12px;
      font-weight:800;
      margin-bottom:7px;
    }

    .metric-card .value {
      position:relative;
      z-index:1;
      font-size:33px;
      font-weight:950;
      line-height:1;
    }

    .metric-card .hint {
      position:relative;
      z-index:1;
      color:var(--muted)!important;
      font-size:10px;
      margin-top:9px;
    }

    .positive .value { color:var(--green)!important; }
    .negative .value { color:var(--red)!important; }
    .pending .value { color:var(--orange)!important; }
    .processed .value { color:var(--blue)!important; }

    /* Panels and controls */
    .section,
    [data-testid="stVerticalBlockBorderWrapper"] {
      background:var(--panel);
      border:1px solid var(--line)!important;
      border-radius:var(--radius)!important;
      box-shadow:var(--shadow-soft);
    }

    [data-testid="stVerticalBlockBorderWrapper"] > div {
      padding:14px!important;
    }

    [data-baseweb="select"] > div,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
      background:#fff!important;
      border-color:var(--line-strong)!important;
      border-radius:11px!important;
      min-height:43px!important;
      box-shadow:none!important;
    }

    [data-testid="stCheckbox"] label {
      font-size:12px!important;
      font-weight:800!important;
    }

    .stButton button,
    .stDownloadButton button,
    .stLinkButton a {
      border-radius:11px!important;
      min-height:40px!important;
      padding:0 14px!important;
      font-size:12px!important;
      font-weight:900!important;
      border:1px solid var(--line-strong)!important;
      background:#fff!important;
      color:#263249!important;
      box-shadow:none!important;
      transition:.18s ease!important;
    }

    .stButton button:hover,
    .stDownloadButton button:hover,
    .stLinkButton a:hover {
      transform:translateY(-1px);
      border-color:#bfd0ea!important;
      background:#f9fbff!important;
    }

    .stButton button[kind="primary"],
    .stDownloadButton button[kind="primary"] {
      background:var(--blue)!important;
      color:#fff!important;
      border-color:var(--blue)!important;
      box-shadow:0 8px 18px rgba(18,104,232,.18)!important;
    }

    /* Legend */
    .legend {
      display:flex;
      gap:8px;
      flex-wrap:wrap;
      margin:4px 0 14px;
    }

    .legend-item {
      display:inline-flex;
      align-items:center;
      gap:6px;
      padding:7px 10px;
      background:#fff;
      border:1px solid var(--line);
      border-radius:10px;
      color:#4f5b70!important;
      font-size:10px;
      font-weight:800;
    }

    .legend-dot { width:7px; height:7px; border-radius:50%; display:inline-block; }

    /* Table */
    .table-head,
    .news-grid {
      display:grid;
      grid-template-columns:105px 115px minmax(300px,1fr) 105px 70px;
      gap:14px;
      align-items:center;
    }

    .table-head {
      background:#fafbfd;
      border:1px solid var(--line);
      border-radius:13px 13px 8px 8px;
      padding:12px 15px;
      margin-top:10px;
      position:sticky;
      top:8px;
      z-index:6;
      box-shadow:0 4px 14px rgba(30,45,75,.035);
    }

    .table-head span {
      color:#5f6b80!important;
      font-size:10px;
      font-weight:900;
    }

    .news-row {
      background:#fff;
      border:1px solid var(--line);
      border-radius:12px;
      padding:14px 15px;
      margin:6px 0;
      box-shadow:0 2px 10px rgba(31,48,79,.025);
      transition:.18s ease;
    }

    .news-row:hover {
      border-color:#cdd8e8;
      box-shadow:0 8px 24px rgba(31,48,79,.055);
      transform:translateY(-1px);
    }

    .symbol {
      font-weight:950;
      color:var(--blue)!important;
      font-size:13px;
      direction:ltr;
      text-align:right;
    }

    .company-note {
      color:var(--muted)!important;
      font-size:9px;
      margin-top:3px;
    }

    .title-ar {
      font-weight:850;
      line-height:1.55;
      font-size:13px;
    }

    .time {
      color:#3d485d!important;
      font-size:11px;
      font-weight:750;
    }

    .time small {
      display:block;
      color:var(--muted)!important;
      font-size:9px;
      margin-top:3px;
    }

    .score {
      font-size:22px;
      font-weight:950;
      text-align:center;
    }

    .score.strong,.score.buy { color:var(--green)!important; }
    .score.watch { color:var(--orange)!important; }
    .score.negative { color:var(--red)!important; }

    .badge {
      display:inline-flex;
      justify-content:center;
      min-width:76px;
      border-radius:9px;
      padding:7px 10px;
      font-size:10px;
      font-weight:950;
      white-space:nowrap;
    }

    .badge.strong,.badge.buy { color:var(--green)!important; background:var(--green-soft); }
    .badge.watch { color:var(--orange)!important; background:var(--orange-soft); }
    .badge.negative { color:var(--red)!important; background:var(--red-soft); }

    .mini {
      color:var(--muted)!important;
      font-size:10px;
      margin-top:5px;
      line-height:1.5;
    }

    .row-actions {
      margin:-2px 0 8px;
      padding:0 6px;
    }

    .row-actions .stButton button,
    .row-actions .stLinkButton a {
      min-height:32px!important;
      font-size:10px!important;
      padding:0 9px!important;
    }

    /* Price cells */
    .price-grid {
      display:grid;
      grid-template-columns:repeat(4,minmax(0,1fr));
      gap:7px;
      margin-top:10px;
    }

    .price-box {
      border:1px solid var(--line);
      border-radius:10px;
      padding:8px 9px;
      background:var(--panel-2);
    }

    .price-box b { display:block; font-size:12px; direction:ltr; text-align:right; }
    .price-box span { color:var(--muted)!important; font-size:8px; }

    /* Development */
    .daily-card {
      background:#fff;
      border:1px solid var(--line);
      border-radius:15px;
      padding:15px;
      min-height:260px;
      box-shadow:var(--shadow-soft);
    }

    .daily-card h4 { margin:0 0 8px; font-size:14px; }
    .daily-card ul { padding-right:18px; margin:7px 0; }
    .daily-card li { font-size:10px; line-height:1.7; }

    .status-pill {
      display:inline-flex;
      border-radius:999px;
      padding:5px 9px;
      font-size:9px;
      font-weight:950;
      margin-bottom:9px;
    }

    .status-pill.pending { color:var(--orange)!important; background:var(--orange-soft); }
    .status-pill.done { color:var(--green)!important; background:var(--green-soft); }

    .memory-card {
      border:1px solid var(--line);
      border-radius:13px;
      padding:13px;
      background:#fff;
      margin:7px 0;
      box-shadow:0 2px 10px rgba(31,48,79,.025);
    }

    .memory-code { color:var(--purple)!important; font-size:9px; font-weight:950; direction:ltr; }

    .result-success { color:var(--green)!important; font-weight:900; }
    .result-fail { color:var(--red)!important; font-weight:900; }
    .result-pending { color:var(--orange)!important; font-weight:900; }

    .work-progress {
      background:#fff;
      border:1px solid var(--line);
      border-radius:15px;
      padding:15px;
      margin:14px 0 18px;
      box-shadow:var(--shadow-soft);
    }

    .work-progress-head {
      display:flex;
      justify-content:space-between;
      align-items:center;
      gap:10px;
      margin-bottom:10px;
      font-size:11px;
      font-weight:900;
    }

    .work-progress-bar {
      display:flex;
      overflow:hidden;
      height:40px;
      border-radius:10px;
      background:#edf0f5;
    }

    .work-progress-done,
    .work-progress-pending {
      display:flex;
      align-items:center;
      justify-content:center;
      min-width:0;
      color:#fff!important;
      font-size:10px;
      font-weight:950;
    }

    .work-progress-done { background:linear-gradient(90deg,#11a858,#3bc46f); }
    .work-progress-pending { background:linear-gradient(90deg,#ee9815,#ffae26); }

    /* Chart bars */
    .bar-list {
      background:#fff;
      border:1px solid var(--line);
      border-radius:15px;
      padding:14px;
      box-shadow:var(--shadow-soft);
    }

    .bar-row {
      display:grid;
      grid-template-columns:110px 1fr 65px;
      gap:10px;
      align-items:center;
      margin:12px 0;
    }

    .bar-label { font-size:11px; font-weight:800; }
    .bar-track { height:9px; background:#edf0f5; border-radius:999px; overflow:hidden; }
    .bar-fill { height:100%; border-radius:999px; background:var(--blue); }
    .bar-value { font-size:11px; font-weight:900; text-align:left; direction:ltr; }

    /* Mobile */
    @media (max-width:900px) {
      .block-container { padding:12px 9px 80px; }
      .top-shell { padding-top:2px; align-items:center; }
      .page-icon { width:38px; height:38px; font-size:18px; }
      .page-title { font-size:21px; }
      .page-sub { font-size:10px; }
      .last-update { display:none; }
      .metrics-4 { grid-template-columns:repeat(2,minmax(0,1fr)); }
      .metrics-2 { gap:9px; }
      .metric-card { min-height:112px; padding:15px; border-radius:15px; }
      .metric-card .value { font-size:27px; }
      .table-head { display:none; }
      .news-grid { grid-template-columns:1fr 72px; gap:9px; }
      .news-grid > div:nth-child(1) { grid-column:1; grid-row:1; }
      .news-grid > div:nth-child(2) { grid-column:1 / span 2; grid-row:2; }
      .news-grid > div:nth-child(3) { grid-column:1; grid-row:3; }
      .news-grid > div:nth-child(4) { grid-column:2; grid-row:1; }
      .news-grid > div:nth-child(5) { grid-column:2; grid-row:3; }
      .news-row { padding:13px; border-radius:13px; }
      .price-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
      .daily-card { min-height:auto; }
      .top-meta { gap:5px; }
      .live { padding:6px 9px; }
      [data-testid="stSidebar"] { min-width:260px!important; }
    }

    @media (max-width:520px) {
      .metrics-4 { grid-template-columns:1fr 1fr; }
      .metric-card .hint { display:none; }
      .metric-card { min-height:96px; }
      .metric-card .metric-icon { width:31px; height:31px; font-size:14px; margin-bottom:7px; }
      .metric-card .value { font-size:24px; }
      .legend-item { padding:6px 8px; font-size:9px; }
      .bar-row { grid-template-columns:90px 1fr 54px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value) -> str:
    if value is None:
        return "—"
    try:
        return f"${float(value):.4f}"
    except Exception:
        return "—"


def percent(value) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):+.2f}%"
    except Exception:
        return "—"


def rec_class(recommendation: str) -> str:
    return {
        RECOMMENDATION_STRONG_BUY: "strong",
        RECOMMENDATION_BUY: "buy",
        RECOMMENDATION_WATCH: "watch",
        RECOMMENDATION_NEGATIVE: "negative",
    }.get(recommendation, "watch")


def metric_cards(
    positive: int,
    negative: int,
    positive_hint: str = "الأخبار ذات الدرجة الإيجابية",
    negative_hint: str = "الأخبار ذات الدرجة السلبية",
) -> None:
    st.markdown(
        f"""
        <div class="metrics-2">
          <div class="metric-card positive">
            <div class="metric-icon">↗</div>
            <div class="label">إيجابية</div>
            <div class="value">{positive}</div>
            <div class="hint">{html.escape(positive_hint)}</div>
          </div>
          <div class="metric-card negative">
            <div class="metric-icon">↘</div>
            <div class="label">سلبية</div>
            <div class="value">{negative}</div>
            <div class="hint">{html.escape(negative_hint)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def recommendation_legend() -> None:
    st.markdown(
        """
        <div class="legend">
          <span class="legend-item"><i class="legend-dot" style="background:#10a857"></i>فوق 90: شراء قوي</span>
          <span class="legend-item"><i class="legend-dot" style="background:#48b875"></i>فوق 65: شراء</span>
          <span class="legend-item"><i class="legend-dot" style="background:#ee9815"></i>0–65: مراقبة</span>
          <span class="legend-item"><i class="legend-dot" style="background:#e74848"></i>أقل من 0: سلبي</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str) -> None:
    control = load_control()
    live = bool(control.get("enabled"))
    status = load_json(config.STATUS_FILE, {})
    last_check = format_saudi_time(status.get("last_check")) if status.get("last_check") else "لم يبدأ الفحص"
    icons = {
        "الرئيسية": "⌂",
        "الأخبار": "▤",
        "المفضلة": "☆",
        "سجل التعلم": "◇",
        "الإحصائيات": "▥",
        "تطوير AI": "AI",
        "تحليل سهم": "⌕",
        "الحساب": "○",
    }
    live_html = (
        '<div class="live"><span class="dot"></span>يعمل</div>'
        if live
        else '<div class="live off"><span class="dot"></span>متوقف</div>'
    )
    st.markdown(
        f"""
        <div class="top-shell">
          <div class="top-title-wrap">
            <div class="page-icon">{html.escape(icons.get(title, "⚡"))}</div>
            <div>
              <h1 class="page-title">{html.escape(title)}</h1>
              <div class="page-sub">{html.escape(subtitle)}</div>
            </div>
          </div>
          <div class="top-meta">
            {live_html}
            <div class="last-update">آخر تحديث: {html.escape(last_check)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def table_header() -> None:
    st.markdown(
        """
        <div class="table-head">
          <span>الوقت</span>
          <span>الشركة / الرمز</span>
          <span>العنوان</span>
          <span>التوصية</span>
          <span>الدرجة</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def article_html(article: dict) -> str:
    item = enrich_article_for_display(article)
    recommendation = item["recommendation"]
    css = rec_class(recommendation)
    symbols = " / ".join(item.get("tickers") or ["—"])
    title = item.get("arabic_title") or "خبر جديد"
    time_text = format_saudi_time(item.get("published"))
    opinion = item.get("system_reason") or "لا توجد إشارة واضحة"
    ai = item.get("ai") or {}
    ai_summary = ai.get("summary")
    note = ai_summary if ai_summary and ai.get("available") else opinion

    return f"""
    <div class="news-row">
      <div class="news-grid">
        <div class="time">{html.escape(time_text)}<small>وقت السعودية</small></div>
        <div><div class="symbol">{html.escape(symbols)}</div><div class="company-note">خبر مرتبط بالسهم</div></div>
        <div>
          <div class="title-ar">{html.escape(str(title))}</div>
          <div class="mini">{html.escape(str(note))}</div>
        </div>
        <div><span class="badge {css}">{html.escape(recommendation)}</span></div>
        <div class="score {css}">{item.get("final_score", 0)}</div>
      </div>
    </div>
    """


def render_articles(
    articles: list[dict],
    prefix: str,
    limit: int = 100,
    allow_favorite: bool = True,
) -> None:
    if not articles:
        st.info("لا توجد أخبار ضمن الفترة المحددة.")
        return

    recommendation_legend()
    table_header()

    for index, article in enumerate(articles[:limit]):
        item = enrich_article_for_display(article)
        article_id = str(item.get("id"))
        st.markdown(article_html(item), unsafe_allow_html=True)

        cols = st.columns([1, 1, 7])
        with cols[0]:
            if allow_favorite:
                favorite = is_favorite(article_id)
                if st.button(
                    "★ محفوظ" if favorite else "☆ حفظ",
                    key=f"{prefix}_fav_{article_id}_{index}",
                    use_container_width=True,
                ):
                    if favorite:
                        remove_favorite(article_id)
                    else:
                        add_favorite(item)
                    st.rerun()

        with cols[1]:
            url = item.get("url")
            if url:
                st.link_button("فتح", url, use_container_width=True)

        with cols[2]:
            st.caption(
                f"الحالة: {item.get('event_status', 'غير مصنف')}"
            )

def load_current_feed() -> list[dict]:
    return load_json(config.FEED_FILE, [])


def counts_from_articles(
    articles: list[dict],
) -> tuple[int, int]:
    positive = 0
    negative = 0

    for article in articles:
        item = enrich_article_for_display(article)
        score = int(item.get("final_score", 0))
        if score > 0:
            positive += 1
        elif score < 0:
            negative += 1

    return positive, negative



def render_bar_rows(
    values: dict,
    suffix: str = "",
) -> None:
    numeric = {
        str(key): float(value or 0)
        for key, value in values.items()
    }
    maximum = max(
        [abs(value) for value in numeric.values()] or [1]
    )
    rows = []

    for label, value in numeric.items():
        width = (
            abs(value) / maximum * 100
            if maximum
            else 0
        )
        color = (
            "var(--red)"
            if value < 0
            else "var(--green)"
            if label in ("شراء قوي", "شراء", "نجح")
            else "var(--orange)"
            if label in ("مراقبة", "قيد المتابعة")
            else "var(--blue)"
        )
        row_html = (
            '<div class="bar-row">'
            f'<div class="bar-label">{html.escape(label)}</div>'
            '<div class="bar-track">'
            f'<div class="bar-fill" style="width:{width:.1f}%;background:{color}"></div>'
            '</div>'
            f'<div class="bar-value">{value:g}{html.escape(suffix)}</div>'
            '</div>'
        )
        rows.append(row_html)

    st.markdown(
        '<div class="bar-list">'
        + "".join(rows)
        + "</div>",
        unsafe_allow_html=True,
    )


def sidebar_navigation() -> str:
    icon_map = {
        "الرئيسية": "⌂  الرئيسية",
        "الأخبار": "▤  الأخبار",
        "المفضلة": "☆  المفضلة",
        "سجل التعلم": "◇  سجل التعلم",
        "الإحصائيات": "▥  الإحصائيات",
        "تطوير AI": "AI  تطوير الذكاء",
        "تحليل سهم": "⌕  تحليل سهم",
        "الحساب": "○  الحساب",
    }

    with st.sidebar:
        st.markdown(
            '<div class="brand"><span class="bolt">⚡</span>برق</div>',
            unsafe_allow_html=True,
        )

        page = st.radio(
            "التنقل",
            list(icon_map.keys()),
            label_visibility="collapsed",
            format_func=lambda value: icon_map[value],
        )

        status = load_json(config.STATUS_FILE, {})
        control = load_control()
        state = "الرصد يعمل" if control.get("enabled") else "الرصد متوقف"
        last = (
            format_saudi_time(status.get("last_check"))
            if status.get("last_check")
            else "لم يبدأ بعد"
        )
        st.markdown(
            f"""
            <div class="sidebar-card">
              <div class="small">حالة النظام</div>
              <div class="strong">{html.escape(state)}</div>
              <div class="small" style="margin-top:10px">آخر فحص</div>
              <div class="strong">{html.escape(last)}</div>
              <div class="small" style="margin-top:10px">القائمة</div>
              <div class="strong">932 سهمًا</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return page


page = sidebar_navigation()


# ============================================================
# الرئيسية
# ============================================================
if page == "الرئيسية":
    page_header(
        "الرئيسية",
        "ملخص الرصد وآخر الأخبار المؤثرة",
    )

    feed = load_current_feed()
    positive_count, negative_count = counts_from_articles(feed)
    metric_cards(positive_count, negative_count)

    control = load_control()
    monitoring = bool(control.get("enabled"))
    with st.container(border=True):
        col_start, col_refresh, col_telegram = st.columns(3)

        with col_start:
            if st.button(
                "إيقاف الرصد" if monitoring else "تشغيل الرصد",
                type="primary",
                use_container_width=True,
            ):
                update_control(
                    enabled=not monitoring,
                    positive_only=True,
                    ai_enabled=True,
                )
                st.rerun()

        with col_refresh:
            if st.button(
                "تحديث العرض",
                use_container_width=True,
            ):
                st.rerun()

        with col_telegram:
            if st.button(
                "اختبار تيليجرام",
                use_container_width=True,
            ):
                ok, message = telegram_send(
                    "⚡ <b>برق</b>\nتم الاتصال بنجاح."
                )
                if ok:
                    st.success(message)
                else:
                    st.error(message)

    st.subheader("آخر الأخبار")
    render_articles(feed, "home", limit=20)


# ============================================================
# الأخبار
# ============================================================
elif page == "الأخبار":
    page_header(
        "الأخبار",
        "استرجاع الأخبار وفلترتها وإرسالها إلى تيليجرام",
    )

    with st.container(border=True):
        control_cols = st.columns([1.2, 1, 1, 1])
        with control_cols[0]:
            period = st.selectbox(
                "الفترة",
                [
                    "آخر 15 دقيقة",
                    "آخر 30 دقيقة",
                    "آخر ساعتين",
                    "آخر 6 ساعات",
                    "آخر 24 ساعة",
                    "آخر أسبوع",
                ],
            )
        with control_cols[1]:
            news_type = st.selectbox(
                "النوع",
                ["الكل", "إيجابية", "سلبية"],
            )
        with control_cols[2]:
            use_ai = st.checkbox(
                "تحليل AI",
                value=True,
            )
        with control_cols[3]:
            send_telegram = st.checkbox(
                "إرسال تيليجرام",
                value=False,
            )

    hours = {
        "آخر 15 دقيقة": 0.25,
        "آخر 30 دقيقة": 0.5,
        "آخر ساعتين": 2,
        "آخر 6 ساعات": 6,
        "آخر 24 ساعة": 24,
        "آخر أسبوع": 168,
    }[period]

    if st.button(
        "جلب الأخبار",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner("جارٍ جلب الأخبار وتحليلها..."):
                raw_items = fetch_news(
                    hours=hours,
                    limit=config.NEWS_LIMIT,
                )
                results = process_articles(
                    raw_items,
                    hours=hours,
                    ai_enabled=use_ai,
                    watchlist_only=True,
                )

                if news_type == "إيجابية":
                    results = [
                        item
                        for item in results
                        if enrich_article_for_display(item)[
                            "final_score"
                        ] > 0
                    ]
                elif news_type == "سلبية":
                    results = [
                        item
                        for item in results
                        if enrich_article_for_display(item)[
                            "final_score"
                        ] < 0
                    ]

                signal_map = record_signals_batch(results)
                for article in results:
                    records = signal_map.get(
                        str(article.get("id"))
                    ) or []
                    if records:
                        article["tracking"] = records[0]

                save_json(
                    config.RETRIEVAL_FILE,
                    results[:2000],
                )

                sent_count = 0
                if send_telegram:
                    for article in results[:100]:
                        ok, _ = telegram_send(
                            article_message(article)
                        )
                        if ok:
                            sent_count += 1

                st.session_state["news_fetch_stats"] = {
                    "raw": len(raw_items),
                    "matched": len(results),
                    "sent": sent_count,
                }

        except Exception as exc:
            st.error(str(exc))

    results = load_json(config.RETRIEVAL_FILE, [])
    positive_count, negative_count = counts_from_articles(results)
    metric_cards(positive_count, negative_count)

    stats = st.session_state.get("news_fetch_stats")
    if stats:
        st.caption(
            f'المصدر: {stats["raw"]} خبر — '
            f'المطابق للقائمة: {stats["matched"]} — '
            f'المرسل: {stats["sent"]}'
        )

    render_articles(results, "news", limit=300)


# ============================================================
# المفضلة
# ============================================================
elif page == "المفضلة":
    page_header(
        "المفضلة",
        "الأخبار المحفوظة ومتابعة السعر منذ لحظة الرصد",
    )

    rows = favorite_rows()
    positive = sum(
        1 for row in rows if int(row.get("score", 0)) > 0
    )
    negative = sum(
        1 for row in rows if int(row.get("score", 0)) < 0
    )
    metric_cards(
        positive,
        negative,
        "الأخبار الإيجابية المحفوظة",
        "الأخبار السلبية المحفوظة",
    )

    with st.container(border=True):
        filter_cols = st.columns([2, 1])
        with filter_cols[0]:
            search = st.text_input(
                "بحث",
                placeholder="ابحث بالرمز أو العنوان",
            ).strip().lower()
        with filter_cols[1]:
            review_filter = st.selectbox(
                "الحالة",
                ["الكل", "تمت المراجعة", "لم تراجع"],
            )

    if search:
        rows = [
            row
            for row in rows
            if search in str(row.get("symbol", "")).lower()
            or search in str(row.get("title", "")).lower()
        ]

    if review_filter == "تمت المراجعة":
        rows = [row for row in rows if row.get("reviewed")]
    elif review_filter == "لم تراجع":
        rows = [row for row in rows if not row.get("reviewed")]

    if not rows:
        st.info("لم تحفظ أي خبر في المفضلة بعد.")
    else:
        recommendation_legend()
        table_header()

    for index, row in enumerate(rows):
        recommendation = str(row.get("recommendation"))
        css = rec_class(recommendation)

        st.markdown(
            f"""
            <div class="news-row">
              <div class="news-grid">
                <div class="time">{html.escape(format_saudi_time(row.get("detected_at")))}<small>وقت الرصد</small></div>
                <div><div class="symbol">{html.escape(str(row.get("symbol") or "—"))}</div><div class="company-note">محفوظ في المفضلة</div></div>
                <div>
                  <div class="title-ar">{html.escape(str(row.get("title") or "خبر محفوظ"))}</div>
                  <div class="price-grid">
                    <div class="price-box"><b>{money(row.get("price_at_signal"))}</b><span>سعر الرصد</span></div>
                    <div class="price-box"><b>{money(row.get("lowest_price"))}</b><span>أدنى سعر منذ الرصد</span></div>
                    <div class="price-box"><b>{money(row.get("highest_price"))}</b><span>أعلى سعر منذ الرصد</span></div>
                    <div class="price-box"><b>{percent(row.get("last_change_pct"))}</b><span>التغير الحالي</span></div>
                  </div>
                </div>
                <div><span class="badge {css}">{html.escape(recommendation)}</span></div>
                <div class="score {css}">{row.get("score", 0)}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cols = st.columns([1.2, 1, 1, 4])
        with cols[0]:
            reviewed = st.checkbox(
                "تمت المراجعة",
                value=bool(row.get("reviewed")),
                key=f"fav_review_{row.get('article_id')}_{index}",
            )
            if reviewed != bool(row.get("reviewed")):
                set_favorite_reviewed(
                    str(row.get("article_id")),
                    reviewed,
                )
                st.rerun()

        with cols[1]:
            if st.button(
                "حذف",
                key=f"fav_remove_{row.get('article_id')}_{index}",
                use_container_width=True,
            ):
                remove_favorite(
                    str(row.get("article_id"))
                )
                st.rerun()

        with cols[2]:
            if row.get("url"):
                st.link_button(
                    "فتح",
                    row["url"],
                    use_container_width=True,
                )


# ============================================================
# سجل التعلم
# ============================================================
elif page == "سجل التعلم":
    page_header(
        "سجل التعلم",
        "مقارنة درجة الخبر بما حدث فعليًا في حركة السعر",
    )

    with st.container(border=True):
        col_update, col_filter = st.columns([1, 3])
        with col_update:
            if st.button(
                "تحديث الأسعار",
                type="primary",
                use_container_width=True,
            ):
                try:
                    result = update_signal_outcomes()
                    st.success(
                        f'تم تحديث {result["updated_records"]} سجل.'
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        with col_filter:
            symbol_filter = st.text_input(
                "فلترة بالرمز",
                placeholder="مثال: NTCL",
            ).strip().upper()

    records = load_json(config.SIGNALS_FILE, [])
    if symbol_filter:
        records = [
            item
            for item in records
            if str(item.get("symbol", "")).upper()
            == symbol_filter
        ]

    records.sort(
        key=lambda item: item.get("detected_at") or "",
        reverse=True,
    )

    successes = sum(
        1 for item in records if signal_result(item) == "نجح"
    )
    failures = sum(
        1
        for item in records
        if signal_result(item) == "لم ينجح"
    )
    metric_cards(
        successes,
        failures,
        "إشارات طابقت اتجاه السعر",
        "إشارات خالفت اتجاه السعر",
    )

    if records:
        recommendation_legend()
        table_header()

    for index, record in enumerate(records[:500]):
        recommendation = signal_recommendation(record)
        css = rec_class(recommendation)
        result = signal_result(record)
        mismatch = signal_mismatch_reason(record)
        result_css = {
            "نجح": "result-success",
            "لم ينجح": "result-fail",
            "قيد المتابعة": "result-pending",
        }[result]

        score = (
            record.get("ai_score")
            if isinstance(record.get("ai_score"), (int, float))
            else record.get("system_score", 0)
        )

        article = {
            "title": record.get("title"),
            "system_reason": record.get("system_opinion"),
            "system_score": record.get("system_score", 0),
            "event_status": record.get("event_status"),
            "tickers": [record.get("symbol")],
            "ai": {
                "available": record.get("ai_available"),
                "score": record.get("ai_score"),
                "summary": record.get("ai_opinion"),
            },
        }
        title = enrich_article_for_display(article)[
            "arabic_title"
        ]

        st.markdown(
            f"""
            <div class="news-row">
              <div class="news-grid">
                <div class="time">{html.escape(format_saudi_time(record.get("detected_at")))}<small>وقت الرصد</small></div>
                <div><div class="symbol">{html.escape(str(record.get("symbol") or "—"))}</div><div class="company-note"><span class="{result_css}">{result}</span></div></div>
                <div>
                  <div class="title-ar">{html.escape(str(title))}</div>
                  <div class="price-grid">
                    <div class="price-box"><b>{money(record.get("price_at_signal"))}</b><span>سعر الرصد</span></div>
                    <div class="price-box"><b>{money(record.get("lowest_price"))}</b><span>أدنى سعر</span></div>
                    <div class="price-box"><b>{money(record.get("highest_price"))}</b><span>أعلى سعر</span></div>
                    <div class="price-box"><b>{money(record.get("latest_price"))}</b><span>السعر الحالي</span></div>
                  </div>
                  <div class="mini">التغير: {percent(record.get("last_change_pct"))}</div>
                  <div class="mini">{html.escape(str(mismatch or record.get("development_comment") or ""))}</div>
                </div>
                <div><span class="badge {css}">{html.escape(recommendation)}</span></div>
                <div class="score {css}">{score}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# الإحصائيات
# ============================================================
elif page == "الإحصائيات":
    page_header(
        "الإحصائيات",
        "ملخص أداء الرصد والتوصيات مقارنة بحركة السعر",
    )

    days = st.selectbox(
        "الفترة",
        [7, 30, 90, 180],
        index=1,
        format_func=lambda value: f"آخر {value} يومًا",
    )
    stats = calculate_statistics(days=days)

    st.markdown(
        f"""
        <div class="metrics-4">
          <div class="metric-card">
            <div class="metric-icon">▤</div>
            <div class="label">إجمالي الإشارات</div>
            <div class="value">{stats["total"]}</div>
            <div class="hint">خلال {days} يومًا</div>
          </div>
          <div class="metric-card positive">
            <div class="metric-icon">↗</div>
            <div class="label">إيجابية</div>
            <div class="value">{stats["positive"]}</div>
            <div class="hint">درجة أعلى من صفر</div>
          </div>
          <div class="metric-card negative">
            <div class="metric-icon">↘</div>
            <div class="label">سلبية</div>
            <div class="value">{stats["negative"]}</div>
            <div class="hint">درجة أقل من صفر</div>
          </div>
          <div class="metric-card processed">
            <div class="metric-icon">%</div>
            <div class="label">نسبة النجاح</div>
            <div class="value">{stats["success_rate"]}%</div>
            <div class="hint">من الإشارات المحسومة</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_rec, col_result = st.columns(2)

    with col_rec:
        st.subheader("توزيع التوصيات")
        render_bar_rows(
            stats["recommendations"],
        )

    with col_result:
        st.subheader("نتائج الإشارات")
        render_bar_rows(
            stats["results"],
        )

    st.subheader("متوسط تغير السعر حسب التوصية")
    render_bar_rows(
        stats["average_changes"],
        suffix="%",
    )

    st.subheader("أكثر الأخطاء رصدًا")
    if stats["top_errors"]:
        for item in stats["top_errors"]:
            st.markdown(
                f"""
                <div class="memory-card">
                  <b>{html.escape(str(item["type"]))}</b>
                  <div class="mini">تكرر {item["count"]} مرات</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("لا توجد أخطاء متكررة كافية ضمن الفترة.")


# ============================================================
# تطوير AI
# ============================================================
elif page == "تطوير AI":
    page_header(
        "تطوير AI",
        "ذاكرة تراكمية للتعليقات اليومية والتحسينات المنفذة والمعلقة",
    )

    dashboard = development_dashboard()

    st.markdown(
        f"""
        <div class="metrics-4">
          <div class="metric-card">
            <div class="metric-icon">▣</div>
            <div class="label">أيام مسجلة</div>
            <div class="value">{dashboard["days_recorded"]}</div>
            <div class="hint">إجمالي التعليقات اليومية</div>
          </div>
          <div class="metric-card processed">
            <div class="metric-icon">✓</div>
            <div class="label">تم العمل عليها</div>
            <div class="value">{dashboard["days_processed"]}</div>
            <div class="hint">أيام تم تصدير ملاحظاتها</div>
          </div>
          <div class="metric-card pending">
            <div class="metric-icon">◷</div>
            <div class="label">ملاحظات معلقة</div>
            <div class="value">{dashboard["days_pending"]}</div>
            <div class="hint">أيام لم يتم تصديرها</div>
          </div>
          <div class="metric-card">
            <div class="metric-icon">AI</div>
            <div class="label">تحسينات معلقة</div>
            <div class="value">{dashboard["pending_improvements"]}</div>
            <div class="hint">عناصر داخل ذاكرة التطوير</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    total_days = max(1, int(dashboard["days_recorded"]))
    processed_days = int(dashboard["days_processed"])
    pending_days = int(dashboard["days_pending"])
    processed_pct = processed_days / total_days * 100
    pending_pct = pending_days / total_days * 100

    st.markdown(
        f"""
        <div class="work-progress">
          <div class="work-progress-head">
            <span>حالة العمل</span>
            <span>{processed_days} تم العمل عليها — {pending_days} معلقة</span>
          </div>
          <div class="work-progress-bar">
            <div class="work-progress-done" style="width:{processed_pct:.1f}%">{processed_days}</div>
            <div class="work-progress-pending" style="width:{pending_pct:.1f}%">{pending_days}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pending_total = int(dashboard["days_pending"])
    export_options = [
        value
        for value in (10, 30, 50, 100)
        if value < pending_total
    ]
    export_options.append(
        pending_total if pending_total else 1
    )
    export_options = sorted(set(export_options))

    export_limit = st.selectbox(
        "عدد الأيام المراد تصديرها من الأقدم",
        export_options,
        index=len(export_options) - 1,
        format_func=lambda value: (
            f"{value} يوم"
            if value != pending_total
            else f"كل المعلق ({pending_total})"
        ),
        disabled=pending_total == 0,
    )

    action_cols = st.columns(4)

    with action_cols[0]:
        if st.button(
            "إنشاء تعليق اليوم",
            type="primary",
            use_container_width=True,
        ):
            with st.spinner("جارٍ تحليل الأخطاء مع الذاكرة السابقة..."):
                review = generate_daily_development_review(
                    force=False
                )
            st.success(
                f'تم تجهيز تعليق {review.get("date")}.'
            )
            st.rerun()

    with action_cols[1]:
        if st.button(
            "إعادة تحليل اليوم",
            use_container_width=True,
        ):
            with st.spinner("جارٍ إعادة التحليل..."):
                review = generate_daily_development_review(
                    force=True
                )
            st.success("تم تحديث تعليق اليوم.")
            st.rerun()

    with action_cols[2]:
        if st.button(
            "تجهيز الملاحظات المعلقة",
            use_container_width=True,
        ):
            export = export_pending_development_txt(limit=export_limit)
            st.session_state["pending_export"] = export
            if export["count"]:
                st.success(export["message"])
                st.rerun()
            else:
                st.info(export["message"])

    with action_cols[3]:
        if st.button(
            "تجهيز السجل الكامل",
            use_container_width=True,
        ):
            st.session_state[
                "full_export"
            ] = export_all_development_txt()

    pending_export = st.session_state.get("pending_export")
    if pending_export and pending_export.get("text"):
        st.download_button(
            "تنزيل ملف الملاحظات المعلقة TXT",
            data=pending_export["text"],
            file_name=pending_export["filename"],
            mime="text/plain",
            type="primary",
            use_container_width=True,
        )

    full_export = st.session_state.get("full_export")
    if full_export and full_export.get("text"):
        st.download_button(
            "تنزيل السجل التراكمي الكامل TXT",
            data=full_export["text"],
            file_name=full_export["filename"],
            mime="text/plain",
            use_container_width=True,
        )

    st.subheader("سجل التعليقات اليومية")
    reviews = development_dashboard()["reviews"]

    if not reviews:
        st.info("لم يتم إنشاء أي تعليق يومي بعد.")

    for start_index in range(0, len(reviews), 3):
        columns = st.columns(3)
        for offset, review in enumerate(
            reviews[start_index:start_index + 3]
        ):
            with columns[offset]:
                status = review.get("status")
                status_text = (
                    "تم العمل على الملاحظات"
                    if status in ("exported", "processed")
                    else "معلقة"
                )
                status_css = (
                    "done"
                    if status in ("exported", "processed")
                    else "pending"
                )

                errors = review.get("errors") or []
                recommendations = (
                    review.get("recommendations") or []
                )

                error_html = "".join(
                    f"<li>{html.escape(str(item.get('title')))}</li>"
                    for item in errors[:4]
                )
                rec_html = "".join(
                    f"<li>{html.escape(str(item.get('title')))}</li>"
                    for item in recommendations[:4]
                )

                st.markdown(
                    f"""
                    <div class="daily-card">
                      <span class="status-pill {status_css}">{status_text}</span>
                      <h4>{html.escape(str(review.get("date")))}</h4>
                      <div class="mini">{html.escape(str(review.get("summary") or ""))}</div>
                      <hr>
                      <b>الأخطاء</b>
                      <ul>{error_html or "<li>لا توجد أخطاء قوية</li>"}</ul>
                      <b>التحسينات</b>
                      <ul>{rec_html or "<li>لا يوجد اقتراح جديد</li>"}</ul>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                with st.expander("التفاصيل والذاكرة"):
                    st.write(review.get("summary"))
                    for note in review.get("memory_notes") or []:
                        st.caption(f"ذاكرة: {note}")

                    for error in errors:
                        st.markdown(
                            f"**{error.get('title')}** — "
                            f"{error.get('reason')}"
                        )
                        st.caption(
                            str(error.get("evidence") or "")
                        )

                    for rec in recommendations:
                        st.markdown(
                            f"**{rec.get('title')}**"
                        )
                        st.write(rec.get("action"))
                        st.caption(
                            f"الرمز: {rec.get('code')} — "
                            f"النوع: {rec.get('mode')}"
                        )

    st.subheader("ذاكرة التحسينات")
    improvements = development_dashboard()[
        "improvements"
    ]

    for index, item in enumerate(improvements):
        status_map = {
            "pending": "معلقة",
            "exported": "تم العمل على الملاحظات",
            "implemented": "تم التنفيذ",
            "monitoring": "تحت قياس الأثر",
            "closed": "مغلقة",
        }
        st.markdown(
            f"""
            <div class="memory-card">
              <div class="memory-code">{html.escape(str(item.get("code")))}</div>
              <b>{html.escape(str(item.get("title") or ""))}</b>
              <div class="mini">{html.escape(str(item.get("action") or ""))}</div>
              <div class="mini">
                الحالة: {html.escape(status_map.get(item.get("status"), str(item.get("status"))))}
                — أول ظهور: {html.escape(str(item.get("first_seen") or "—"))}
                — آخر ظهور: {html.escape(str(item.get("last_seen") or "—"))}
                — تكرر: {item.get("times_seen", 1)}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cols = st.columns([1, 1, 1, 4])
        with cols[0]:
            if st.button(
                "تم التنفيذ",
                key=f"imp_done_{item.get('code')}_{index}",
                use_container_width=True,
            ):
                mark_improvement_status(
                    str(item.get("code")),
                    "implemented",
                    "تم تأكيد تنفيذ التحسين من الواجهة.",
                )
                st.rerun()

        with cols[1]:
            if st.button(
                "قياس الأثر",
                key=f"imp_monitor_{item.get('code')}_{index}",
                use_container_width=True,
            ):
                mark_improvement_status(
                    str(item.get("code")),
                    "monitoring",
                    "تم وضع التحسين تحت قياس الأثر.",
                )
                st.rerun()

        with cols[2]:
            if st.button(
                "إغلاق",
                key=f"imp_close_{item.get('code')}_{index}",
                use_container_width=True,
            ):
                mark_improvement_status(
                    str(item.get("code")),
                    "closed",
                    "أُغلق التحسين يدويًا.",
                )
                st.rerun()


# ============================================================
# تحليل سهم
# ============================================================
elif page == "تحليل سهم":
    page_header(
        "تحليل سهم",
        "بحث مباشر عن أخبار رمز واحد مع خلاصة AI",
    )

    cols = st.columns([2, 1, 1])
    with cols[0]:
        symbol = st.text_input(
            "رمز السهم",
            placeholder="مثال: NTCL",
        ).strip().upper()
    with cols[1]:
        symbol_period = st.selectbox(
            "الفترة",
            [
                "آخر 15 دقيقة",
                "آخر 30 دقيقة",
                "آخر 24 ساعة",
                "آخر 3 أيام",
                "آخر أسبوع",
            ],
        )
    with cols[2]:
        symbol_use_ai = st.checkbox(
            "تحليل AI",
            value=True,
        )

    symbol_hours = {
        "آخر 15 دقيقة": 0.25,
        "آخر 30 دقيقة": 0.5,
        "آخر 24 ساعة": 24,
        "آخر 3 أيام": 72,
        "آخر أسبوع": 168,
    }[symbol_period]

    if st.button(
        "تحليل السهم",
        type="primary",
        use_container_width=True,
    ):
        if not symbol:
            st.warning("أدخل رمز السهم.")
        else:
            try:
                with st.spinner("جارٍ تحليل الأخبار..."):
                    result = analyze_symbol_news(
                        symbol=symbol,
                        hours=symbol_hours,
                        ai_enabled=symbol_use_ai,
                    )
                    st.session_state[
                        "symbol_result"
                    ] = result
            except Exception as exc:
                st.error(str(exc))

    result = st.session_state.get("symbol_result")
    if result:
        articles = result.get("articles") or []
        positive_count, negative_count = counts_from_articles(
            articles
        )
        metric_cards(positive_count, negative_count)

        overall = result.get("overall_ai") or {}
        if overall:
            if overall.get("available") is False:
                st.warning(
                    overall.get("reason")
                    or "الخلاصة غير متاحة."
                )
            else:
                st.markdown(
                    '<div class="section">',
                    unsafe_allow_html=True,
                )
                st.subheader("الخلاصة")
                st.write(overall.get("summary"))
                st.write(
                    f'**أهم إيجابية:** '
                    f'{overall.get("key_positive", "—")}'
                )
                st.write(
                    f'**أهم خطر:** '
                    f'{overall.get("key_risk", "—")}'
                )
                st.info(overall.get("verdict", ""))
                st.markdown(
                    "</div>",
                    unsafe_allow_html=True,
                )

        render_articles(
            articles,
            "symbol",
            limit=150,
        )


# ============================================================
# الحساب
# ============================================================
elif page == "الحساب":
    page_header(
        "الحساب",
        "حالة OpenAI والتكلفة التقديرية",
    )

    account = load_account()
    totals = usage_totals()

    st.markdown(
        f"""
        <div class="metrics-4">
          <div class="metric-card">
            <div class="metric-icon">$</div>
            <div class="label">مصروف اليوم</div>
            <div class="value">${totals["today_cost"]:.4f}</div>
          </div>
          <div class="metric-card">
            <div class="metric-icon">7</div>
            <div class="label">مصروف الأسبوع</div>
            <div class="value">${totals["week_cost"]:.4f}</div>
          </div>
          <div class="metric-card">
            <div class="metric-icon">Σ</div>
            <div class="label">إجمالي المصروف</div>
            <div class="value">${totals["total_cost"]:.4f}</div>
          </div>
          <div class="metric-card">
            <div class="metric-icon">≈</div>
            <div class="label">المتبقي التقديري</div>
            <div class="value">${totals["estimated_remaining"]:.2f}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    with cols[0]:
        starting_balance = st.number_input(
            "الرصيد المشحون",
            min_value=0.0,
            value=float(
                account.get(
                    "starting_balance_usd",
                    5.0,
                )
            ),
            step=1.0,
        )
    with cols[1]:
        weekly_budget = st.number_input(
            "الحد الأسبوعي",
            min_value=0.0,
            value=float(
                account.get(
                    "weekly_budget_usd",
                    2.0,
                )
            ),
            step=0.5,
        )
    with cols[2]:
        ai_mode = st.selectbox(
            "وضع AI",
            ["economic", "professional", "off"],
            index=[
                "economic",
                "professional",
                "off",
            ].index(
                str(account.get("ai_mode", "economic"))
            ),
            format_func=lambda value: {
                "economic": "اقتصادي",
                "professional": "احترافي",
                "off": "متوقف",
            }[value],
        )

    if st.button(
        "حفظ الإعدادات",
        type="primary",
        use_container_width=True,
    ):
        account.update(
            {
                "starting_balance_usd": starting_balance,
                "weekly_budget_usd": weekly_budget,
                "ai_mode": ai_mode,
            }
        )
        save_account(account)
        st.success("تم الحفظ.")

    if st.button(
        "فحص OpenAI",
        use_container_width=True,
    ):
        status = daily_openai_status()
        if status["connected"]:
            st.success(status["message"])
        else:
            st.error(status["message"])
