from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests

import config

RIYADH = ZoneInfo("Asia/Riyadh")

POSITIVE_RULES = [
    ("fda approval", 95, "اعتماد FDA"),
    ("approved by the fda", 95, "اعتماد FDA"),
    ("fda clearance", 85, "تصريح FDA"),
    ("510(k) clearance", 82, "تصريح 510(k)"),
    ("acquisition", 85, "استحواذ"),
    ("to be acquired", 90, "اتفاق استحواذ"),
    ("merger agreement", 82, "اتفاق اندماج"),
    ("strategic partnership", 65, "شراكة استراتيجية"),
    ("partnership", 48, "شراكة"),
    ("awarded contract", 75, "عقد جديد"),
    ("contract award", 75, "عقد جديد"),
    ("purchase order", 58, "أمر شراء"),
    ("new order", 55, "طلبية جديدة"),
    ("phase 3", 75, "مرحلة ثالثة"),
    ("phase iii", 75, "مرحلة ثالثة"),
    ("positive topline", 78, "نتائج إيجابية"),
    ("positive results", 70, "نتائج إيجابية"),
    ("met primary endpoint", 78, "حقق الهدف الرئيسي"),
    ("beats estimates", 62, "تفوق على التوقعات"),
    ("beat estimates", 62, "تفوق على التوقعات"),
    ("raises guidance", 64, "رفع التوقعات"),
    ("raised guidance", 64, "رفع التوقعات"),
    ("patent granted", 55, "براءة اختراع"),
    ("share repurchase", 58, "إعادة شراء أسهم"),
    ("buyback", 55, "إعادة شراء"),
    ("grant awarded", 55, "منحة"),
    ("received grant", 55, "منحة"),
    ("launches", 42, "إطلاق"),
    ("commercial launch", 58, "إطلاق تجاري"),
    ("expands", 40, "توسع"),
    ("price target raised", 48, "رفع السعر المستهدف"),
    ("upgrade", 48, "ترقية تقييم"),
]

NEGATIVE_RULES = [
    ("bankruptcy", -100, "إفلاس"),
    ("chapter 11", -100, "إفلاس فصل 11"),
    ("delisting", -88, "خطر شطب"),
    ("nasdaq notice", -58, "إشعار ناسداك"),
    ("non-compliance", -62, "عدم امتثال"),
    ("public offering", -78, "طرح أسهم"),
    ("registered direct offering", -82, "طرح مباشر"),
    ("at-the-market offering", -72, "بيع عبر السوق"),
    ("shelf registration", -48, "تسجيل رف"),
    ("warrant exercise", -58, "ممارسة ضمانات"),
    ("clinical hold", -92, "تعليق سريري"),
    ("trial failed", -92, "فشل تجربة"),
    ("did not meet primary endpoint", -92, "فشل الهدف الرئيسي"),
    ("misses estimates", -58, "دون التوقعات"),
    ("missed estimates", -58, "دون التوقعات"),
    ("lowers guidance", -68, "خفض التوقعات"),
    ("lowered guidance", -68, "خفض التوقعات"),
    ("reverse stock split", -52, "تجزئة عكسية"),
    ("going concern", -68, "شكوك الاستمرارية"),
    ("investigation", -45, "تحقيق"),
    ("downgrade", -48, "خفض تقييم"),
    ("price target lowered", -45, "خفض السعر المستهدف"),
    ("layoffs", -42, "تسريح موظفين"),
]

NOISE_PATTERNS = [
    "complete transcript",
    "earnings call transcript",
    "weekly recap",
    "daily recap",
    "top stories",
    "morning brief",
]


def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


def default_control() -> dict[str, Any]:
    return {
        "enabled": False,
        "positive_only": True,
        "ai_enabled": True,
        "updated_at": "",
    }


def load_control() -> dict[str, Any]:
    data = default_control()
    data.update(load_json(config.CONTROL_FILE, {}))
    return data


def update_control(**values: Any) -> dict[str, Any]:
    data = load_control()
    data.update(values)
    data["updated_at"] = datetime.now(RIYADH).isoformat()
    save_json(config.CONTROL_FILE, data)
    return data


def default_account() -> dict[str, Any]:
    return {
        "starting_balance_usd": 5.0,
        "weekly_budget_usd": 2.0,
        "ai_mode": "economic",
        "last_daily_report": "",
    }


def load_account() -> dict[str, Any]:
    data = default_account()
    data.update(load_json(config.ACCOUNT_FILE, {}))
    return data


def save_account(data: dict[str, Any]) -> None:
    merged = default_account()
    merged.update(data)
    save_json(config.ACCOUNT_FILE, merged)


def load_symbols() -> set[str]:
    if not config.SYMBOLS_FILE.exists():
        return set()

    return {
        item.strip().upper().replace("$", "")
        for item in re.split(
            r"[\s,;]+",
            config.SYMBOLS_FILE.read_text(
                encoding="utf-8",
                errors="ignore",
            ),
        )
        if item.strip()
    }


def clean_text(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def normalize_tickers(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = re.split(r"[\s,;]+", value)
    elif isinstance(value, list):
        raw = value
    elif value:
        raw = [value]
    else:
        raw = []

    output: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            candidate = item.get("symbol") or item.get("ticker") or ""
        else:
            candidate = item

        symbol = str(candidate or "").strip().upper().replace("$", "")
        if symbol and symbol not in output:
            output.append(symbol)

    return output


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )
        except Exception:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def ordinal_day(day: int) -> str:
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {
            1: "st",
            2: "nd",
            3: "rd",
        }.get(day % 10, "th")

    return f"{day}{suffix}"


def format_saudi_time(value: Any) -> str:
    dt = parse_time(value)
    if dt is None:
        return "—" if not value else str(value)

    local = dt.astimezone(RIYADH)
    return (
        f"{local.strftime('%b')} "
        f"{ordinal_day(local.day)} - "
        f"{local.strftime('%I:%M%p').lower()}"
    )


def system_analyze(title: str, teaser: str) -> dict[str, Any]:
    combined = f"{title} {teaser}".lower()

    if any(pattern in combined for pattern in NOISE_PATTERNS):
        return {
            "score": 0,
            "sentiment": "neutral",
            "reason": "خبر تجميعي أو منخفض الأهمية",
        }

    matches = []
    for phrase, score, reason in POSITIVE_RULES + NEGATIVE_RULES:
        if phrase in combined:
            matches.append((score, reason))

    if not matches:
        return {
            "score": 0,
            "sentiment": "neutral",
            "reason": "لا توجد إشارة آلية قوية",
        }

    strongest_score = max(matches, key=lambda item: abs(item[0]))[0]
    reasons: list[str] = []

    for _, reason in sorted(
        matches,
        key=lambda item: abs(item[0]),
        reverse=True,
    ):
        if reason not in reasons:
            reasons.append(reason)

    return {
        "score": strongest_score,
        "sentiment": "positive" if strongest_score > 0 else "negative",
        "reason": "، ".join(reasons[:3]),
    }


def normalize_article(item: dict[str, Any]) -> dict[str, Any]:
    title = clean_text(item.get("title"))
    teaser = clean_text(item.get("teaser") or item.get("body"))
    published = str(
        item.get("published")
        or item.get("created")
        or item.get("last_updated")
        or ""
    )
    analysis = system_analyze(title, teaser)

    article_id = str(
        item.get("benzinga_id")
        or item.get("id")
        or f"{published}:{title}"
    )

    return {
        "id": article_id,
        "title": title or "خبر بلا عنوان",
        "teaser": teaser,
        "published": published,
        "published_display": format_saudi_time(published),
        "url": str(item.get("url") or ""),
        "tickers": normalize_tickers(
            item.get("tickers")
            or item.get("stocks")
        ),
        "channels": item.get("channels") or [],
        "tags": item.get("tags") or [],
        "system_score": int(analysis["score"]),
        "system_sentiment": analysis["sentiment"],
        "system_reason": analysis["reason"],
    }


# Alias يحمي من أخطاء الاسم القديمة.
normalize = normalize_article


def extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("results", "data", "news"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

    return []


def _url_with_api_key(url: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("apiKey", config.MASSIVE_API_KEY)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def massive_get(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = 40,
) -> requests.Response:
    if not config.MASSIVE_API_KEY:
        raise RuntimeError("MASSIVE_API_KEY غير مضاف.")

    request_params = dict(params or {})
    existing_query = dict(
        parse_qsl(
            urlsplit(url).query,
            keep_blank_values=True,
        )
    )
    if "apiKey" not in existing_query:
        request_params.setdefault(
            "apiKey",
            config.MASSIVE_API_KEY,
        )

    response = requests.get(
        url,
        params=request_params,
        timeout=timeout,
    )

    if response.status_code in (401, 403):
        request_params.pop("apiKey", None)
        response = requests.get(
            url,
            params=request_params,
            headers={
                "Authorization": f"Bearer {config.MASSIVE_API_KEY}"
            },
            timeout=timeout,
        )

    response.raise_for_status()
    return response


def fetch_news(
    hours: float | None = None,
    limit: int | None = None,
    ticker: str | None = None,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    target_limit = min(
        max(int(limit or config.NEWS_LIMIT), 1),
        50000,
    )
    page_limit = min(target_limit, 50000)
    page_cap = max_pages or config.NEWS_MAX_PAGES

    params: dict[str, Any] = {
        "limit": page_limit,
        "sort": "published.desc",
    }

    if hours is not None:
        since = datetime.now(timezone.utc) - timedelta(hours=float(hours))
        params["published.gte"] = (
            since.isoformat().replace("+00:00", "Z")
        )

    if ticker:
        params["tickers"] = ticker.strip().upper()

    url: str | None = config.MASSIVE_NEWS_URL
    items: list[dict[str, Any]] = []
    pages = 0

    while url and pages < page_cap and len(items) < target_limit:
        response = massive_get(
            url,
            params=params if pages == 0 else None,
            timeout=45,
        )
        payload = response.json()
        items.extend(extract_items(payload))
        pages += 1

        next_url = (
            payload.get("next_url")
            if isinstance(payload, dict)
            else None
        )

        if not next_url:
            break

        url = _url_with_api_key(str(next_url))

    # إزالة التكرار مع الحفاظ على الترتيب.
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in items:
        key = str(
            item.get("benzinga_id")
            or item.get("id")
            or (
                str(item.get("published"))
                + ":"
                + str(item.get("title"))
            )
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return unique[:target_limit]


def extract_response_text(data: dict[str, Any]) -> str:
    if data.get("output_text"):
        return str(data["output_text"])

    parts: list[str] = []
    output = data.get("output")
    if not isinstance(output, list):
        return ""

    for item in output:
        if not isinstance(item, dict):
            continue

        content = item.get("content")
        if not isinstance(content, list):
            continue

        for block in content:
            if isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))

    return "\n".join(parts)


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}

        try:
            return json.loads(match.group(0))
        except Exception:
            return {}


def record_usage(
    data: dict[str, Any],
    item_id: str,
) -> dict[str, Any]:
    usage = data.get("usage") or {}
    input_tokens = int(
        usage.get("input_tokens")
        or usage.get("prompt_tokens")
        or 0
    )
    output_tokens = int(
        usage.get("output_tokens")
        or usage.get("completion_tokens")
        or 0
    )
    cost = (
        input_tokens
        / 1_000_000
        * config.OPENAI_INPUT_USD_PER_1M
        + output_tokens
        / 1_000_000
        * config.OPENAI_OUTPUT_USD_PER_1M
    )

    ledger = load_json(config.USAGE_FILE, [])
    ledger.append(
        {
            "time": datetime.now(RIYADH).isoformat(),
            "item_id": item_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 8),
        }
    )
    save_json(config.USAGE_FILE, ledger[-20000:])

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 8),
    }


def ai_analyze(article: dict[str, Any]) -> dict[str, Any]:
    if not config.OPENAI_API_KEY:
        return {
            "score": 0,
            "sentiment": "not_run",
            "summary": "لم يتم تشغيل AI",
            "reason": "مفتاح OpenAI غير مضاف",
            "squeeze_score": 0,
            "dilution_risk": 0,
            "cost_usd": 0.0,
        }

    prompt = f"""
حلل خبر سهم أمريكي بشكل صارم. لا تعتبر العنوان إيجابيًا تلقائيًا.
افحص: قوة المحفز، الطرح والتخفيف، الضمانات، خطر الشطب،
التجزئة العكسية، احتمال أن يكون الخبر مسعرًا، وقابلية السكويز.

أعد JSON فقط:
{{
  "score": عدد صحيح من -100 إلى 100,
  "sentiment": "positive أو negative أو neutral أو mixed",
  "summary": "رأي عربي قصير وواضح",
  "reason": "سبب القرار بالعربية",
  "squeeze_score": عدد من 0 إلى 100,
  "dilution_risk": عدد من 0 إلى 100
}}

الرموز: {article.get("tickers")}
العنوان: {article.get("title")}
الملخص: {article.get("teaser")}
تقييم النظام: {article.get("system_score")}
رأي النظام: {article.get("system_reason")}
"""

    response = requests.post(
        config.OPENAI_URL,
        headers={
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.OPENAI_MODEL,
            "input": prompt,
            "temperature": 0.1,
        },
        timeout=60,
    )

    if response.status_code == 429:
        detail = ""
        try:
            detail = (
                response.json()
                .get("error", {})
                .get("message", "")
            )
        except Exception:
            detail = response.text[:300]

        raise RuntimeError(
            "OpenAI 429: "
            + (
                detail
                or "الرصيد غير كافٍ أو تم تجاوز حد الاستخدام."
            )
        )

    response.raise_for_status()
    data = response.json()
    result = parse_json_object(extract_response_text(data))

    result["score"] = max(
        -100,
        min(100, int(result.get("score", 0))),
    )
    result["squeeze_score"] = max(
        0,
        min(100, int(result.get("squeeze_score", 0))),
    )
    result["dilution_risk"] = max(
        0,
        min(100, int(result.get("dilution_risk", 0))),
    )

    usage = record_usage(
        data,
        f"article:{article.get('id')}",
    )
    result["cost_usd"] = usage["cost_usd"]
    return result


def ai_should_run(
    article: dict[str, Any],
    mode: str,
) -> bool:
    score = abs(int(article.get("system_score", 0)))

    if mode == "off":
        return False

    if mode == "economic":
        return score >= 45

    return score >= config.AI_ANALYZE_SYSTEM_MIN


def telegram_send(text: str) -> tuple[bool, str]:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False, "بيانات تيليجرام ناقصة."

    response = requests.post(
        (
            "https://api.telegram.org/bot"
            f"{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        ),
        json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )

    try:
        data = response.json()
    except Exception:
        data = {}

    if response.ok and data.get("ok"):
        return True, "تم الإرسال."

    return False, str(
        data.get("description")
        or response.text[:300]
    )


def fetch_price_snapshot(symbol: str) -> dict[str, Any]:
    symbol = str(symbol or "").strip().upper()
    if not symbol:
        raise ValueError("رمز السهم فارغ.")

    response = massive_get(
        config.MASSIVE_SNAPSHOT_URL.format(symbol=symbol),
        timeout=30,
    )
    payload = response.json()
    ticker_data = payload.get("ticker") or {}

    price = None
    source = None
    updated = ticker_data.get("updated")

    candidates = [
        ("lastTrade", "p"),
        ("min", "c"),
        ("day", "c"),
        ("prevDay", "c"),
    ]

    for section, key in candidates:
        block = ticker_data.get(section) or {}
        value = block.get(key)
        if value is None:
            continue

        try:
            price = float(value)
            source = section
            break
        except Exception:
            continue

    if price is None:
        raise RuntimeError(
            f"لم يرجع Massive سعرًا متاحًا للرمز {symbol}."
        )

    return {
        "symbol": symbol,
        "price": price,
        "source": source,
        "updated": updated,
        "checked_at": datetime.now(RIYADH).isoformat(),
    }


def signal_sentiment(article: dict[str, Any]) -> str:
    ai = article.get("ai") or {}
    ai_sentiment = str(ai.get("sentiment") or "")

    if ai_sentiment in ("positive", "negative", "mixed"):
        return ai_sentiment

    return str(
        article.get("system_sentiment")
        or "neutral"
    )


def should_track_signal(article: dict[str, Any]) -> bool:
    system_score = abs(int(article.get("system_score", 0)))
    ai = article.get("ai") or {}

    try:
        ai_score = abs(int(ai.get("score", 0)))
    except Exception:
        ai_score = 0

    return system_score >= 35 or ai_score >= 45


def outcome_comment(record: dict[str, Any]) -> str:
    change = record.get("last_change_pct")
    if change is None:
        return "بانتظار توفر سعر للمقارنة."

    sentiment = str(record.get("signal_sentiment") or "neutral")
    change = float(change)

    if sentiment == "positive":
        if change >= 15:
            return "السوق أكد الإشارة الإيجابية بقوة."
        if change >= 5:
            return "الإشارة الإيجابية انعكست بارتفاع ملحوظ."
        if change <= -15:
            return "السوق خالف الإشارة الإيجابية بقوة؛ يحتاج السبب للمراجعة."
        if change <= -5:
            return "الخبر الإيجابي لم ينعكس سعريًا حتى الآن."
        return "استجابة السعر محدودة بعد الإشارة الإيجابية."

    if sentiment in ("negative", "mixed"):
        if change <= -15:
            return "السوق أكد الأثر السلبي بقوة."
        if change <= -5:
            return "الأثر السلبي ظهر في حركة السعر."
        if change >= 15:
            return "السوق خالف الإشارة السلبية بقوة؛ يستحق المراجعة."
        if change >= 5:
            return "السعر ارتفع رغم الإشارة السلبية."
        return "استجابة السعر محدودة بعد الإشارة السلبية."

    return "الإشارة محايدة؛ يتم حفظ النتيجة للمقارنة لاحقًا."


def record_signal(
    article: dict[str, Any],
    price_map: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not should_track_signal(article):
        return []

    records = load_json(config.SIGNALS_FILE, [])
    existing = {
        str(item.get("signal_id")): item
        for item in records
    }
    created: list[dict[str, Any]] = []
    ai = article.get("ai") or {}

    for symbol in (article.get("tickers") or [])[:5]:
        signal_id = f"{article.get('id')}:{symbol}"
        if signal_id in existing:
            created.append(existing[signal_id])
            continue

        snapshot = None
        snapshot_error = None

        try:
            if price_map is not None:
                if symbol in price_map:
                    snapshot = price_map[symbol]
                    if snapshot is None:
                        snapshot_error = (
                            "سعر Snapshot غير متاح "
                            "ضمن الطلب المجمع."
                        )
                else:
                    snapshot_error = (
                        "لم يُطلب سعر هذا الرمز "
                        "ضمن الدفعة الحالية."
                    )
            else:
                snapshot = fetch_price_snapshot(symbol)
        except Exception as exc:
            snapshot_error = str(exc)

        initial_price = (
            float(snapshot["price"])
            if snapshot and snapshot.get("price") is not None
            else None
        )

        record = {
            "signal_id": signal_id,
            "article_id": str(article.get("id")),
            "symbol": symbol,
            "title": article.get("title"),
            "url": article.get("url"),
            "published": article.get("published"),
            "detected_at": datetime.now(RIYADH).isoformat(),
            "signal_sentiment": signal_sentiment(article),
            "system_score": article.get("system_score", 0),
            "system_opinion": article.get("system_reason"),
            "ai_score": ai.get("score"),
            "ai_opinion": ai.get("summary"),
            "ai_reason": ai.get("reason"),
            "squeeze_score": ai.get("squeeze_score"),
            "dilution_risk": ai.get("dilution_risk"),
            "price_at_signal": initial_price,
            "latest_price": initial_price,
            "highest_price": initial_price,
            "lowest_price": initial_price,
            "last_change_pct": 0.0 if initial_price else None,
            "highest_change_pct": 0.0 if initial_price else None,
            "lowest_change_pct": 0.0 if initial_price else None,
            "last_price_check": (
                snapshot.get("checked_at")
                if snapshot
                else None
            ),
            "price_source": (
                snapshot.get("source")
                if snapshot
                else None
            ),
            "price_error": snapshot_error,
            "updates": 0,
            "development_comment": (
                "تم حفظ الإشارة وسيتم تتبع السعر."
                if initial_price
                else "تم حفظ الإشارة، لكن السعر غير متاح حاليًا."
            ),
        }

        records.append(record)
        existing[signal_id] = record
        created.append(record)

    save_json(config.SIGNALS_FILE, records[-10000:])
    return created



def record_signals_batch(
    articles: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    trackable = [
        article
        for article in articles
        if should_track_signal(article)
    ]

    symbols: list[str] = []
    for article in trackable:
        for symbol in article.get("tickers") or []:
            if symbol not in symbols:
                symbols.append(symbol)

    symbols = symbols[
        : config.MAX_TRACKED_TICKERS_PER_UPDATE
    ]

    price_map: dict[str, dict[str, Any] | None] = {
        symbol: None
        for symbol in symbols
    }
    for symbol in symbols:
        try:
            price_map[symbol] = fetch_price_snapshot(symbol)
        except Exception:
            price_map[symbol] = None

    output: dict[str, list[dict[str, Any]]] = {}
    for article in trackable:
        records = record_signal(
            article,
            price_map=price_map,
        )
        output[str(article.get("id"))] = records

    return output

def update_signal_outcomes(
    max_tickers: int | None = None,
) -> dict[str, Any]:
    records = load_json(config.SIGNALS_FILE, [])
    if not records:
        return {
            "updated_records": 0,
            "updated_tickers": 0,
            "errors": [],
        }

    cutoff = datetime.now(timezone.utc) - timedelta(
        days=config.SIGNAL_TRACK_DAYS
    )

    active_symbols: list[str] = []
    for record in reversed(records):
        detected = parse_time(record.get("detected_at"))
        if detected and detected < cutoff:
            continue

        symbol = str(record.get("symbol") or "").upper()
        if symbol and symbol not in active_symbols:
            active_symbols.append(symbol)

    active_symbols = active_symbols[
        : max_tickers
        or config.MAX_TRACKED_TICKERS_PER_UPDATE
    ]

    snapshots: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    for symbol in active_symbols:
        try:
            snapshots[symbol] = fetch_price_snapshot(symbol)
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")

    updated_records = 0

    for record in records:
        symbol = str(record.get("symbol") or "").upper()
        snapshot = snapshots.get(symbol)
        if not snapshot:
            continue

        current_price = float(snapshot["price"])
        initial_price = record.get("price_at_signal")

        if initial_price is None:
            record["price_at_signal"] = current_price
            initial_price = current_price

        initial_price = float(initial_price)
        highest_price = record.get("highest_price")
        lowest_price = record.get("lowest_price")

        record["latest_price"] = current_price
        record["highest_price"] = (
            current_price
            if highest_price is None
            else max(float(highest_price), current_price)
        )
        record["lowest_price"] = (
            current_price
            if lowest_price is None
            else min(float(lowest_price), current_price)
        )

        if initial_price > 0:
            record["last_change_pct"] = round(
                (
                    current_price
                    / initial_price
                    - 1
                )
                * 100,
                2,
            )
            record["highest_change_pct"] = round(
                (
                    float(record["highest_price"])
                    / initial_price
                    - 1
                )
                * 100,
                2,
            )
            record["lowest_change_pct"] = round(
                (
                    float(record["lowest_price"])
                    / initial_price
                    - 1
                )
                * 100,
                2,
            )

        record["last_price_check"] = snapshot["checked_at"]
        record["price_source"] = snapshot["source"]
        record["price_error"] = None
        record["updates"] = int(record.get("updates", 0)) + 1
        record["development_comment"] = outcome_comment(record)
        updated_records += 1

    save_json(config.SIGNALS_FILE, records[-10000:])

    return {
        "updated_records": updated_records,
        "updated_tickers": len(snapshots),
        "errors": errors,
    }


def article_message(article: dict[str, Any]) -> str:
    ai = article.get("ai") or {}
    symbols = " • ".join(article.get("tickers") or ["—"])
    url = article.get("url") or ""
    link = (
        f'\n<a href="{escape(url)}">فتح الخبر</a>'
        if url
        else ""
    )

    tracking = article.get("tracking") or {}
    price_line = ""
    if tracking.get("price_at_signal") is not None:
        price_line = (
            "\n<b>سعر الرصد:</b> "
            f"${float(tracking['price_at_signal']):.4f}"
        )

    return (
        "<b>⚡ برق نيوز</b>\n"
        f"<b>{escape(symbols)}</b>\n"
        f"<b>وقت الخبر:</b> "
        f"{format_saudi_time(article.get('published'))}\n"
        f"<b>تقييم النظام:</b> "
        f"{article.get('system_score', 0)}\n"
        f"<b>رأي النظام:</b> "
        f"{escape(str(article.get('system_reason') or 'لا توجد إشارة واضحة'))}\n"
        f"<b>تقييم AI:</b> {ai.get('score', '—')}\n"
        f"<b>رأي AI:</b> "
        f"{escape(str(ai.get('summary') or 'لم يتم تشغيل AI'))}\n"
        f"<b>سبب AI:</b> "
        f"{escape(str(ai.get('reason') or 'لا يوجد سبب متاح'))}\n"
        f"<b>سكويز:</b> {ai.get('squeeze_score', '—')}\n"
        f"<b>خطر التخفيف:</b> "
        f"{ai.get('dilution_risk', '—')}"
        f"{price_line}\n"
        f"<b>{escape(str(article.get('title', '')))}</b>"
        f"{link}"
    )


def is_positive(article: dict[str, Any]) -> bool:
    ai = article.get("ai") or {}
    sentiment = ai.get("sentiment")

    if sentiment in ("negative", "mixed"):
        return False

    if sentiment == "positive":
        return int(ai.get("score", 0)) >= config.AI_POSITIVE_MIN

    return (
        int(article.get("system_score", 0))
        >= config.SYSTEM_POSITIVE_MIN
    )


def process_articles(
    raw_items: list[dict[str, Any]],
    hours: float | None,
    ai_enabled: bool,
    watchlist_only: bool = True,
) -> list[dict[str, Any]]:
    watchlist = load_symbols()
    account = load_account()
    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(hours=float(hours))
        if hours is not None
        else None
    )
    output: list[dict[str, Any]] = []

    for raw in raw_items:
        article = normalize_article(raw)

        if watchlist_only:
            matched = sorted(
                set(article["tickers"])
                & watchlist
            )
            if not matched:
                continue
            article["tickers"] = matched

        published = parse_time(article["published"])
        if cutoff and (
            not published
            or published < cutoff
        ):
            continue

        if ai_enabled and ai_should_run(
            article,
            str(account.get("ai_mode", "economic")),
        ):
            try:
                article["ai"] = ai_analyze(article)
            except Exception as exc:
                article["ai_error"] = str(exc)
                article["ai"] = {
                    "score": 0,
                    "sentiment": "error",
                    "summary": "تعذر تحليل AI",
                    "reason": str(exc),
                    "squeeze_score": 0,
                    "dilution_risk": 0,
                    "cost_usd": 0.0,
                }

        output.append(article)

    output.sort(
        key=lambda item: item.get("published", ""),
        reverse=True,
    )
    return output


def analyze_symbol_news(
    symbol: str,
    hours: float = 168,
    ai_enabled: bool = True,
) -> dict[str, Any]:
    symbol = str(symbol or "").strip().upper().replace("$", "")
    if not symbol:
        raise ValueError("أدخل رمز سهم صحيح.")

    # الاستعلام المباشر بالرمز يعطي نتائج أكثر دقة من جلب السوق كاملًا.
    raw_items = fetch_news(
        hours=hours,
        limit=config.NEWS_LIMIT,
        ticker=symbol,
    )

    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=float(hours)
    )
    articles: list[dict[str, Any]] = []

    for raw in raw_items:
        article = normalize_article(raw)
        if symbol not in set(article.get("tickers") or []):
            continue

        published = parse_time(article.get("published"))
        if published and published < cutoff:
            continue

        articles.append(article)

    articles.sort(
        key=lambda item: item.get("published", ""),
        reverse=True,
    )

    ai_limit = min(
        len(articles),
        config.SYMBOL_AI_MAX_ARTICLES,
    )

    if ai_enabled:
        for article in articles[:ai_limit]:
            try:
                article["ai"] = ai_analyze(article)
            except Exception as exc:
                article["ai_error"] = str(exc)
                article["ai"] = {
                    "score": 0,
                    "sentiment": "error",
                    "summary": "تعذر تحليل AI",
                    "reason": str(exc),
                    "squeeze_score": 0,
                    "dilution_risk": 0,
                    "cost_usd": 0.0,
                }

    system_scores = [
        int(article.get("system_score", 0))
        for article in articles
    ]
    ai_scores = [
        int((article.get("ai") or {}).get("score", 0))
        for article in articles
        if isinstance(
            (article.get("ai") or {}).get("score"),
            int,
        )
    ]

    overall_ai = None

    if (
        ai_enabled
        and articles
        and config.OPENAI_API_KEY
    ):
        compact = []
        for article in articles[:20]:
            ai = article.get("ai") or {}
            compact.append(
                {
                    "time": format_saudi_time(
                        article.get("published")
                    ),
                    "title": article.get("title"),
                    "system_score": article.get("system_score"),
                    "system_opinion": article.get("system_reason"),
                    "ai_score": ai.get("score"),
                    "ai_opinion": ai.get("summary"),
                    "ai_reason": ai.get("reason"),
                }
            )

        prompt = f"""
حلل مجمل أخبار السهم {symbol} خلال آخر {hours} ساعة.
وازن بين الأخبار الإيجابية والسلبية والتخفيف والسيولة والسكويز.
أعد JSON فقط:
{{
  "overall_score": عدد من -100 إلى 100,
  "sentiment": "positive أو negative أو neutral أو mixed",
  "summary": "خلاصة عربية قصيرة",
  "key_positive": "أهم عامل إيجابي",
  "key_risk": "أهم خطر",
  "verdict": "رأي نهائي مختصر وليس توصية مالية"
}}

الأخبار:
{json.dumps(compact, ensure_ascii=False)}
"""

        response = requests.post(
            config.OPENAI_URL,
            headers={
                "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.OPENAI_MODEL,
                "input": prompt,
                "temperature": 0.1,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        overall_ai = parse_json_object(
            extract_response_text(data)
        )
        record_usage(
            data,
            f"symbol_summary:{symbol}",
        )

    price_snapshot = None
    try:
        price_snapshot = fetch_price_snapshot(symbol)
    except Exception:
        price_snapshot = None

    price_map = {
        symbol: price_snapshot
    }

    saved_signals = 0
    for article in articles:
        if should_track_signal(article):
            records = record_signal(
                article,
                price_map=price_map,
            )
            saved_signals += len(records)

    return {
        "symbol": symbol,
        "hours": hours,
        "raw_count": len(raw_items),
        "count": len(articles),
        "ai_analyzed_count": ai_limit if ai_enabled else 0,
        "saved_signals": saved_signals,
        "articles": articles,
        "system_average": (
            round(
                sum(system_scores)
                / len(system_scores),
                1,
            )
            if system_scores
            else 0
        ),
        "ai_average": (
            round(
                sum(ai_scores)
                / len(ai_scores),
                1,
            )
            if ai_scores
            else 0
        ),
        "overall_ai": overall_ai,
        "latest_price": (
            price_snapshot.get("price")
            if price_snapshot
            else None
        ),
    }


def usage_totals() -> dict[str, Any]:
    ledger = load_json(config.USAGE_FILE, [])
    today = datetime.now(RIYADH).date()
    week_start = today - timedelta(
        days=today.weekday()
    )

    total_cost = 0.0
    today_cost = 0.0
    week_cost = 0.0

    for row in ledger:
        cost = float(row.get("cost_usd", 0))
        total_cost += cost

        try:
            date_value = (
                datetime.fromisoformat(row["time"])
                .astimezone(RIYADH)
                .date()
            )
        except Exception:
            continue

        if date_value == today:
            today_cost += cost

        if date_value >= week_start:
            week_cost += cost

    account = load_account()
    starting_balance = float(
        account.get("starting_balance_usd", 0)
    )

    return {
        "total_cost": round(total_cost, 4),
        "today_cost": round(today_cost, 4),
        "week_cost": round(week_cost, 4),
        "starting_balance": starting_balance,
        "estimated_remaining": round(
            max(0, starting_balance - total_cost),
            4,
        ),
    }


def daily_openai_status() -> dict[str, Any]:
    totals = usage_totals()
    status = {
        "connected": False,
        "message": "مفتاح OpenAI غير مضاف.",
        **totals,
    }

    if not config.OPENAI_API_KEY:
        return status

    try:
        response = requests.post(
            config.OPENAI_URL,
            headers={
                "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.OPENAI_MODEL,
                "input": "Reply with OK only.",
                "max_output_tokens": 5,
            },
            timeout=30,
        )

        if response.ok:
            status["connected"] = True
            status["message"] = (
                "OpenAI يعمل والحساب يسمح بطلب جديد."
            )
        elif response.status_code == 429:
            status["message"] = (
                "OpenAI أعاد 429: الرصيد غير كافٍ "
                "أو حد الاستخدام متجاوز."
            )
        else:
            status["message"] = (
                f"OpenAI: HTTP {response.status_code}"
            )

    except Exception as exc:
        status["message"] = (
            f"تعذر فحص OpenAI: {exc}"
        )

    return status
