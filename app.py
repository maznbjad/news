from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

import config
from core import (
    article_message,
    daily_openai_status,
    fetch_news,
    format_saudi_time,
    is_positive,
    load_account,
    load_control,
    load_json,
    process_articles,
    save_account,
    save_json,
    telegram_send,
    update_control,
    usage_totals,
)

RIYADH = ZoneInfo("Asia/Riyadh")

st.set_page_config(
    page_title="برق نيوز",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

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
      direction: rtl;
      text-align: right;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Tahoma, Arial, sans-serif;
    }

    .stApp {
      background:
        radial-gradient(circle at 100% -10%, rgba(255,212,59,.12), transparent 33%),
        var(--bg);
      color: var(--text);
    }

    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    #MainMenu,
    footer {
      display:none!important;
    }

    .block-container {
      max-width:620px!important;
      padding:20px 14px 90px!important;
    }

    h1,h2,h3,p,label,span,div { color:var(--text); }

    .top {
      display:flex;
      justify-content:space-between;
      align-items:center;
      margin-bottom:16px;
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
      border-radius:24px;
      padding:20px;
      margin:10px 0 14px;
    }

    .hero h2 {
      margin:0 0 7px;
      font-size:24px;
    }

    .hero p {
      margin:0;
      color:#aab2bf!important;
      font-size:13px;
      line-height:1.7;
    }

    [data-testid="stButton"] button {
      min-height:50px;
      border-radius:16px;
      border:1px solid var(--line);
      background:var(--panel);
      font-weight:900;
    }

    .big [data-testid="stButton"] button {
      min-height:78px;
      font-size:20px;
      background:linear-gradient(145deg,var(--yellow),#ffb800);
      color:#171000;
      border:0;
    }

    .card {
      display:block;
      text-decoration:none!important;
      border:1px solid var(--line);
      border-radius:18px;
      padding:14px;
      margin:9px 0;
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

    .metrics {
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:8px;
      margin:12px 0;
    }

    .metric {
      border:1px solid var(--line);
      background:var(--panel);
      border-radius:16px;
      padding:12px;
    }

    .metric b { font-size:18px; }

    .metric small {
      display:block;
      color:var(--muted);
      margin-top:3px;
    }

    .note {
      font-size:11px;
      color:var(--muted)!important;
      line-height:1.6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_card(article: dict) -> str:
    ai = article.get("ai") or {}
    sentiment = str(
        ai.get("sentiment")
        or article.get("system_sentiment")
        or "neutral"
    )

    if sentiment == "positive":
        css_class = "pos"
    elif sentiment in ("negative", "mixed"):
        css_class = "neg"
    else:
        css_class = "neu"

    tickers = " • ".join(article.get("tickers") or ["—"])
    url = html.escape(str(article.get("url") or "#"), quote=True)
    target = "_blank" if url != "#" else "_self"

    return (
        f'<a class="card {css_class}" href="{url}" target="{target}">'
        f'<div class="row">'
        f'<span class="ticker">{html.escape(tickers)}</span>'
        f'<span class="time">{html.escape(str(article.get("published_display", "—")))}</span>'
        f'</div>'
        f'<div class="headline">{html.escape(str(article.get("title", "")))}</div>'
        f'<div class="scores">'
        f'<div class="score">'
        f'<div class="num">{article.get("system_score", 0)}</div>'
        f'<div class="lab">تقييم النظام</div>'
        f'</div>'
        f'<div class="score">'
        f'<div class="num">{ai.get("score", "—")}</div>'
        f'<div class="lab">تقييم AI</div>'
        f'</div>'
        f'</div>'
        f'</a>'
    )


def render_results(items: list[dict]) -> None:
    if not items:
        st.info("لا توجد نتائج.")
        return

    for article in items:
        st.markdown(render_card(article), unsafe_allow_html=True)


control = load_control()
status = load_json(config.STATUS_FILE, {})
monitoring_enabled = bool(control.get("enabled"))
status_css = "status live" if monitoring_enabled else "status"
status_text = "● الرصد يعمل" if monitoring_enabled else "الرصد متوقف"

st.markdown(
    f"""
    <div class="top">
      <div>
        <div class="brand">⚡ برق نيوز</div>
        <div class="sub">يرصد ويرسل إلى تيليجرام</div>
      </div>
      <div class="{status_css}">{status_text}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_monitor, tab_retrieve, tab_account = st.tabs(
    ["الرصد", "الاسترجاع", "الحساب"]
)

with tab_monitor:
    st.markdown(
        """
        <div class="hero">
          <h2>الرصد الإيجابي</h2>
          <p>
            الرصد يعمل بعملية مستقلة، لذلك لا يتوقف عند التنقل بين صفحات الموقع.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="big">', unsafe_allow_html=True)
    if st.button(
        "إيقاف الرصد" if monitoring_enabled else "تشغيل الرصد",
        type="primary",
        use_container_width=True,
    ):
        update_control(
            enabled=not monitoring_enabled,
            positive_only=True,
            ai_enabled=True,
        )
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    col_test, col_refresh = st.columns(2)

    with col_test:
        if st.button("اختبار تيليجرام", use_container_width=True):
            ok, message = telegram_send(
                "⚡ <b>برق نيوز</b>\nتم الاتصال بنجاح"
            )
            if ok:
                st.success(message)
            else:
                st.error(message)

    with col_refresh:
        if st.button("تحديث العرض", use_container_width=True):
            st.rerun()

    st.caption(
        status.get(
            "message",
            "شغّل run_barq.bat لتشغيل عامل الرصد",
        )
    )

    if status.get("last_check"):
        st.caption(
            f'آخر فحص: {format_saudi_time(status.get("last_check"))} — '
            f'آخر إرسال: {status.get("last_sent", 0)}'
        )

    st.subheader("آخر النتائج")
    render_results(load_json(config.FEED_FILE, [])[:30])

with tab_retrieve:
    st.subheader("استرجاع الأخبار وإرسالها")

    period = st.selectbox(
        "الفترة",
        ["آخر ساعتين", "آخر 6 ساعات", "آخر 24 ساعة", "آخر أسبوع"],
    )
    news_type = st.selectbox(
        "النوع",
        ["إيجابية", "سلبية", "الكل"],
    )
    use_ai = st.checkbox("تحليل AI", value=True)

    hours = {
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
            with st.spinner("جارٍ الجلب والتحليل..."):
                raw_items = fetch_news(
                    hours=hours,
                    limit=config.NEWS_LIMIT,
                )
                results = process_articles(
                    raw_items,
                    hours,
                    use_ai,
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
                            (article.get("ai") or {}).get("sentiment")
                            in ("negative", "mixed")
                            or int(article.get("system_score", 0)) < 0
                        )
                    ]

                save_json(
                    config.RETRIEVAL_FILE,
                    results[:500],
                )

                sent_count = 0
                for article in results[:50]:
                    ok, _ = telegram_send(
                        article_message(article)
                    )
                    if ok:
                        sent_count += 1

                st.success(
                    f"تم العثور على {len(results)} خبر، "
                    f"وإرسال {sent_count} إشعار"
                )

        except Exception as exc:
            st.error(str(exc))

    st.subheader("قائمة الاسترجاع")
    render_results(
        load_json(config.RETRIEVAL_FILE, [])[:100]
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

    st.markdown(
        """
        <div class="note">
          لا يمكن لمفتاح OpenAI العادي إرجاع الرصيد النقدي الحقيقي.
          التطبيق يفحص يوميًا أن الحساب يسمح بطلب جديد،
          ويحسب المتبقي تقديريًا من الرصيد الذي تدخله.
        </div>
        """,
        unsafe_allow_html=True,
    )

    starting_balance = st.number_input(
        "الرصيد المشحون بالدولار",
        min_value=0.0,
        value=float(account.get("starting_balance_usd", 5.0)),
        step=1.0,
    )

    weekly_budget = st.number_input(
        "الحد الأسبوعي بالدولار",
        min_value=0.0,
        value=float(account.get("weekly_budget_usd", 2.0)),
        step=0.5,
    )

    ai_mode = st.selectbox(
        "استخدام AI",
        ["economic", "professional", "off"],
        index=["economic", "professional", "off"].index(
            str(account.get("ai_mode", "economic"))
        ),
        format_func=lambda value: {
            "economic": "اقتصادي — الأخبار القوية فقط",
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
        st.success("تم الحفظ")

    col_openai, col_report = st.columns(2)

    with col_openai:
        if st.button(
            "فحص OpenAI الآن",
            use_container_width=True,
        ):
            result = daily_openai_status()
            if result["connected"]:
                st.success(result["message"])
            else:
                st.error(result["message"])

    with col_report:
        if st.button(
            "إرسال تقرير الحساب",
            use_container_width=True,
        ):
            result = daily_openai_status()
            ok, message = telegram_send(
                "<b>⚡ حساب برق نيوز</b>\n"
                f'<b>حالة OpenAI:</b> {result["message"]}\n'
                f'<b>مصروف اليوم:</b> ${result["today_cost"]:.4f}\n'
                f'<b>مصروف الأسبوع:</b> ${result["week_cost"]:.4f}\n'
                f'<b>المتبقي التقديري:</b> '
                f'${result["estimated_remaining"]:.4f}'
            )
            if ok:
                st.success(message)
            else:
                st.error(message)

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
                    "date": datetime.now(RIYADH).isoformat(),
                    "amount_usd": amount,
                    "note": note,
                }
            )
            save_json(
                config.PAYMENTS_FILE,
                payments,
            )

            account["starting_balance_usd"] = (
                float(account.get("starting_balance_usd", 0))
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
