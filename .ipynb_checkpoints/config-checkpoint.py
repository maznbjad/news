MASSIVE_API_KEY = "mJCTSFzMQ1Gf8igHUGrKAun6GA4xP_Mq"
TELEGRAM_BOT_TOKEN = "8831935365:AAEYl7vtj6UnEQgvW1TIuEvB4QB5yTv8Iko"
TELEGRAM_CHAT_ID = "849742381"
OPENAI_API_KEY = "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"

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MASSIVE_NEWS_URL = "https://api.massive.com/benzinga/v2/news"
OPENAI_URL = "https://api.openai.com/v1/responses"
OPENAI_MODEL = "gpt-4.1-mini"
POLL_SECONDS = 15
NEWS_LIMIT = 1000
SYSTEM_POSITIVE_MIN = 55
AI_POSITIVE_MIN = 65
AI_ANALYZE_SYSTEM_MIN = 35
OPENAI_INPUT_USD_PER_1M = 0.40
OPENAI_OUTPUT_USD_PER_1M = 1.60
SYMBOLS_FILE = DATA_DIR / "symbols.txt"
CONTROL_FILE = DATA_DIR / "control.json"
STATUS_FILE = DATA_DIR / "status.json"
SENT_FILE = DATA_DIR / "sent_ids.json"
FEED_FILE = DATA_DIR / "feed.json"
RETRIEVAL_FILE = DATA_DIR / "retrieval_results.json"
ACCOUNT_FILE = DATA_DIR / "account.json"
USAGE_FILE = DATA_DIR / "openai_usage.json"
PAYMENTS_FILE = DATA_DIR / "payments.json"
WORKER_LOCK_FILE = DATA_DIR / "worker.lock"
