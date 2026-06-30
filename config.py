from pathlib import Path

MASSIVE_API_KEY = ""
TELEGRAM_BOT_TOKEN = "8"
TELEGRAM_CHAT_ID = ""
OPENAI_API_KEY = "sk-proj--"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

MASSIVE_NEWS_URL = "https://api.massive.com/benzinga/v2/news"
MASSIVE_SNAPSHOT_URL = (
    "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
)

OPENAI_URL = "https://api.openai.com/v1/responses"
OPENAI_MODEL = "gpt-4.1-mini"

POLL_SECONDS = 30
HEARTBEAT_SECONDS = 1800
OUTCOME_UPDATE_SECONDS = 1800

# Benzinga يسمح بحد أقصى 50,000 نتيجة. نستخدم حدًا عمليًا أقل ثم نتبع next_url.
NEWS_LIMIT = 5000
NEWS_MAX_PAGES = 10

SYSTEM_POSITIVE_MIN = 45
AI_POSITIVE_MIN = 60
AI_ANALYZE_SYSTEM_MIN = 25
SYMBOL_AI_MAX_ARTICLES = 25

OPENAI_INPUT_USD_PER_1M = 0.40
OPENAI_OUTPUT_USD_PER_1M = 1.60

SIGNAL_TRACK_DAYS = 30
MAX_TRACKED_TICKERS_PER_UPDATE = 75

SYMBOLS_FILE = DATA_DIR / "symbols.txt"
CONTROL_FILE = DATA_DIR / "control.json"
STATUS_FILE = DATA_DIR / "status.json"
SENT_FILE = DATA_DIR / "sent_ids.json"
FEED_FILE = DATA_DIR / "feed.json"
RETRIEVAL_FILE = DATA_DIR / "retrieval_results.json"
ACCOUNT_FILE = DATA_DIR / "account.json"
USAGE_FILE = DATA_DIR / "openai_usage.json"
PAYMENTS_FILE = DATA_DIR / "payments.json"
SIGNALS_FILE = DATA_DIR / "signal_history.json"
WORKER_LOCK_FILE = DATA_DIR / "worker.lock"
