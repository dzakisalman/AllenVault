"""
AllenVault Configuration Module
Memuat semua environment variables dan konstanta aplikasi.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file dari root proyek
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


# ─── Telegram ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

_raw_ids = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: list[int] = [
    int(uid.strip())
    for uid in _raw_ids.split(",")
    if uid.strip().isdigit()
]


# ─── Google Sheets ────────────────────────────────────────────
GOOGLE_SPREADSHEET_ID: str = os.getenv("GOOGLE_SPREADSHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON: str = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_JSON", "credentials.json"
)

# Scopes yang dibutuhkan untuk Google Sheets
GOOGLE_SCOPES: list[str] = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


# ─── Database ────────────────────────────────────────────────
DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "allenvault.db"))


# ─── Aplikasi ────────────────────────────────────────────────
TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Jakarta")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# AI (Phase 4)
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")


# ─── Tab Names di Google Sheets ──────────────────────────────
SHEET_TRANSACTIONS = "Transactions"
SHEET_ACCOUNTS = "Accounts"
SHEET_CATEGORIES = "Categories"
SHEET_BUDGETS = "Budgets"
SHEET_SETTINGS = "Settings"
SHEET_RECEIPT_ITEMS = "Receipt_Items"
SHEET_DASHBOARD = "Dashboard"

REQUIRED_SHEETS = [
    SHEET_TRANSACTIONS,
    SHEET_ACCOUNTS,
    SHEET_CATEGORIES,
    SHEET_BUDGETS,
    SHEET_SETTINGS,
    SHEET_RECEIPT_ITEMS,
]


# ─── Header kolom per sheet ───────────────────────────────────
TRANSACTIONS_HEADERS = [
    "transaction_id", "date", "time", "type", "category",
    "description", "amount", "payment_method", "account",
    "from_account", "to_account", "merchant", "source",
    "status", "created_at",
]

ACCOUNTS_HEADERS = [
    "account_id", "account_name", "account_type",
    "initial_balance", "is_active",
]

CATEGORIES_HEADERS = [
    "category_id", "category_name", "type", "is_active",
]

BUDGETS_HEADERS = [
    "budget_id", "month", "category", "budget_amount",
]

SETTINGS_HEADERS = [
    "setting_key", "setting_value", "description",
]

RECEIPT_ITEMS_HEADERS = [
    "item_id", "transaction_id", "item_name",
    "quantity", "unit_price", "subtotal",
]

SHEET_HEADERS: dict[str, list[str]] = {
    SHEET_TRANSACTIONS:  TRANSACTIONS_HEADERS,
    SHEET_ACCOUNTS:      ACCOUNTS_HEADERS,
    SHEET_CATEGORIES:    CATEGORIES_HEADERS,
    SHEET_BUDGETS:       BUDGETS_HEADERS,
    SHEET_SETTINGS:      SETTINGS_HEADERS,
    SHEET_RECEIPT_ITEMS: RECEIPT_ITEMS_HEADERS,
}


# ─── Default Categories ───────────────────────────────────────
DEFAULT_EXPENSE_CATEGORIES = [
    "Makanan & Minuman",
    "Transportasi",
    "Belanja",
    "Kesehatan",
    "Hiburan",
    "Tagihan & Utilitas",
    "Pendidikan",
    "Perawatan Diri",
    "Rumah Tangga",
    "Lain-lain",
]

DEFAULT_INCOME_CATEGORIES = [
    "Gaji",
    "Freelance",
    "Bisnis",
    "Investasi",
    "Hadiah",
    "Lain-lain",
]


# ─── Validasi konfigurasi ─────────────────────────────────────
def validate_config() -> list[str]:
    """
    Periksa konfigurasi wajib. Return list of error strings.
    """
    errors = []
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        errors.append("TELEGRAM_BOT_TOKEN belum diatur di file .env")
    if not ALLOWED_USER_IDS:
        errors.append("ALLOWED_USER_IDS belum diatur di file .env")
    if not GOOGLE_SPREADSHEET_ID or GOOGLE_SPREADSHEET_ID == "your_spreadsheet_id_here":
        errors.append("GOOGLE_SPREADSHEET_ID belum diatur di file .env")
    return errors


# ─── Logging setup ────────────────────────────────────────────
def setup_logging() -> None:
    """Konfigurasi logging untuk seluruh aplikasi."""
    numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Kurangi kebisingan log dari library pihak ketiga
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("gspread").setLevel(logging.WARNING)

