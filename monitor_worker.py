from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from core import (
    article_message,
    daily_openai_status,
    fetch_news,
    format_saudi_time,
    generate_daily_development_review,
    is_positive,
    load_account,
    load_control,
    load_json,
    process_articles,
    record_signals_batch,
    save_account,
    save_json,
    telegram_send,
    update_signal_outcomes,
)

RIYADH = ZoneInfo("Asia/Riyadh")


def write_status(**values):
    status = load_json(config.STATUS_FILE, {})
    status.update(values)
    status["worker_pid"] = os.getpid()
    status["updated_at"] = datetime.now(RIYADH).isoformat()
    save_json(config.STATUS_FILE, status)


def acquire_lock() -> bool:
    if config.WORKER_LOCK_FILE.exists():
        try:
            old_pid = int(
                config.WORKER_LOCK_FILE.read_text().strip()
            )

            if os.name == "nt":
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {old_pid}"],
                    capture_output=True,
                    text=True,
                )
                if str(old_pid) in result.stdout:
                    return False
            else:
                os.kill(old_pid, 0)
                return False

        except Exception:
            pass

    config.WORKER_LOCK_FILE.write_text(
        str(os.getpid()),
        encoding="utf-8",
    )
    return True


def send_daily_report_if_needed() -> None:
    account = load_account()
    today = datetime.now(RIYADH).date().isoformat()

    if account.get("last_daily_report") == today:
        return

    status = daily_openai_status()
    message = (
        "<b>⚡ تقرير برق نيوز اليومي</b>\n"
        f"<b>حالة OpenAI:</b> {status['message']}\n"
        f"<b>مصروف اليوم:</b> ${status['today_cost']:.4f}\n"
        f"<b>مصروف الأسبوع:</b> ${status['week_cost']:.4f}\n"
        f"<b>المتبقي التقديري:</b> "
        f"${status['estimated_remaining']:.4f}\n"
        "<i>المتبقي تقديري حسب الرصيد المدخل.</i>"
    )

    telegram_send(message)
    account["last_daily_report"] = today
    save_account(account)


def send_heartbeat_if_needed() -> None:
    status = load_json(config.STATUS_FILE, {})
    now = datetime.now(RIYADH)
    last_value = status.get("last_heartbeat")
    last_heartbeat = None

    if last_value:
        try:
            last_heartbeat = datetime.fromisoformat(last_value)
            if last_heartbeat.tzinfo is None:
                last_heartbeat = last_heartbeat.replace(
                    tzinfo=RIYADH
                )
        except Exception:
            last_heartbeat = None

    if (
        last_heartbeat
        and (now - last_heartbeat).total_seconds()
        < config.HEARTBEAT_SECONDS
    ):
        return

    message = (
        "<b>⚡ برق نيوز</b>\n"
        "<b>✅ الرصد ما زال يعمل</b>\n"
        f"<b>الوقت:</b> {format_saudi_time(now)}\n"
        f"<b>آخر فحص:</b> "
        f"{format_saudi_time(status.get('last_check'))}\n"
        f"<b>الأخبار المفحوصة:</b> "
        f"{status.get('last_fetched', 0)}\n"
        f"<b>الإشعارات المرسلة:</b> "
        f"{status.get('last_sent', 0)}"
    )

    ok, _ = telegram_send(message)
    if ok:
        status["last_heartbeat"] = now.isoformat()
        save_json(config.STATUS_FILE, status)


def update_outcomes_if_needed() -> None:
    status = load_json(config.STATUS_FILE, {})
    now = datetime.now(RIYADH)
    last_value = status.get("last_outcome_update")
    last_update = None

    if last_value:
        try:
            last_update = datetime.fromisoformat(last_value)
            if last_update.tzinfo is None:
                last_update = last_update.replace(
                    tzinfo=RIYADH
                )
        except Exception:
            last_update = None

    if (
        last_update
        and (now - last_update).total_seconds()
        < config.OUTCOME_UPDATE_SECONDS
    ):
        return

    result = update_signal_outcomes()
    status["last_outcome_update"] = now.isoformat()
    status["last_outcome_records"] = result["updated_records"]
    status["last_outcome_tickers"] = result["updated_tickers"]
    status["last_outcome_errors"] = result["errors"][:10]
    save_json(config.STATUS_FILE, status)


def run() -> None:
    if not acquire_lock():
        return

    write_status(
        worker_alive=True,
        monitoring=False,
        message="عامل الرصد يعمل.",
    )

    while True:
        try:
            send_daily_report_if_needed()
            control = load_control()

            if not control.get("enabled"):
                write_status(
                    worker_alive=True,
                    monitoring=False,
                    message="الرصد متوقف.",
                )
                time.sleep(2)
                continue

            write_status(
                worker_alive=True,
                monitoring=True,
                message="جارٍ فحص الأخبار...",
            )

            raw_items = fetch_news(
                hours=2,
                limit=config.NEWS_LIMIT,
            )
            articles = process_articles(
                raw_items,
                hours=2,
                ai_enabled=bool(
                    control.get("ai_enabled", True)
                ),
                watchlist_only=True,
            )

            sent_ids = set(
                str(item)
                for item in load_json(
                    config.SENT_FILE,
                    [],
                )
            )
            feed = load_json(config.FEED_FILE, [])
            first_start = len(sent_ids) == 0
            sent_count = 0

            new_articles = [
                article
                for article in articles
                if str(article["id"]) not in sent_ids
            ]
            signal_map = record_signals_batch(new_articles)

            for article in new_articles:
                article_id = str(article["id"])
                sent_ids.add(article_id)

                records = signal_map.get(article_id) or []
                if records:
                    article["tracking"] = records[0]

                feed.insert(0, article)

                if (
                    is_positive(article)
                    and not first_start
                ):
                    ok, _ = telegram_send(
                        article_message(article)
                    )
                    if ok:
                        sent_count += 1

            save_json(
                config.SENT_FILE,
                list(sent_ids)[-20000:],
            )

            seen = set()
            clean_feed = []

            for article in feed:
                article_id = str(article.get("id"))
                if not article_id or article_id in seen:
                    continue

                seen.add(article_id)
                clean_feed.append(article)

            save_json(
                config.FEED_FILE,
                clean_feed[:2000],
            )

            write_status(
                worker_alive=True,
                monitoring=True,
                message="الرصد يعمل.",
                last_check=datetime.now(RIYADH).isoformat(),
                last_raw_fetched=len(raw_items),
                last_fetched=len(articles),
                last_sent=sent_count,
            )

            update_outcomes_if_needed()
            generate_daily_development_review(force=False)
            send_heartbeat_if_needed()

        except Exception as exc:
            write_status(
                worker_alive=True,
                monitoring=True,
                message=f"خطأ الرصد: {exc}",
                last_error=str(exc),
            )

        time.sleep(max(10, config.POLL_SECONDS))


if __name__ == "__main__":
    try:
        run()
    finally:
        try:
            config.WORKER_LOCK_FILE.unlink(
                missing_ok=True
            )
        except Exception:
            pass
