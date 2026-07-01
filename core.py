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



UNCERTAIN_EVENT_TERMS = [
    "proposed",
    "proposal",
    "non-binding",
    "nonbinding",
    "unsolicited",
    "considering",
    "exploring",
    "potential",
    "possible",
    "in talks",
    "reportedly",
    "rumor",
    "rumoured",
    "may acquire",
    "seeking to acquire",
]

ACQUISITION_TERMS = [
    "acquisition",
    "acquire",
    "acquired",
    "takeover",
    "merger",
    "buyout",
    "purchase offer",
]


def confidence_label(score: int) -> str:
    if score >= 80:
        return "عالية"
    if score >= 55:
        return "متوسطة"
    return "منخفضة"


def classify_acquisition_event(text: str) -> dict[str, Any] | None:
    combined = str(text or "").lower()

    if not any(term in combined for term in ACQUISITION_TERMS):
        return None

    cancelled_terms = [
        "withdraws offer",
        "withdrawn offer",
        "terminates merger",
        "terminated merger",
        "deal terminated",
        "rejects offer",
        "rejected offer",
        "rejects acquisition",
        "rejected acquisition",
        "rejects takeover",
        "rejected takeover",
        "rejects proposed",
        "declines offer",
        "abandons acquisition",
        "acquisition cancelled",
        "acquisition canceled",
    ]
    completed_terms = [
        "completes acquisition",
        "completed acquisition",
        "closes acquisition",
        "closed acquisition",
        "completion of acquisition",
        "merger completed",
        "transaction completed",
        "deal closed",
        "consummated",
    ]
    definitive_terms = [
        "definitive agreement",
        "entered into an agreement",
        "agreed to acquire",
        "agreement to acquire",
        "signed merger agreement",
        "binding agreement",
    ]
    approved_terms = [
        "board approves",
        "board approved",
        "shareholders approve",
        "shareholder approval",
        "accepts offer",
        "accepted offer",
        "recommends the offer",
    ]
    review_terms = [
        "board confirms proposed",
        "board receives proposal",
        "reviewing the proposal",
        "evaluating the proposal",
        "considering the proposal",
        "special committee",
        "strategic alternatives",
    ]

    if any(term in combined for term in cancelled_terms):
        return {
            "score": -72,
            "sentiment": "negative",
            "reason": "إلغاء أو رفض صفقة استحواذ",
            "event_status": "ملغى أو مرفوض",
            "confidence_score": 92,
            "alert_level": "سلبي مؤكد",
        }

    if any(term in combined for term in completed_terms):
        return {
            "score": 96,
            "sentiment": "positive",
            "reason": "إتمام صفقة الاستحواذ",
            "event_status": "مكتمل",
            "confidence_score": 96,
            "alert_level": "مؤكد",
        }

    if any(term in combined for term in definitive_terms):
        return {
            "score": 90,
            "sentiment": "positive",
            "reason": "اتفاق استحواذ نهائي وموقّع",
            "event_status": "اتفاق نهائي",
            "confidence_score": 92,
            "alert_level": "مؤكد",
        }

    if any(term in combined for term in approved_terms):
        return {
            "score": 82,
            "sentiment": "positive",
            "reason": "موافقة رسمية على عرض أو صفقة استحواذ",
            "event_status": "موافق عليه",
            "confidence_score": 86,
            "alert_level": "قوي",
        }

    if any(term in combined for term in review_terms):
        return {
            "score": 55,
            "sentiment": "positive",
            "reason": "عرض استحواذ قيد المراجعة ولم يصبح اتفاقًا نهائيًا",
            "event_status": "قيد المراجعة",
            "confidence_score": 58,
            "alert_level": "مبدئي",
        }

    if any(term in combined for term in UNCERTAIN_EVENT_TERMS):
        return {
            "score": 48,
            "sentiment": "positive",
            "reason": "عرض أو احتمال استحواذ غير نهائي",
            "event_status": "مقترح غير نهائي",
            "confidence_score": 48,
            "alert_level": "مبدئي",
        }

    return {
        "score": 68,
        "sentiment": "positive",
        "reason": "خبر استحواذ دون دليل كافٍ على الإتمام النهائي",
        "event_status": "استحواذ معلن",
        "confidence_score": 65,
        "alert_level": "متوسط",
    }


def default_event_metadata(
    score: int,
    sentiment: str,
    combined: str,
) -> dict[str, Any]:
    uncertain = any(term in combined for term in UNCERTAIN_EVENT_TERMS)
    absolute_score = abs(int(score))

    if uncertain:
        confidence_score = min(50, max(30, absolute_score))
        event_status = "مبدئي أو غير مؤكد"
        alert_level = "مبدئي"
    elif absolute_score >= 80:
        confidence_score = 84
        event_status = "خبر واضح"
        alert_level = "قوي"
    elif absolute_score >= 55:
        confidence_score = 68
        event_status = "خبر متوسط الوضوح"
        alert_level = "متوسط"
    elif absolute_score > 0:
        confidence_score = 50
        event_status = "خبر يحتاج تحقق"
        alert_level = "مبدئي"
    else:
        confidence_score = 25
        event_status = "غير مصنف"
        alert_level = "منخفض"

    return {
        "event_status": event_status,
        "confidence_score": confidence_score,
        "confidence_label": confidence_label(confidence_score),
        "alert_level": alert_level,
    }


def ai_unavailable_result(
    reason: str,
    error_code: str = "unavailable",
) -> dict[str, Any]:
    return {
        "available": False,
        "score": None,
        "sentiment": "error",
        "summary": "تحليل AI غير متاح",
        "reason": str(reason or "تعذر تشغيل تحليل AI"),
        "squeeze_score": None,
        "dilution_risk": None,
        "cost_usd": 0.0,
        "error_code": error_code,
    }


def ai_error_from_response(response: requests.Response) -> dict[str, Any]:
    detail = ""

    try:
        error = response.json().get("error", {})
        detail = str(error.get("message") or "")
        api_code = str(error.get("code") or error.get("type") or "")
    except Exception:
        detail = response.text[:300]
        api_code = ""

    if response.status_code == 401:
        return ai_unavailable_result(
            "مفتاح OpenAI غير صالح أو غير مصرح له. "
            "تحقق من Streamlit Secrets ثم أعد تشغيل التطبيق.",
            "unauthorized",
        )

    if response.status_code == 429:
        return ai_unavailable_result(
            "الرصيد غير كافٍ أو تم تجاوز حد استخدام OpenAI."
            + (f" ({detail})" if detail else ""),
            api_code or "rate_or_quota",
        )

    return ai_unavailable_result(
        f"تعذر اتصال OpenAI: HTTP {response.status_code}"
        + (f" — {detail}" if detail else ""),
        api_code or f"http_{response.status_code}",
    )



def system_analyze(title: str, teaser: str) -> dict[str, Any]:
    combined = f"{title} {teaser}".lower()

    acquisition = classify_acquisition_event(combined)
    if acquisition:
        acquisition["confidence_label"] = confidence_label(
            int(acquisition["confidence_score"])
        )
        return acquisition

    if any(pattern in combined for pattern in NOISE_PATTERNS):
        metadata = default_event_metadata(0, "neutral", combined)
        return {
            "score": 0,
            "sentiment": "neutral",
            "reason": "خبر تجميعي أو منخفض الأهمية",
            **metadata,
        }

    matches = []
    for phrase, score, reason in POSITIVE_RULES + NEGATIVE_RULES:
        if phrase in combined:
            matches.append((score, reason))

    if not matches:
        metadata = default_event_metadata(0, "neutral", combined)
        return {
            "score": 0,
            "sentiment": "neutral",
            "reason": "لا توجد إشارة آلية قوية",
            **metadata,
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

    # الكلمات غير المؤكدة تمنع رفع الخبر كفرصة قوية.
    if any(term in combined for term in UNCERTAIN_EVENT_TERMS):
        if strongest_score > 55:
            strongest_score = 55
        elif strongest_score < -55:
            strongest_score = -55

    sentiment = (
        "positive"
        if strongest_score > 0
        else "negative"
        if strongest_score < 0
        else "neutral"
    )
    metadata = default_event_metadata(
        strongest_score,
        sentiment,
        combined,
    )

    return {
        "score": strongest_score,
        "sentiment": sentiment,
        "reason": "، ".join(reasons[:3]),
        **metadata,
    }



SYSTEM_OPINION_EMPTY_VALUES = {
    "",
    "—",
    "-",
    "غير متاح",
    "غير متوفر",
    "لا يوجد",
    "none",
    "null",
}


def ensure_system_analysis(
    article: dict[str, Any],
) -> dict[str, Any]:
    """يعيد بناء تحليل النظام لأي خبر قديم أو ناقص البيانات."""
    current_reason = str(
        article.get("system_reason")
        or article.get("system_opinion")
        or ""
    ).strip()

    reason_is_missing = (
        current_reason.lower()
        in SYSTEM_OPINION_EMPTY_VALUES
    )

    required_missing = any(
        key not in article
        for key in (
            "system_score",
            "system_sentiment",
            "event_status",
            "confidence_score",
            "confidence_label",
            "alert_level",
        )
    )

    if not reason_is_missing and not required_missing:
        return article

    analysis = system_analyze(
        clean_text(article.get("title")),
        clean_text(
            article.get("teaser")
            or article.get("body")
            or article.get("description")
        ),
    )

    article["system_score"] = int(
        analysis.get("score", article.get("system_score", 0))
    )
    article["system_sentiment"] = analysis.get(
        "sentiment",
        article.get("system_sentiment", "neutral"),
    )
    article["system_reason"] = analysis.get(
        "reason",
        "لا توجد إشارة آلية قوية",
    )
    article["event_status"] = analysis.get(
        "event_status",
        article.get("event_status", "غير مصنف"),
    )
    article["confidence_score"] = int(
        analysis.get(
            "confidence_score",
            article.get("confidence_score", 0),
        )
    )
    article["confidence_label"] = analysis.get(
        "confidence_label",
        article.get("confidence_label", "منخفضة"),
    )
    article["alert_level"] = analysis.get(
        "alert_level",
        article.get("alert_level", "منخفض"),
    )

    return article


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

    article = {
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
        "event_status": analysis.get("event_status", "غير مصنف"),
        "confidence_score": int(analysis.get("confidence_score", 0)),
        "confidence_label": analysis.get("confidence_label", "منخفضة"),
        "alert_level": analysis.get("alert_level", "منخفض"),
    }

    return ensure_system_analysis(article)


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
        return ai_unavailable_result(
            "مفتاح OpenAI غير مضاف في Streamlit Secrets أو البيئة.",
            "missing_key",
        )

    prompt = f"""
حلل خبر سهم أمريكي بشكل صارم. لا تعتبر العنوان إيجابيًا تلقائيًا.
افحص: مرحلة الحدث، قوة المحفز، الطرح والتخفيف، الضمانات،
خطر الشطب، التجزئة العكسية، احتمال أن يكون الخبر مسعرًا،
وقابلية السكويز.

أعد JSON فقط:
{{
  "score": عدد صحيح من -100 إلى 100,
  "sentiment": "positive أو negative أو neutral أو mixed",
  "arabic_title": "عنوان عربي مختصر للخبر لا يتجاوز 12 كلمة",
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
حالة الحدث: {article.get("event_status")}
ثقة النظام: {article.get("confidence_score")}
نوع التنبيه: {article.get("alert_level")}
"""

    try:
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
    except Exception as exc:
        return ai_unavailable_result(
            f"تعذر الاتصال بـ OpenAI: {exc}",
            "connection_error",
        )

    if not response.ok:
        return ai_error_from_response(response)

    try:
        data = response.json()
        result = parse_json_object(extract_response_text(data))

        result["available"] = True
        result["arabic_title"] = clean_text(
            result.get("arabic_title")
        )[:140]
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

    except Exception as exc:
        return ai_unavailable_result(
            f"وصل رد من OpenAI لكن تعذر فهمه: {exc}",
            "invalid_response",
        )


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
    article = ensure_system_analysis(dict(article))

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
            "event_status": article.get("event_status"),
            "confidence_score": article.get("confidence_score"),
            "confidence_label": article.get("confidence_label"),
            "alert_level": article.get("alert_level"),
            "ai_available": bool(ai.get("available")),
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
    article = enrich_article_for_display(article)
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

    ai_score = ai.get("score")
    ai_failed = (
        ai.get("available") is False
        or ai.get("sentiment") == "error"
        or str(ai.get("summary") or "").startswith(
            "تعذر تحليل AI"
        )
    )
    ai_score_text = (
        "غير متاح"
        if ai_failed or ai_score is None
        else str(ai_score)
    )

    return (
        "<b>⚡ برق نيوز</b>\n"
        f"<b>{escape(symbols)}</b>\n"
        f"<b>وقت الخبر:</b> "
        f"{format_saudi_time(article.get('published'))}\n"
        f"<b>العنوان:</b> "
        f"{escape(str(article.get('arabic_title')))}\n"
        f"<b>الدرجة:</b> "
        f"{article.get('final_score', 0)}\n"
        f"<b>التوصية:</b> "
        f"{escape(str(article.get('recommendation')))}\n"
        f"<b>حالة الحدث:</b> "
        f"{escape(str(article.get('event_status') or 'غير مصنف'))}\n"
        f"<b>رأي النظام:</b> "
        f"{escape(str(article.get('system_reason') or 'لا توجد إشارة واضحة'))}\n"
        f"<b>تقييم AI:</b> {ai_score_text}\n"
        f"<b>رأي AI:</b> "
        f"{escape(str(ai.get('summary') or 'لم يتم تشغيل AI'))}"
        f"{price_line}"
        f"{link}"
    )


def is_positive(article: dict[str, Any]) -> bool:
    ai = article.get("ai") or {}
    ai_available = bool(ai.get("available"))
    ai_sentiment = ai.get("sentiment")
    ai_score = ai.get("score")
    system_score = int(article.get("system_score", 0))
    alert_level = str(article.get("alert_level") or "")
    confidence_score = int(article.get("confidence_score", 0))

    if ai_available and ai_sentiment in ("negative", "mixed"):
        return False

    # الأخبار المقترحة ترسل كتحديث مبدئي، ولا تُعامل كفرصة قوية.
    if alert_level == "مبدئي":
        if ai_available:
            return (
                ai_sentiment == "positive"
                and isinstance(ai_score, int)
                and ai_score >= 55
            )
        return system_score >= 45 and confidence_score >= 40

    if ai_available and ai_sentiment == "positive":
        return (
            isinstance(ai_score, int)
            and ai_score >= config.AI_POSITIVE_MIN
        )

    return system_score >= config.SYSTEM_POSITIVE_MIN


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
        article = ensure_system_analysis(normalize_article(raw))

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
                article["ai"] = ai_unavailable_result(
                    str(exc),
                    "internal_error",
                )

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
        article = ensure_system_analysis(normalize_article(raw))
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
                article["ai"] = ai_unavailable_result(
                    str(exc),
                    "internal_error",
                )

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

    available_ai_articles = [
        article
        for article in articles
        if bool((article.get("ai") or {}).get("available"))
    ]

    if (
        ai_enabled
        and available_ai_articles
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

        try:
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

            if response.ok:
                data = response.json()
                overall_ai = parse_json_object(
                    extract_response_text(data)
                )
                record_usage(
                    data,
                    f"symbol_summary:{symbol}",
                )
            else:
                overall_ai = {
                    "available": False,
                    "summary": "الخلاصة النهائية غير متاحة",
                    "reason": ai_error_from_response(response).get("reason"),
                }

        except Exception as exc:
            overall_ai = {
                "available": False,
                "summary": "الخلاصة النهائية غير متاحة",
                "reason": str(exc),
            }

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
        else:
            error_result = ai_error_from_response(response)
            status["message"] = str(
                error_result.get("reason")
                or f"OpenAI: HTTP {response.status_code}"
            )

    except Exception as exc:
        status["message"] = (
            f"تعذر فحص OpenAI: {exc}"
        )

    return status


# ============================================================
# v15 — العرض المبسط، المفضلة، الإحصائيات، والتطوير التراكمي
# ============================================================

RECOMMENDATION_STRONG_BUY = "شراء قوي"
RECOMMENDATION_BUY = "شراء"
RECOMMENDATION_WATCH = "مراقبة"
RECOMMENDATION_NEGATIVE = "سلبي"


def effective_score(article: dict[str, Any]) -> int:
    ai = article.get("ai") or {}
    ai_score = ai.get("score")

    if (
        ai.get("available") is True
        and isinstance(ai_score, (int, float))
    ):
        return int(round(float(ai_score)))

    try:
        return int(article.get("system_score", 0))
    except Exception:
        return 0


def recommendation_from_score(score: int | float) -> str:
    value = float(score)

    if value > 90:
        return RECOMMENDATION_STRONG_BUY
    if value > 65:
        return RECOMMENDATION_BUY
    if value < 0:
        return RECOMMENDATION_NEGATIVE
    return RECOMMENDATION_WATCH


def article_recommendation(article: dict[str, Any]) -> str:
    return recommendation_from_score(effective_score(article))


def concise_arabic_title(article: dict[str, Any]) -> str:
    ai = article.get("ai") or {}
    ai_title = clean_text(ai.get("arabic_title"))

    if ai_title:
        return ai_title[:140]

    original = clean_text(article.get("title"))
    if re.search(r"[\u0600-\u06FF]", original):
        return original[:140]

    reason = clean_text(
        article.get("system_reason")
        or article.get("system_opinion")
    )
    symbol = " / ".join(article.get("tickers") or [])

    title_map = {
        "اعتماد FDA": "هيئة الغذاء والدواء تعتمد منتجًا جديدًا",
        "تصريح FDA": "الشركة تحصل على تصريح من هيئة الغذاء والدواء",
        "تصريح 510(k)": "الشركة تحصل على تصريح طبي 510(k)",
        "عقد جديد": "الشركة تحصل على عقد جديد",
        "أمر شراء": "الشركة تعلن أمر شراء جديد",
        "طلبية جديدة": "الشركة تستقبل طلبية جديدة",
        "شراكة استراتيجية": "الشركة تعلن شراكة استراتيجية",
        "شراكة": "الشركة تعلن اتفاق شراكة",
        "مرحلة ثالثة": "تطور جديد في المرحلة الثالثة للتجربة",
        "نتائج إيجابية": "الشركة تعلن نتائج إيجابية",
        "حقق الهدف الرئيسي": "التجربة تحقق هدفها الرئيسي",
        "تفوق على التوقعات": "النتائج تتفوق على التوقعات",
        "رفع التوقعات": "الشركة ترفع توقعاتها المستقبلية",
        "إعادة شراء أسهم": "الشركة تعلن إعادة شراء الأسهم",
        "منحة": "الشركة تحصل على منحة جديدة",
        "براءة اختراع": "الشركة تحصل على براءة اختراع",
        "إطلاق تجاري": "الشركة تبدأ إطلاقًا تجاريًا جديدًا",
        "إطلاق": "الشركة تطلق منتجًا جديدًا",
        "توسع": "الشركة تعلن خطة توسع",
        "طرح أسهم": "الشركة تعلن طرح أسهم",
        "طرح مباشر": "الشركة تعلن طرحًا مباشرًا",
        "خطر شطب": "الشركة تواجه خطر الشطب",
        "عدم امتثال": "إشعار بعدم الامتثال لمتطلبات الإدراج",
        "إفلاس": "الشركة تعلن إجراءات إفلاس",
        "فشل تجربة": "التجربة السريرية لا تحقق النتائج المطلوبة",
        "تعليق سريري": "تعليق التجربة السريرية",
        "تجزئة عكسية": "الشركة تعلن تجزئة عكسية",
        "خفض التوقعات": "الشركة تخفض توقعاتها المستقبلية",
        "دون التوقعات": "النتائج تأتي دون التوقعات",
    }

    for key, title in title_map.items():
        if key in reason:
            return f"{title} — {symbol}" if symbol else title

    event_status = clean_text(article.get("event_status"))
    if "استحواذ" in reason or event_status in {
        "قيد المراجعة",
        "مقترح غير نهائي",
        "موافق عليه",
        "اتفاق نهائي",
        "مكتمل",
        "ملغى أو مرفوض",
    }:
        event_titles = {
            "قيد المراجعة": "عرض استحواذ قيد المراجعة",
            "مقترح غير نهائي": "عرض استحواذ مقترح وغير نهائي",
            "موافق عليه": "موافقة رسمية على صفقة الاستحواذ",
            "اتفاق نهائي": "توقيع اتفاق استحواذ نهائي",
            "مكتمل": "اكتمال صفقة الاستحواذ",
            "ملغى أو مرفوض": "رفض أو إلغاء عرض الاستحواذ",
        }
        title = event_titles.get(
            event_status,
            "تطور جديد في صفقة استحواذ",
        )
        return f"{title} — {symbol}" if symbol else title

    if reason and reason != "لا توجد إشارة آلية قوية":
        return f"{reason} — {symbol}" if symbol else reason

    return (
        f"تحديث جديد عن سهم {symbol}"
        if symbol
        else original[:100] or "خبر جديد"
    )


def enrich_article_for_display(
    article: dict[str, Any],
) -> dict[str, Any]:
    output = ensure_system_analysis(dict(article))
    output["final_score"] = effective_score(output)
    output["recommendation"] = article_recommendation(output)
    output["arabic_title"] = concise_arabic_title(output)
    return output


def _favorite_id(article: dict[str, Any]) -> str:
    return str(
        article.get("id")
        or article.get("article_id")
        or (
            clean_text(article.get("published"))
            + ":"
            + clean_text(article.get("title"))
        )
    )


def load_favorites() -> list[dict[str, Any]]:
    favorites = load_json(config.FAVORITES_FILE, [])
    return favorites if isinstance(favorites, list) else []


def is_favorite(article_id: str) -> bool:
    target = str(article_id)
    return any(
        str(item.get("article_id")) == target
        for item in load_favorites()
    )


def add_favorite(article: dict[str, Any]) -> dict[str, Any]:
    favorites = load_favorites()
    article = enrich_article_for_display(article)
    article_id = _favorite_id(article)

    for item in favorites:
        if str(item.get("article_id")) == article_id:
            return item

    signal_map = record_signals_batch([article])
    signal_records = signal_map.get(article_id) or []

    item = {
        "article_id": article_id,
        "saved_at": datetime.now(RIYADH).isoformat(),
        "reviewed": False,
        "article": article,
        "signal_ids": [
            record.get("signal_id")
            for record in signal_records
            if record.get("signal_id")
        ],
    }
    favorites.append(item)
    save_json(config.FAVORITES_FILE, favorites[-5000:])
    return item


def remove_favorite(article_id: str) -> bool:
    target = str(article_id)
    favorites = load_favorites()
    filtered = [
        item
        for item in favorites
        if str(item.get("article_id")) != target
    ]
    changed = len(filtered) != len(favorites)

    if changed:
        save_json(config.FAVORITES_FILE, filtered)

    return changed


def set_favorite_reviewed(
    article_id: str,
    reviewed: bool,
) -> bool:
    favorites = load_favorites()
    changed = False

    for item in favorites:
        if str(item.get("article_id")) == str(article_id):
            item["reviewed"] = bool(reviewed)
            item["reviewed_at"] = (
                datetime.now(RIYADH).isoformat()
                if reviewed
                else None
            )
            changed = True
            break

    if changed:
        save_json(config.FAVORITES_FILE, favorites)

    return changed


def favorite_rows() -> list[dict[str, Any]]:
    favorites = load_favorites()
    signals = load_json(config.SIGNALS_FILE, [])
    signal_by_id = {
        str(record.get("signal_id")): record
        for record in signals
    }
    rows: list[dict[str, Any]] = []

    for favorite in favorites:
        article = enrich_article_for_display(
            favorite.get("article") or {}
        )
        linked = [
            signal_by_id[signal_id]
            for signal_id in favorite.get("signal_ids") or []
            if signal_id in signal_by_id
        ]

        if not linked:
            article_id = str(favorite.get("article_id"))
            linked = [
                record
                for record in signals
                if str(record.get("article_id")) == article_id
            ]

        first_signal = linked[0] if linked else {}
        lowest_values = [
            float(record["lowest_price"])
            for record in linked
            if record.get("lowest_price") is not None
        ]
        highest_values = [
            float(record["highest_price"])
            for record in linked
            if record.get("highest_price") is not None
        ]

        rows.append(
            {
                "article_id": favorite.get("article_id"),
                "reviewed": bool(favorite.get("reviewed")),
                "saved_at": favorite.get("saved_at"),
                "detected_at": (
                    first_signal.get("detected_at")
                    or favorite.get("saved_at")
                ),
                "symbol": " / ".join(
                    article.get("tickers") or []
                ),
                "title": article.get("arabic_title"),
                "score": article.get("final_score", 0),
                "recommendation": article.get("recommendation"),
                "url": article.get("url"),
                "price_at_signal": first_signal.get(
                    "price_at_signal"
                ),
                "lowest_price": (
                    min(lowest_values)
                    if lowest_values
                    else first_signal.get("lowest_price")
                ),
                "highest_price": (
                    max(highest_values)
                    if highest_values
                    else first_signal.get("highest_price")
                ),
                "latest_price": first_signal.get("latest_price"),
                "last_change_pct": first_signal.get(
                    "last_change_pct"
                ),
            }
        )

    rows.sort(
        key=lambda item: item.get("saved_at") or "",
        reverse=True,
    )
    return rows


def signal_recommendation(record: dict[str, Any]) -> str:
    score = record.get("ai_score")
    if not isinstance(score, (int, float)):
        score = record.get("system_score", 0)

    return recommendation_from_score(score or 0)


def signal_result(record: dict[str, Any]) -> str:
    change = record.get("last_change_pct")
    if change is None or int(record.get("updates", 0)) < 1:
        return "قيد المتابعة"

    recommendation = signal_recommendation(record)
    value = float(change)

    if recommendation in (
        RECOMMENDATION_STRONG_BUY,
        RECOMMENDATION_BUY,
    ):
        return "نجح" if value > 0 else "لم ينجح"

    if recommendation == RECOMMENDATION_NEGATIVE:
        return "نجح" if value < 0 else "لم ينجح"

    return "قيد المتابعة"


def signal_mismatch_reason(
    record: dict[str, Any],
) -> str | None:
    result = signal_result(record)
    if result != "لم ينجح":
        return None

    recommendation = signal_recommendation(record)
    change = record.get("last_change_pct")
    score = (
        record.get("ai_score")
        if isinstance(record.get("ai_score"), (int, float))
        else record.get("system_score", 0)
    )
    event_status = clean_text(record.get("event_status"))
    title = clean_text(record.get("title")).lower()

    reasons: list[str] = []

    if event_status in (
        "مقترح غير نهائي",
        "قيد المراجعة",
    ):
        reasons.append("الخبر غير نهائي وقد يكون السوق لم يثق بإتمامه")

    if any(
        term in title
        for term in (
            "offering",
            "warrant",
            "dilution",
            "shelf",
            "atm",
        )
    ):
        reasons.append("احتمال وجود تخفيف أو تمويل عكس أثر الخبر")

    if recommendation in (
        RECOMMENDATION_STRONG_BUY,
        RECOMMENDATION_BUY,
    ) and float(change or 0) <= 0:
        reasons.append("درجة الخبر أعلى من استجابة السعر الفعلية")

    if recommendation == RECOMMENDATION_NEGATIVE and float(change or 0) >= 0:
        reasons.append("السوق تجاهل الأثر السلبي أو كان الخبر مسعرًا مسبقًا")

    if abs(float(score or 0)) >= 90:
        reasons.append("الدرجة القصوى قد تكون مبالغًا فيها دون سياق السيولة والقيمة السوقية")

    return "؛ ".join(reasons) or "حركة السعر لم تطابق اتجاه الخبر"


def calculate_statistics(
    days: int = 30,
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    records = load_json(config.SIGNALS_FILE, [])
    selected: list[dict[str, Any]] = []

    for record in records:
        detected = parse_time(record.get("detected_at"))
        if detected and detected < cutoff:
            continue
        selected.append(record)

    positive = 0
    negative = 0
    neutral = 0
    result_counts = {
        "نجح": 0,
        "لم ينجح": 0,
        "قيد المتابعة": 0,
    }
    recommendation_counts = {
        RECOMMENDATION_STRONG_BUY: 0,
        RECOMMENDATION_BUY: 0,
        RECOMMENDATION_WATCH: 0,
        RECOMMENDATION_NEGATIVE: 0,
    }
    changes_by_recommendation: dict[str, list[float]] = {
        key: []
        for key in recommendation_counts
    }
    mismatch_types: dict[str, int] = {}
    daily: dict[str, dict[str, int]] = {}

    for record in selected:
        score = (
            record.get("ai_score")
            if isinstance(record.get("ai_score"), (int, float))
            else record.get("system_score", 0)
        )
        score = float(score or 0)

        if score > 0:
            positive += 1
        elif score < 0:
            negative += 1
        else:
            neutral += 1

        recommendation = signal_recommendation(record)
        recommendation_counts[recommendation] += 1

        result = signal_result(record)
        result_counts[result] += 1

        change = record.get("last_change_pct")
        if change is not None:
            changes_by_recommendation[recommendation].append(
                float(change)
            )

        mismatch = signal_mismatch_reason(record)
        if mismatch:
            primary = mismatch.split("؛")[0]
            mismatch_types[primary] = (
                mismatch_types.get(primary, 0) + 1
            )

        detected = parse_time(record.get("detected_at"))
        if detected:
            date_key = detected.astimezone(RIYADH).date().isoformat()
            bucket = daily.setdefault(
                date_key,
                {
                    "total": 0,
                    "positive": 0,
                    "negative": 0,
                    "success": 0,
                    "failure": 0,
                },
            )
            bucket["total"] += 1
            if score > 0:
                bucket["positive"] += 1
            elif score < 0:
                bucket["negative"] += 1
            if result == "نجح":
                bucket["success"] += 1
            elif result == "لم ينجح":
                bucket["failure"] += 1

    averages = {
        key: (
            round(sum(values) / len(values), 2)
            if values
            else 0.0
        )
        for key, values in changes_by_recommendation.items()
    }

    decided = result_counts["نجح"] + result_counts["لم ينجح"]
    success_rate = (
        round(result_counts["نجح"] / decided * 100, 1)
        if decided
        else 0.0
    )

    top_errors = sorted(
        (
            {"type": key, "count": value}
            for key, value in mismatch_types.items()
        ),
        key=lambda item: item["count"],
        reverse=True,
    )[:8]

    return {
        "days": days,
        "total": len(selected),
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "recommendations": recommendation_counts,
        "results": result_counts,
        "success_rate": success_rate,
        "average_changes": averages,
        "top_errors": top_errors,
        "daily": daily,
    }


def _review_date(record: dict[str, Any]) -> str:
    return str(record.get("date") or "")


def load_daily_reviews() -> list[dict[str, Any]]:
    reviews = load_json(config.DAILY_REVIEWS_FILE, [])
    return reviews if isinstance(reviews, list) else []


def load_improvements() -> list[dict[str, Any]]:
    items = load_json(config.IMPROVEMENTS_FILE, [])
    return items if isinstance(items, list) else []


def _normalize_issue_code(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9_\-]+", "_", text)
    return text.strip("_")[:80] or "general_improvement"


def _local_daily_review(
    date_key: str,
    stats: dict[str, Any],
    previous: list[dict[str, Any]],
) -> dict[str, Any]:
    registry = {
        str(item.get("code")): item
        for item in previous
    }
    recommendations: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    failure_count = int(
        stats.get("results", {}).get("لم ينجح", 0)
    )
    total = int(stats.get("total", 0))

    if failure_count:
        errors.append(
            {
                "code": "score_price_mismatch",
                "title": "عدم مطابقة تغير السعر مع درجة الخبر",
                "reason": "بعض الدرجات المرتفعة لم تتبعها حركة سعر إيجابية",
                "evidence": f"{failure_count} إشارة لم تنجح من أصل {total}",
                "severity": "عالية" if failure_count >= 5 else "متوسطة",
            }
        )
        code = "score_price_mismatch"
        old = registry.get(code)

        if old and old.get("status") in (
            "exported",
            "implemented",
        ):
            recommendations.append(
                {
                    "code": "score_price_mismatch_followup",
                    "title": "قياس أثر تعديل الدرجات السابق",
                    "action": "قارن نتائج ما قبل التعديل وما بعده، وحدد أنواع الأخبار التي ما زالت تحصل على درجات أعلى من استجابة السعر.",
                    "reason": "المشكلة استمرت بعد العمل على الملاحظة السابقة، لذلك المطلوب الآن قياس الأثر لا تكرار نفس الاقتراح.",
                    "priority": "عالية",
                    "mode": "follow_up",
                    "related_previous_code": code,
                }
            )
        else:
            recommendations.append(
                {
                    "code": code,
                    "title": "إعادة معايرة درجات الأخبار",
                    "action": "خفض الدرجات القصوى للأخبار غير النهائية وإضافة وزن لحجم الشركة والسيولة والتخفيف.",
                    "reason": "الدرجة الحالية لا تفسر حركة السعر دائمًا.",
                    "priority": "عالية",
                    "mode": "new",
                }
            )

    top_errors = stats.get("top_errors") or []
    if top_errors:
        errors.extend(
            {
                "code": f"error_{index}",
                "title": item.get("type"),
                "reason": item.get("type"),
                "evidence": f"تكرر {item.get('count', 0)} مرات",
                "severity": "متوسطة",
            }
            for index, item in enumerate(top_errors[:3], start=1)
        )

    if total and not recommendations:
        recommendations.append(
            {
                "code": "monitor_without_change",
                "title": "الاستمرار في المراقبة دون تعديل جديد",
                "action": "اجمع بيانات أيام إضافية قبل تعديل القواعد حتى لا يتغير النظام بناءً على عينة صغيرة.",
                "reason": "لا يوجد خطأ متكرر قوي يبرر تغييرًا جديدًا اليوم.",
                "priority": "منخفضة",
                "mode": "monitor",
            }
        )

    if not total:
        summary = "لا توجد إشارات سعرية كافية لإنشاء تقييم تطويري موثوق اليوم."
    else:
        summary = (
            f"تمت مراجعة {total} إشارة. "
            f"نسبة النجاح الحالية {stats.get('success_rate', 0)}%. "
            f"ظهر {failure_count} عدم تطابق يحتاج متابعة."
        )

    return {
        "date": date_key,
        "summary": summary,
        "errors": errors,
        "recommendations": recommendations,
        "memory_notes": [],
        "source": "local",
    }


def _openai_daily_review(
    date_key: str,
    stats: dict[str, Any],
    signals: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
    prior_reviews: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not config.OPENAI_API_KEY:
        return None

    compact_signals = []
    for record in signals[-120:]:
        compact_signals.append(
            {
                "symbol": record.get("symbol"),
                "title": record.get("title"),
                "score": (
                    record.get("ai_score")
                    if isinstance(
                        record.get("ai_score"),
                        (int, float),
                    )
                    else record.get("system_score")
                ),
                "recommendation": signal_recommendation(record),
                "event_status": record.get("event_status"),
                "price_at_signal": record.get("price_at_signal"),
                "latest_price": record.get("latest_price"),
                "highest_change_pct": record.get(
                    "highest_change_pct"
                ),
                "lowest_change_pct": record.get(
                    "lowest_change_pct"
                ),
                "last_change_pct": record.get(
                    "last_change_pct"
                ),
                "result": signal_result(record),
                "mismatch": signal_mismatch_reason(record),
            }
        )

    memory = [
        {
            "code": item.get("code"),
            "title": item.get("title"),
            "action": item.get("action"),
            "status": item.get("status"),
            "first_seen": item.get("first_seen"),
            "last_seen": item.get("last_seen"),
            "exported_at": item.get("exported_at"),
            "implemented_at": item.get("implemented_at"),
            "times_seen": item.get("times_seen"),
        }
        for item in improvements[-100:]
    ]
    previous_summaries = [
        {
            "date": review.get("date"),
            "summary": review.get("summary"),
            "status": review.get("status"),
            "recommendation_codes": [
                item.get("code")
                for item in review.get("recommendations") or []
            ],
        }
        for review in prior_reviews[-30:]
    ]

    prompt = f"""
أنت مسؤول تطوير تراكمي لنظام تحليل أخبار الأسهم.
أنشئ تعليق التطوير اليومي بتاريخ {date_key}.

قواعد الذاكرة الإلزامية:
1) لا تتعامل مع كل يوم كأنه أول مرة.
2) لا تكرر اقتراحًا سبق تصديره أو تنفيذه بنفس الصياغة.
3) إذا استمرت المشكلة بعد تنفيذ اقتراح سابق، اذكر أن التعديل السابق لم يحلها بالكامل، ثم اقترح اختبارًا أو خطوة متابعة مختلفة.
4) فرّق بين خطأ في تقييم الخبر وخطأ سببه السوق أو السيولة أو التخفيف أو أن الخبر كان مسعرًا.
5) لا تقترح توسيع الكلمات المفتاحية إذا كانت الذاكرة تقول إن ذلك نُفذ، إلا كمتابعة لقياس الفئات التي ما زالت مفقودة.
6) اعتمد على الأدلة الرقمية، وتجنب التوصيات العامة المتكررة.

أعد JSON فقط:
{{
  "summary": "تعليق يومي واضح من 3 إلى 6 جمل",
  "errors": [
    {{
      "code": "رمز ثابت بالإنجليزية",
      "title": "اسم الخطأ بالعربية",
      "reason": "السبب المحتمل",
      "evidence": "الدليل الرقمي أو الأمثلة",
      "severity": "عالية أو متوسطة أو منخفضة"
    }}
  ],
  "recommendations": [
    {{
      "code": "رمز ثابت بالإنجليزية",
      "title": "عنوان التحسين",
      "action": "إجراء عملي محدد",
      "reason": "لماذا يلزم",
      "priority": "عالية أو متوسطة أو منخفضة",
      "mode": "new أو follow_up أو monitor",
      "related_previous_code": "رمز سابق عند الحاجة"
    }}
  ],
  "memory_notes": [
    "ماذا تم سابقًا وكيف أثر على قرار اليوم"
  ]
}}

الإحصائيات:
{json.dumps(stats, ensure_ascii=False)}

الإشارات:
{json.dumps(compact_signals, ensure_ascii=False)}

ذاكرة التحسينات السابقة:
{json.dumps(memory, ensure_ascii=False)}

ملخصات الأيام السابقة:
{json.dumps(previous_summaries, ensure_ascii=False)}
"""

    try:
        response = requests.post(
            config.OPENAI_URL,
            headers={
                "Authorization": (
                    f"Bearer {config.OPENAI_API_KEY}"
                ),
                "Content-Type": "application/json",
            },
            json={
                "model": config.OPENAI_MODEL,
                "input": prompt,
                "temperature": 0.1,
            },
            timeout=90,
        )

        if not response.ok:
            return None

        data = response.json()
        result = parse_json_object(
            extract_response_text(data)
        )
        if not result:
            return None

        record_usage(
            data,
            f"daily_development:{date_key}",
        )
        result["date"] = date_key
        result["source"] = "openai"
        return result

    except Exception:
        return None



def _apply_cumulative_memory(
    review: dict[str, Any],
    improvements: list[dict[str, Any]],
    date_key: str,
) -> dict[str, Any]:
    """يمنع تكرار الاقتراح كأنه جديد ويحوّله إلى متابعة عند الحاجة."""
    by_code = {
        str(item.get("code")): item
        for item in improvements
    }
    memory_notes = list(review.get("memory_notes") or [])
    cleaned: list[dict[str, Any]] = []

    for recommendation in review.get("recommendations") or []:
        original_code = _normalize_issue_code(
            recommendation.get("code")
            or recommendation.get("title")
        )
        recommendation["code"] = original_code
        existing = by_code.get(original_code)

        if not existing:
            cleaned.append(recommendation)
            continue

        status = str(existing.get("status") or "pending")

        if status == "pending":
            memory_notes.append(
                f"الاقتراح «{existing.get('title')}» موجود مسبقًا وما زال معلقًا؛ لم يُضف كاقتراح جديد."
            )
            continue

        follow_code = f"{original_code}_effect_check"
        follow_existing = by_code.get(follow_code)

        if follow_existing:
            memory_notes.append(
                f"تم العمل سابقًا على «{existing.get('title')}»، ومتابعة أثره مسجلة بالفعل بحالة {follow_existing.get('status')}."
            )
            continue

        previous_action = clean_text(
            existing.get("latest_action")
            or existing.get("action")
        )
        recommendation = dict(recommendation)
        recommendation["code"] = follow_code
        recommendation["mode"] = "follow_up"
        recommendation["related_previous_code"] = original_code
        recommendation["title"] = (
            f"قياس أثر التحسين السابق: "
            f"{existing.get('title') or recommendation.get('title')}"
        )
        recommendation["action"] = (
            "لا تكرر الإجراء السابق. "
            "قارن الأداء قبل التنفيذ وبعده، وحدد سبب استمرار المشكلة، "
            "ثم اختبر تعديلًا مختلفًا قائمًا على النتائج. "
            f"الإجراء السابق كان: {previous_action}"
        )
        recommendation["reason"] = (
            "المشكلة ظهرت مجددًا رغم أن الملاحظة السابقة "
            f"حالتها «{status}»، ولذلك تحولت إلى متابعة أثر."
        )
        cleaned.append(recommendation)
        memory_notes.append(
            f"لم يُكرر الاقتراح {original_code}؛ تم تحويله إلى متابعة أثر مرتبطة به."
        )

    review["recommendations"] = cleaned
    review["memory_notes"] = memory_notes
    return review


def _merge_review_into_registry(
    review: dict[str, Any],
) -> list[dict[str, Any]]:
    registry = load_improvements()
    by_code = {
        str(item.get("code")): item
        for item in registry
    }
    date_key = str(review.get("date"))

    for recommendation in review.get("recommendations") or []:
        code = _normalize_issue_code(
            recommendation.get("code")
            or recommendation.get("title")
        )
        recommendation["code"] = code
        existing = by_code.get(code)

        if existing:
            existing["last_seen"] = date_key
            existing["times_seen"] = int(
                existing.get("times_seen", 1)
            ) + 1
            existing["latest_reason"] = recommendation.get(
                "reason"
            )
            existing["latest_action"] = recommendation.get(
                "action"
            )
            sources = existing.setdefault("source_dates", [])
            if date_key not in sources:
                sources.append(date_key)
            continue

        item = {
            "code": code,
            "title": recommendation.get("title"),
            "action": recommendation.get("action"),
            "reason": recommendation.get("reason"),
            "priority": recommendation.get(
                "priority",
                "متوسطة",
            ),
            "mode": recommendation.get("mode", "new"),
            "related_previous_code": recommendation.get(
                "related_previous_code"
            ),
            "status": "pending",
            "first_seen": date_key,
            "last_seen": date_key,
            "times_seen": 1,
            "source_dates": [date_key],
            "created_at": datetime.now(RIYADH).isoformat(),
        }
        registry.append(item)
        by_code[code] = item

    save_json(config.IMPROVEMENTS_FILE, registry)
    return registry


def generate_daily_development_review(
    force: bool = False,
    date_key: str | None = None,
) -> dict[str, Any]:
    date_key = date_key or datetime.now(RIYADH).date().isoformat()
    reviews = load_daily_reviews()

    for review in reviews:
        if _review_date(review) == date_key and not force:
            return review

    stats = calculate_statistics(days=30)
    signals = load_json(config.SIGNALS_FILE, [])
    improvements = load_improvements()

    generated = _openai_daily_review(
        date_key,
        stats,
        signals,
        improvements,
        reviews,
    )
    if generated is None:
        generated = _local_daily_review(
            date_key,
            stats,
            improvements,
        )

    generated = _apply_cumulative_memory(
        generated,
        improvements,
        date_key,
    )
    generated["date"] = date_key
    generated["created_at"] = datetime.now(RIYADH).isoformat()
    generated["status"] = "pending"
    generated["stats_snapshot"] = stats

    if force:
        reviews = [
            item
            for item in reviews
            if _review_date(item) != date_key
        ]

    reviews.append(generated)
    reviews.sort(
        key=lambda item: item.get("date") or ""
    )
    save_json(config.DAILY_REVIEWS_FILE, reviews[-1000:])
    _merge_review_into_registry(generated)
    return generated


def mark_improvement_status(
    code: str,
    status: str,
    note: str = "",
) -> bool:
    allowed = {
        "pending",
        "exported",
        "implemented",
        "monitoring",
        "closed",
    }
    if status not in allowed:
        raise ValueError("حالة التحسين غير صحيحة.")

    items = load_improvements()
    changed = False

    for item in items:
        if str(item.get("code")) != str(code):
            continue

        item["status"] = status
        item["status_note"] = clean_text(note)
        item["status_updated_at"] = datetime.now(
            RIYADH
        ).isoformat()

        if status == "implemented":
            item["implemented_at"] = item[
                "status_updated_at"
            ]
        if status == "exported":
            item["exported_at"] = item[
                "status_updated_at"
            ]

        changed = True
        break

    if changed:
        save_json(config.IMPROVEMENTS_FILE, items)

    return changed


def development_dashboard() -> dict[str, Any]:
    reviews = load_daily_reviews()
    improvements = load_improvements()
    pending_reviews = [
        item
        for item in reviews
        if item.get("status") == "pending"
    ]
    processed_reviews = [
        item
        for item in reviews
        if item.get("status") in (
            "exported",
            "processed",
        )
    ]
    pending_improvements = [
        item
        for item in improvements
        if item.get("status") == "pending"
    ]

    return {
        "days_recorded": len(reviews),
        "days_processed": len(processed_reviews),
        "days_pending": len(pending_reviews),
        "pending_improvements": len(
            pending_improvements
        ),
        "reviews": sorted(
            reviews,
            key=lambda item: item.get("date") or "",
            reverse=True,
        ),
        "improvements": sorted(
            improvements,
            key=lambda item: item.get(
                "last_seen",
                "",
            ),
            reverse=True,
        ),
    }


def _development_txt(
    reviews: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
    exported_at: str,
) -> str:
    lines = [
        "برق نيوز — سجل التطوير التراكمي بالذكاء الاصطناعي",
        "=" * 64,
        f"وقت التصدير: {format_saudi_time(exported_at)}",
        f"عدد الأيام: {len(reviews)}",
        f"عدد التحسينات في الذاكرة: {len(improvements)}",
        "",
        "ذاكرة التحسينات التراكمية",
        "-" * 64,
    ]

    for item in improvements:
        lines.extend(
            [
                f"الرمز: {item.get('code')}",
                f"العنوان: {item.get('title')}",
                f"الحالة: {item.get('status')}",
                f"الأولوية: {item.get('priority')}",
                f"الإجراء: {item.get('action')}",
                f"السبب: {item.get('reason')}",
                f"أول ظهور: {item.get('first_seen')}",
                f"آخر ظهور: {item.get('last_seen')}",
                f"عدد مرات الرصد: {item.get('times_seen', 1)}",
                f"ملاحظة الحالة: {item.get('status_note', '')}",
                "",
            ]
        )

    lines.extend(
        [
            "",
            "التعليقات اليومية",
            "=" * 64,
        ]
    )

    for review in sorted(
        reviews,
        key=lambda item: item.get("date") or "",
    ):
        lines.extend(
            [
                "",
                f"التاريخ: {review.get('date')}",
                f"الحالة عند التصدير: {review.get('status')}",
                f"المصدر: {review.get('source')}",
                "",
                "التعليق اليومي:",
                clean_text(review.get("summary")),
                "",
                "الأخطاء المرصودة:",
            ]
        )

        errors = review.get("errors") or []
        if not errors:
            lines.append("- لا توجد أخطاء قوية مرصودة.")

        for error in errors:
            lines.extend(
                [
                    f"- [{error.get('severity', '—')}] {error.get('title')}",
                    f"  الرمز: {error.get('code')}",
                    f"  السبب: {error.get('reason')}",
                    f"  الدليل: {error.get('evidence')}",
                ]
            )

        lines.append("")
        lines.append("التحسينات المقترحة:")

        recommendations = review.get(
            "recommendations"
        ) or []
        if not recommendations:
            lines.append("- لا توجد تحسينات جديدة.")

        for rec in recommendations:
            lines.extend(
                [
                    f"- [{rec.get('priority', '—')}] {rec.get('title')}",
                    f"  الرمز: {rec.get('code')}",
                    f"  النوع: {rec.get('mode')}",
                    f"  الإجراء: {rec.get('action')}",
                    f"  السبب: {rec.get('reason')}",
                    (
                        f"  مرتبط بتحسين سابق: "
                        f"{rec.get('related_previous_code')}"
                        if rec.get("related_previous_code")
                        else ""
                    ),
                ]
            )

        memory_notes = review.get("memory_notes") or []
        if memory_notes:
            lines.append("")
            lines.append("ملاحظات الذاكرة:")
            lines.extend(
                f"- {clean_text(note)}"
                for note in memory_notes
            )

        lines.extend(
            [
                "",
                "-" * 64,
            ]
        )

    return "\n".join(
        line
        for line in lines
        if line is not None
    )


def export_pending_development_txt(limit: int | None = None) -> dict[str, Any]:
    reviews = load_daily_reviews()
    pending = sorted(
        [
            item
            for item in reviews
            if item.get("status") == "pending"
        ],
        key=lambda item: item.get("date") or "",
    )

    if limit is not None:
        pending = pending[: max(1, int(limit))]

    if not pending:
        return {
            "text": "",
            "filename": "",
            "count": 0,
            "message": "لا توجد ملاحظات معلقة للتصدير.",
        }

    exported_at = datetime.now(RIYADH).isoformat()
    pending_dates = {
        str(item.get("date"))
        for item in pending
    }
    improvements = load_improvements()

    text = _development_txt(
        pending,
        improvements,
        exported_at,
    )
    filename = (
        "barq_ai_development_"
        f"{datetime.now(RIYADH).strftime('%Y%m%d_%H%M')}.txt"
    )

    for review in reviews:
        if str(review.get("date")) in pending_dates:
            review["status"] = "exported"
            review["exported_at"] = exported_at

    for item in improvements:
        source_dates = {
            str(date)
            for date in item.get("source_dates") or []
        }
        if (
            item.get("status") == "pending"
            and source_dates.intersection(pending_dates)
        ):
            item["status"] = "exported"
            item["exported_at"] = exported_at
            item["status_note"] = (
                "تم تضمين الملاحظة في ملف التطوير النصي."
            )

    history = load_json(
        config.EXPORT_HISTORY_FILE,
        [],
    )
    history.append(
        {
            "exported_at": exported_at,
            "filename": filename,
            "review_dates": sorted(pending_dates),
            "count": len(pending),
        }
    )

    save_json(config.DAILY_REVIEWS_FILE, reviews)
    save_json(config.IMPROVEMENTS_FILE, improvements)
    save_json(
        config.EXPORT_HISTORY_FILE,
        history[-1000:],
    )

    return {
        "text": text,
        "filename": filename,
        "count": len(pending),
        "message": (
            f"تم تجهيز {len(pending)} يومًا "
            "وتحويلها إلى حالة تم العمل على الملاحظات."
        ),
    }


def export_all_development_txt() -> dict[str, Any]:
    reviews = load_daily_reviews()
    improvements = load_improvements()
    exported_at = datetime.now(RIYADH).isoformat()
    text = _development_txt(
        reviews,
        improvements,
        exported_at,
    )
    return {
        "text": text,
        "filename": (
            "barq_ai_development_full_"
            f"{datetime.now(RIYADH).strftime('%Y%m%d_%H%M')}.txt"
        ),
        "count": len(reviews),
        "message": "تم تجهيز السجل التراكمي كاملًا.",
    }
