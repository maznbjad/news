from __future__ import annotations

import html
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

import config
from core import (
    analyze_symbol_news,
    article_message,
    daily_openai_status,
    fetch_news,
    format_saudi_time,
    is_positive,
    load_account,
    load_control,
    load_json,
    process_articles,
    record_signals_batch,
    save_account,
    save_json,
    telegram_send,
    update_control,
    update_signal_outcomes,
    usage_totals,
)
from monitor_worker import run as run_monitor_worker

RIYADH = ZoneInfo("Asia/Riyadh")

st.set_page_config(
    page_title="برق نيوز",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed",
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


start_background_worker()

st.markdown(
    """
    <style>
    :root {
      --bg:#06080d;
      --panel:#10141d;
      --line:rgba(255,255,255,.09);
      --text:#f6f7fa;
      --muted:#8e98a8;
      --yellow:#ffd43b;
      --green:#31d889;
      --red:#ff6678;
    }

    html, body, [class*="css"] {
      direction:rtl;
      text-align:right;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Tahoma,Arial,sans-serif;
    }

    .stApp {
      background:
        radial-gradient(circle at 100% -10%,rgba(255,212,59,.12),transparent 33%),
        var(--bg);
      color:var(--text);
    }

    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    #MainMenu,
    footer {
      display:none!important;
    }

    .block-container {
      max-width:720px!important;
      padding:18px 12px 90px!important;
    }

    h1,h2,h3,p,label,span,div {
      color:var(--text);
    }

    .top {
      display:flex;
      justify-content:space-between;
      align-items:center;
      margin-bottom:12px;
    }

    .brand {
      font-size:23px;
      font-weight:950;
    }

    .sub {
      font-size:11px;
      color:var(--muted)!important;
    }

    .status {
      font-size:11px;
      padding:8px 10px;
      border-radius:999px;
      border:1px solid var(--line);
      color:var(--muted)!important;
    }

    .status.live {
      color:var(--green)!important;
      border-color:rgba(49,216,137,.35);
      background:rgba(49,216,137,.08);
    }

    .hero {
      border:1px solid rgba(255,212,59,.22);
      background:linear-gradient(145deg,rgba(255,212,59,.12),rgba(16,20,29,.96));
      border-radius:22px;
      padding:18px;
      margin:8px 0 12px;
    }

    .hero h2 {
      margin:0 0 7px;
      font-size:23px;
    }

    .hero p {
      margin:0;
      color:#aab2bf!important;
      font-size:13px;
      line-height:1.7;
    }

    [data-testid="stButton"] button {
      min-height:48px;
      border-radius:15px;
      border:1px solid var(--line);
      background:var(--panel);
      font-weight:900;
    }

    .big [data-testid="stButton"] button {
      min-height:76px;
      font-size:20px;
      background:linear-gradient(145deg,var(--yellow),#ffb800);
      color:#171000;
      border:0;
    }

    .card {
      display:block;
      text-decoration:none!important;
      border:1px solid var(--line);
      border-radius:17px;
      padding:13px;
      margin:8px 0;
      background:var(--panel);
    }

    .card.pos {
      background:linear-gradient(145deg,rgba(49,216,137,.18),rgba(16,20,29,.96));
      border-color:rgba(49,216,137,.32);
    }

    .card.neg {
      background:linear-gradient(145deg,rgba(255,102,120,.18),rgba(16,20,29,.96));
      border-color:rgba(255,102,120,.32);
    }

    .card.neu {
      background:linear-gradient(145deg,rgba(255,212,59,.14),rgba(16,20,29,.96));
      border-color:rgba(255,212,59,.26);
    }

    .row {
      display:flex;
      justify-content:space-between;
      gap:8px;
      align-items:center;
    }

    .ticker {
      font-weight:950;
      color:var(--yellow)!important;
    }

    .time {
      font-size:10px;
      color:var(--muted)!important;
    }

    .headline {
      font-size:14px;
      font-weight:850;
      line-height:1.55;
      margin:8px 0;
    }

    .scores {
      display:grid;
      grid-template-columns:repeat(2,1fr);
      gap:7px;
    }

    .score {
      border:1px solid var(--line);
      background:rgba(0,0,0,.16);
      padding:9px;
      border-radius:12px;
    }

    .num {
      font-size:18px;
      font-weight:950;
    }

    .lab {
      font-size:10px;
      color:var(--muted)!important;
    }

    .opinion {
      margin-top:7px;
      padding-top:7px;
      border-top:1px solid var(--line);
      font-size:12px;
      line-height:1.55;
      color:#cad1dc!important;
    }

    .metrics {
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:7px;
      margin:10px 0;
    }

    .metric {
      border:1px solid var(--line);
      background:var(--panel);
      border-radius:14px;
      padding:11px;
    }

    .metric b {
      font-size:17px;
    }

    .metric small {
      display:block;
      color:var(--muted);
      margin-top:3px;
    }

    .learning {
      border:1px solid var(--line);
      background:var(--panel);
      border-radius:17px;
      padding:13px;
      margin:8px 0;
    }

    .learning-grid {
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:6px;
      margin-top:8px;
    }

    .mini {
      border:1px solid var(--line);
      border-radius:10px;
      padding:8px;
      background:rgba(0,0,0,.15);
    }

    .mini b {
      display:block;
      font-size:14px;
    }

    .mini span {
      font-size:9px;
      color:var(--muted)!important;
    }

    .note {
      font-size:11px;
      color:var(--muted)!important;
      line-height:1.6;
    }

    [data-testid="stTabs"] button {
      font-weight:900;
      font-size:12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_card(article: dict) -> str:
    ai = article.get("ai") or {}
    sentiment = str(
        ai.get("sentiment")
        if ai.get("available")
        else article.get("system_sentiment")
        or "neutral"
    )

    if sentiment == "positive":
        css_class = "pos"
    elif sentiment in ("negative", "mixed"):
        css_class = "neg"
    else:
        css_class = "neu"

    tickers = " • ".join(
        article.get("tickers") or ["—"]
    )
    url = html.escape(
        str(article.get("url") or "#"),
        quote=True,
    )
    target = "_blank" if url != "#" else "_self"

    tracking = article.get("tracking") or {}
    price_text = ""
    if tracking.get("price_at_signal") is not None:
        price_text = (
            f'<div class="opinion"><b>سعر الرصد:</b> '
            f'${float(tracking["price_at_signal"]):.4f}</div>'
        )

    ai_score = ai.get("score")
    ai_failed = (
        ai.get("available") is False
        or ai.get("sentiment") == "error"
        or str(ai.get("summary") or "").startswith("تعذر تحليل AI")
    )
    ai_score_text = (
        "غير متاح"
        if ai_failed or ai_score is None
        else str(ai_score)
    )

    return (
        f'<a class="card {css_class}" href="{url}" target="{target}">'
        f'<div class="row">'
        f'<span class="ticker">{html.escape(tickers)}</span>'
        f'<span class="time">'
        f'{html.escape(str(article.get("published_display", "—")))}</span>'
        f'</div>'
        f'<div class="headline">'
        f'{html.escape(str(article.get("title", "")))}</div>'
        f'<div class="scores">'
        f'<div class="score">'
        f'<div class="num">{article.get("system_score", 0)}</div>'
        f'<div class="lab">تقييم النظام</div>'
        f'</div>'
        f'<div class="score">'
        f'<div class="num">{html.escape(ai_score_text)}</div>'
        f'<div class="lab">تقييم AI</div>'
        f'</div>'
        f'</div>'
        f'<div class="opinion"><b>حالة الحدث:</b> '
        f'{html.escape(str(article.get("event_status") or "غير مصنف"))}'
        f' — <b>التنبيه:</b> '
        f'{html.escape(str(article.get("alert_level") or "منخفض"))}</div>'
        f'<div class="opinion"><b>ثقة النظام:</b> '
        f'{article.get("confidence_score", 0)}% '
        f'({html.escape(str(article.get("confidence_label") or "منخفضة"))})</div>'
        f'<div class="opinion"><b>رأي النظام:</b> '
        f'{html.escape(str(article.get("system_reason") or "لا توجد إشارة واضحة"))}'
        f'</div>'
        f'<div class="opinion"><b>رأي AI:</b> '
        f'{html.escape(str(ai.get("summary") or "لم يتم تشغيل AI"))}'
        f'</div>'
        f'{price_text}'
        f'</a>'
    )


def render_results(items: list[dict], max_items: int = 150) -> None:
    if not items:
        st.info("لا توجد نتائج.")
        return

    for article in items[:max_items]:
        st.markdown(
            render_card(article),
            unsafe_allow_html=True,
        )


def render_signal(record: dict) -> str:
    initial = record.get("price_at_signal")
    latest = record.get("latest_price")
    highest = record.get("highest_change_pct")
    lowest = record.get("lowest_change_pct")
    last_change = record.get("last_change_pct")

    def money(value):
        return (
            "—"
            if value is None
            else f"${float(value):.4f}"
        )

    def percent(value):
        return (
            "—"
            if value is None
            else f"{float(value):+.2f}%"
        )

    sentiment = str(
        record.get("signal_sentiment") or "neutral"
    )
    css_class = (
        "pos"
        if sentiment == "positive"
        else "neg"
        if sentiment in ("negative", "mixed")
        else "neu"
    )

    return (
        f'<div class="learning card {css_class}">'
        f'<div class="row">'
        f'<span class="ticker">{html.escape(str(record.get("symbol", "—")))}</span>'
        f'<span class="time">{format_saudi_time(record.get("detected_at"))}</span>'
        f'</div>'
        f'<div class="headline">{html.escape(str(record.get("title", "")))}</div>'
        f'<div class="learning-grid">'
        f'<div class="mini"><b>{money(initial)}</b><span>سعر الرصد</span></div>'
        f'<div class="mini"><b>{money(latest)}</b><span>آخر سعر</span></div>'
        f'<div class="mini"><b>{percent(last_change)}</b><span>التغير الحالي</span></div>'
        f'<div class="mini"><b>{percent(highest)}</b><span>أعلى تغير</span></div>'
        f'<div class="mini"><b>{percent(lowest)}</b><span>أدنى تغير</span></div>'
        f'<div class="mini"><b>{record.get("updates", 0)}</b><span>مرات التحديث</span></div>'
        f'</div>'
        f'<div class="opinion"><b>حالة الحدث:</b> '
        f'{html.escape(str(record.get("event_status") or "—"))} — '
        f'<b>الثقة:</b> {record.get("confidence_score", "—")}%</div>'
        f'<div class="opinion"><b>رأي النظام:</b> '
        f'{html.escape(str(record.get("system_opinion") or "—"))}</div>'
        f'<div class="opinion"><b>رأي AI:</b> '
        f'{html.escape(str(record.get("ai_opinion") or "—"))}</div>'
        f'<div class="opinion"><b>تعليق التطوير:</b> '
        f'{html.escape(str(record.get("development_comment") or "—"))}</div>'
        f'</div>'
    )


control = load_control()
status = load_json(config.STATUS_FILE, {})
monitoring = bool(control.get("enabled"))
status_class = "status live" if monitoring else "status"

st.markdown(
    f"""
    <div class="top">
      <div>
        <div class="brand">⚡ برق نيوز</div>
        <div class="sub">رصد أخبار + تقييم + تعلّم من حركة السعر</div>
      </div>
      <div class="{status_class}">
        {"● الرصد يعمل" if monitoring else "الرصد متوقف"}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

(
    tab_monitor,
    tab_retrieve,
    tab_symbol,
    tab_learning,
    tab_account,
) = st.tabs(
    [
        "الرصد",
        "الاسترجاع",
        "تحليل سهم",
        "سجل التعلّم",
        "الحساب",
    ]
)

with tab_monitor:
    st.markdown(
        """
        <div class="hero">
          <h2>الرصد الإيجابي</h2>
          <p>
            يراقب قائمة الأسهم، يقيّم الخبر بالنظام وAI،
            يحفظ سعر الرصد، ويرسل الأخبار الإيجابية إلى تيليجرام.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="big">',
        unsafe_allow_html=True,
    )

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

    st.markdown("</div>", unsafe_allow_html=True)

    col_test, col_refresh = st.columns(2)

    with col_test:
        if st.button(
            "اختبار تيليجرام",
            use_container_width=True,
        ):
            ok, message = telegram_send(
                "⚡ <b>برق نيوز</b>\nتم الاتصال بنجاح."
            )
            if ok:
                st.success(message)
            else:
                st.error(message)

    with col_refresh:
        if st.button(
            "تحديث العرض",
            use_container_width=True,
        ):
            st.rerun()

    st.caption(
        status.get(
            "message",
            "عامل الرصد يبدأ تلقائيًا مع التطبيق.",
        )
    )

    if status.get("last_check"):
        st.caption(
            f'آخر فحص: {format_saudi_time(status.get("last_check"))} — '
            f'من المصدر: {status.get("last_raw_fetched", 0)} — '
            f'طابق القائمة: {status.get("last_fetched", 0)} — '
            f'أُرسل: {status.get("last_sent", 0)}'
        )

    st.subheader("آخر النتائج")
    render_results(
        load_json(config.FEED_FILE, []),
        max_items=50,
    )

with tab_retrieve:
    st.subheader("استرجاع الأخبار وإرسالها")

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

    news_type = st.selectbox(
        "النوع",
        ["إيجابية", "سلبية", "الكل"],
    )

    use_ai = st.checkbox(
        "تحليل AI للأخبار المهمة",
        value=True,
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
        "استرجاع وإرسال إلى تيليجرام",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner(
                "جارٍ جلب جميع صفحات الأخبار وفلترتها..."
            ):
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
                        article
                        for article in results
                        if is_positive(article)
                    ]
                elif news_type == "سلبية":
                    results = [
                        article
                        for article in results
                        if (
                            (
                                article.get("ai")
                                or {}
                            ).get("sentiment")
                            in ("negative", "mixed")
                            or int(
                                article.get(
                                    "system_score",
                                    0,
                                )
                            )
                            < 0
                        )
                    ]

                signal_map = record_signals_batch(results)
                for article in results:
                    records = (
                        signal_map.get(
                            str(article.get("id"))
                        )
                        or []
                    )
                    if records:
                        article["tracking"] = records[0]

                save_json(
                    config.RETRIEVAL_FILE,
                    results[:1000],
                )

                sent_count = 0
                for article in results[:50]:
                    ok, _ = telegram_send(
                        article_message(article)
                    )
                    if ok:
                        sent_count += 1

                st.session_state["retrieve_stats"] = {
                    "raw": len(raw_items),
                    "matched": len(results),
                    "sent": sent_count,
                }

                st.success(
                    f"جلبنا {len(raw_items)} خبرًا من المصدر، "
                    f"وبعد الفلترة بقي {len(results)}، "
                    f"وأرسلنا {sent_count} إشعارًا."
                )

        except Exception as exc:
            st.error(str(exc))

    stats = st.session_state.get("retrieve_stats")
    if stats:
        st.caption(
            f'المصدر: {stats["raw"]} — '
            f'بعد الفلترة: {stats["matched"]} — '
            f'تيليجرام: {stats["sent"]}'
        )

    st.subheader("قائمة الاسترجاع")
    render_results(
        load_json(config.RETRIEVAL_FILE, []),
        max_items=300,
    )

with tab_symbol:
    st.subheader("تحليل سريع لأخبار سهم")

    symbol = st.text_input(
        "رمز السهم",
        placeholder="مثال: NTCL",
    ).strip().upper()

    symbol_period = st.selectbox(
        "الفترة",
        [
            "آخر 15 دقيقة",
            "آخر 30 دقيقة",
            "آخر 24 ساعة",
            "آخر 3 أيام",
            "آخر أسبوع",
        ],
        key="symbol_period",
    )

    symbol_hours = {
        "آخر 15 دقيقة": 0.25,
        "آخر 30 دقيقة": 0.5,
        "آخر 24 ساعة": 24,
        "آخر 3 أيام": 72,
        "آخر أسبوع": 168,
    }[symbol_period]

    symbol_use_ai = st.checkbox(
        "تقييم AI وإنشاء خلاصة نهائية",
        value=True,
        key="symbol_ai",
    )

    if st.button(
        "تحليل أخبار السهم",
        type="primary",
        use_container_width=True,
    ):
        if not symbol:
            st.warning("أدخل رمز السهم.")
        else:
            try:
                with st.spinner(
                    "جارٍ طلب أخبار الرمز مباشرة وتحليلها..."
                ):
                    result = analyze_symbol_news(
                        symbol=symbol,
                        hours=symbol_hours,
                        ai_enabled=symbol_use_ai,
                    )
                    st.session_state[
                        "symbol_analysis_result"
                    ] = result

            except Exception as exc:
                st.error(str(exc))

    result = st.session_state.get(
        "symbol_analysis_result"
    )

    if result:
        latest_price = result.get("latest_price")
        latest_price_text = (
            "—"
            if latest_price is None
            else f"${float(latest_price):.4f}"
        )

        st.markdown(
            f"""
            <div class="metrics">
              <div class="metric">
                <b>{result.get("count", 0)}</b>
                <small>الأخبار</small>
              </div>
              <div class="metric">
                <b>{result.get("system_average", 0)}</b>
                <small>متوسط النظام</small>
              </div>
              <div class="metric">
                <b>{result.get("ai_average", 0)}</b>
                <small>متوسط AI</small>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.caption(
            f'آخر سعر متاح: {latest_price_text} — '
            f'حلل AI عدد {result.get("ai_analyzed_count", 0)} خبر — '
            f'حُفظت {result.get("saved_signals", 0)} إشارة.'
        )

        overall = result.get("overall_ai") or {}
        if overall:
            st.markdown("### الخلاصة النهائية")

            if overall.get("available") is False:
                st.warning(
                    f'{overall.get("summary", "الخلاصة غير متاحة")}: '
                    f'{overall.get("reason", "")}'
                )
            else:
                st.write(overall.get("summary", ""))
                st.write(
                    f'**التقييم النهائي:** '
                    f'{overall.get("overall_score", "—")}'
                )
                st.write(
                    f'**أهم إيجابية:** '
                    f'{overall.get("key_positive", "—")}'
                )
                st.write(
                    f'**أهم خطر:** '
                    f'{overall.get("key_risk", "—")}'
                )
                st.info(overall.get("verdict", ""))

            if overall.get("available") is not False and st.button(
                "إرسال خلاصة السهم إلى تيليجرام",
                use_container_width=True,
            ):
                message = (
                    f'<b>⚡ تحليل سهم '
                    f'{html.escape(result.get("symbol", ""))}</b>\n'
                    f'<b>عدد الأخبار:</b> '
                    f'{result.get("count", 0)}\n'
                    f'<b>آخر سعر:</b> {latest_price_text}\n'
                    f'<b>متوسط النظام:</b> '
                    f'{result.get("system_average", 0)}\n'
                    f'<b>متوسط AI:</b> '
                    f'{result.get("ai_average", 0)}\n'
                    f'<b>الخلاصة:</b> '
                    f'{html.escape(str(overall.get("summary", "")))}\n'
                    f'<b>أهم إيجابية:</b> '
                    f'{html.escape(str(overall.get("key_positive", "")))}\n'
                    f'<b>أهم خطر:</b> '
                    f'{html.escape(str(overall.get("key_risk", "")))}\n'
                    f'<b>الرأي النهائي:</b> '
                    f'{html.escape(str(overall.get("verdict", "")))}'
                )

                ok, message_text = telegram_send(message)
                if ok:
                    st.success(message_text)
                else:
                    st.error(message_text)

        st.markdown("### الأخبار المجمعة")
        render_results(
            result.get("articles", []),
            max_items=150,
        )

with tab_learning:
    st.subheader("سجل التعلّم من النتائج")

    st.markdown(
        """
        <div class="note">
          يحتفظ النظام بدرجة الخبر ورأي النظام وAI وسعر لحظة الرصد،
          ثم يحدث أعلى وأدنى وآخر سعر ويضيف تعليقًا للمراجعة والتطوير.
          التخزين الحالي ملف JSON داخل التطبيق.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_update, col_reload = st.columns(2)

    with col_update:
        if st.button(
            "تحديث الأسعار الآن",
            type="primary",
            use_container_width=True,
        ):
            try:
                with st.spinner(
                    "جارٍ تحديث نتائج الإشارات..."
                ):
                    update_result = update_signal_outcomes()

                st.success(
                    f'تحدث {update_result["updated_records"]} سجل '
                    f'لعدد {update_result["updated_tickers"]} سهم.'
                )

                if update_result["errors"]:
                    st.warning(
                        "بعض الأسعار لم تتوفر: "
                        + " | ".join(
                            update_result["errors"][:5]
                        )
                    )

            except Exception as exc:
                st.error(str(exc))

    with col_reload:
        if st.button(
            "تحديث القائمة",
            use_container_width=True,
        ):
            st.rerun()

    signals = load_json(config.SIGNALS_FILE, [])

    symbol_filter = st.text_input(
        "فلترة السجل برمز سهم",
        placeholder="مثال: NTCL",
        key="learning_symbol_filter",
    ).strip().upper()

    if symbol_filter:
        signals = [
            record
            for record in signals
            if str(
                record.get("symbol") or ""
            ).upper()
            == symbol_filter
        ]

    signals = sorted(
        signals,
        key=lambda record: record.get(
            "detected_at",
            "",
        ),
        reverse=True,
    )

    st.caption(
        f"عدد السجلات المعروضة: {len(signals)}"
    )

    for record in signals[:300]:
        st.markdown(
            render_signal(record),
            unsafe_allow_html=True,
        )

with tab_account:
    account = load_account()
    totals = usage_totals()

    st.subheader("OpenAI والتكلفة")

    st.markdown(
        f"""
        <div class="metrics">
          <div class="metric">
            <b>${totals["today_cost"]:.4f}</b>
            <small>مصروف اليوم</small>
          </div>
          <div class="metric">
            <b>${totals["week_cost"]:.4f}</b>
            <small>مصروف الأسبوع</small>
          </div>
          <div class="metric">
            <b>${totals["estimated_remaining"]:.2f}</b>
            <small>متبقي تقديري</small>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    starting_balance = st.number_input(
        "الرصيد المشحون بالدولار",
        min_value=0.0,
        value=float(
            account.get(
                "starting_balance_usd",
                5.0,
            )
        ),
        step=1.0,
    )

    weekly_budget = st.number_input(
        "الحد الأسبوعي بالدولار",
        min_value=0.0,
        value=float(
            account.get(
                "weekly_budget_usd",
                2.0,
            )
        ),
        step=0.5,
    )

    ai_mode = st.selectbox(
        "استخدام AI",
        ["economic", "professional", "off"],
        index=[
            "economic",
            "professional",
            "off",
        ].index(
            str(
                account.get(
                    "ai_mode",
                    "economic",
                )
            )
        ),
        format_func=lambda value: {
            "economic": "اقتصادي — الأخبار الواضحة فقط",
            "professional": "احترافي — أخبار أكثر",
            "off": "إيقاف AI",
        }[value],
    )

    if st.button(
        "حفظ إعدادات الحساب",
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

    col_openai, col_report = st.columns(2)

    with col_openai:
        if st.button(
            "فحص OpenAI الآن",
            use_container_width=True,
        ):
            openai_status = daily_openai_status()
            if openai_status["connected"]:
                st.success(openai_status["message"])
            else:
                st.error(openai_status["message"])

    with col_report:
        if st.button(
            "إرسال تقرير الحساب",
            use_container_width=True,
        ):
            openai_status = daily_openai_status()
            message = (
                "<b>⚡ حساب برق نيوز</b>\n"
                f"<b>حالة OpenAI:</b> "
                f'{openai_status["message"]}\n'
                f"<b>مصروف اليوم:</b> "
                f'${openai_status["today_cost"]:.4f}\n'
                f"<b>مصروف الأسبوع:</b> "
                f'${openai_status["week_cost"]:.4f}\n'
                f"<b>المتبقي التقديري:</b> "
                f'${openai_status["estimated_remaining"]:.4f}'
            )

            ok, message_text = telegram_send(message)
            if ok:
                st.success(message_text)
            else:
                st.error(message_text)

    st.subheader("المدفوعات")

    payments = load_json(config.PAYMENTS_FILE, [])
    amount = st.number_input(
        "إضافة شحن بالدولار",
        min_value=0.0,
        value=0.0,
        step=1.0,
    )
    note = st.text_input("ملاحظة الدفعة")

    if st.button(
        "تسجيل الدفعة",
        use_container_width=True,
    ):
        if amount <= 0:
            st.warning("أدخل مبلغًا أكبر من صفر.")
        else:
            payments.append(
                {
                    "date": datetime.now(
                        RIYADH
                    ).isoformat(),
                    "amount_usd": amount,
                    "note": note,
                }
            )
            save_json(
                config.PAYMENTS_FILE,
                payments,
            )
            account["starting_balance_usd"] = (
                float(
                    account.get(
                        "starting_balance_usd",
                        0,
                    )
                )
                + amount
            )
            save_account(account)
            st.success("تم تسجيل الدفعة.")
            st.rerun()

    for payment in reversed(payments[-10:]):
        st.caption(
            f'${payment.get("amount_usd", 0):.2f} — '
            f'{payment.get("note", "")} — '
            f'{format_saudi_time(payment.get("date"))}'
        )
