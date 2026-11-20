"""
integrations/google_sheets.py
Modul utama integrasi Google Sheets untuk AllenVault.
Bertanggung jawab atas koneksi, inisialisasi tab, dan operasi CRUD.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Optional

import gspread
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
from google.oauth2.service_account import Credentials

import config
from config import (
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SPREADSHEET_ID,
    GOOGLE_SCOPES,
    REQUIRED_SHEETS,
    SHEET_HEADERS,
    SHEET_TRANSACTIONS,
    SHEET_ACCOUNTS,
    SHEET_CATEGORIES,
    SHEET_BUDGETS,
    SHEET_SETTINGS,
    DEFAULT_EXPENSE_CATEGORIES,
    DEFAULT_INCOME_CATEGORIES,
)

logger = logging.getLogger(__name__)

# Tab lama milik user — JANGAN DISENTUH
PROTECTED_TABS = {"2 TUNAI", "2 NON TUNAI", "Sheet3", "TUNAI", "NON TUNAI"}

# Warna header AllenVault (biru teal)
HEADER_BG_COLOR = {"red": 0.13, "green": 0.59, "blue": 0.95}
HEADER_FG_COLOR = {"red": 1.0, "green": 1.0, "blue": 1.0}


class GoogleSheetsClient:
    """
    Client tunggal untuk semua operasi Google Sheets.
    Gunakan get_client() untuk mendapatkan instance yang sudah terkoneksi.
    """

    def __init__(self):
        self._gc: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None
        self._cache: dict = {}
        self._cache_time: dict = {}
        self._cache_ttl: float = 30.0  # 30 detik TTL cache untuk hemat kuota API

    # ─── Koneksi ─────────────────────────────────────────────

    def connect(self) -> bool:
        """
        Buka koneksi ke Google Sheets.
        Mendukung file credentials lokal maupun raw JSON string dari environment variable (Vercel/Cloud).
        Return True jika berhasil, False jika gagal.
        """
        try:
            # 1. Cek apakah ada raw JSON string di environment variable (untuk Vercel/Cloud deployment)
            raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_RAW")
            if not raw_json and GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SERVICE_ACCOUNT_JSON.strip().startswith("{"):
                raw_json = GOOGLE_SERVICE_ACCOUNT_JSON

            if raw_json:
                info = json.loads(raw_json)
                creds = Credentials.from_service_account_info(
                    info,
                    scopes=GOOGLE_SCOPES,
                )
            else:
                creds = Credentials.from_service_account_file(
                    GOOGLE_SERVICE_ACCOUNT_JSON,
                    scopes=GOOGLE_SCOPES,
                )

            self._gc = gspread.authorize(creds)
            self._spreadsheet = self._gc.open_by_key(GOOGLE_SPREADSHEET_ID)
            logger.info(
                f"Terhubung ke spreadsheet: '{self._spreadsheet.title}'"
            )
            return True
        except FileNotFoundError:
            logger.error(
                f"File credentials tidak ditemukan: {GOOGLE_SERVICE_ACCOUNT_JSON}"
            )
        except SpreadsheetNotFound:
            logger.error(
                f"Spreadsheet tidak ditemukan. Cek GOOGLE_SPREADSHEET_ID dan pastikan "
                f"spreadsheet sudah di-share ke service account."
            )
        except APIError as e:
            logger.error(f"Google Sheets API error: {e}")
        except Exception as e:
            logger.error(f"Gagal terhubung ke Google Sheets: {e}")
        return False

    def is_connected(self) -> bool:
        return self._spreadsheet is not None

    def _require_connection(self):
        if not self.is_connected():
            raise ConnectionError(
                "Belum terhubung ke Google Sheets. Panggil connect() terlebih dahulu."
            )

    # ─── Worksheet helpers ────────────────────────────────────

    def get_worksheet(self, name: str) -> Optional[gspread.Worksheet]:
        """Ambil worksheet berdasarkan nama. Return None jika tidak ada."""
        self._require_connection()
        try:
            return self._spreadsheet.worksheet(name)
        except WorksheetNotFound:
            return None

    def worksheet_exists(self, name: str) -> bool:
        return self.get_worksheet(name) is not None

    def list_worksheets(self) -> list[str]:
        """Return daftar nama semua worksheet."""
        self._require_connection()
        return [ws.title for ws in self._spreadsheet.worksheets()]

    # ─── Inisialisasi tab AllenVault ──────────────────────────

    def init_allenvault_sheets(self) -> dict[str, str]:
        """
        Periksa dan buat tab AllenVault yang belum ada.
        Tab lama (PROTECTED_TABS) tidak akan disentuh.
        Return dict {sheet_name: 'created'|'exists'}.
        """
        self._require_connection()
        results = {}
        existing = self.list_worksheets()
        logger.info(f"Tab yang ada: {existing}")

        for sheet_name in REQUIRED_SHEETS:
            if sheet_name in existing:
                logger.info(f"Tab '{sheet_name}' sudah ada — dilewati.")
                results[sheet_name] = "exists"
            else:
                self._create_sheet_with_headers(sheet_name)
                results[sheet_name] = "created"
                logger.info(f"Tab '{sheet_name}' berhasil dibuat.")

        return results

    def _create_sheet_with_headers(self, sheet_name: str) -> gspread.Worksheet:
        """Buat worksheet baru dengan header yang sesuai dan format header."""
        headers = SHEET_HEADERS.get(sheet_name, [])

        # Buat tab baru di akhir
        ws = self._spreadsheet.add_worksheet(
            title=sheet_name,
            rows=1000,
            cols=max(len(headers), 10),
        )
        time.sleep(0.5)  # Hindari rate limit

        if headers:
            ws.append_row(headers, value_input_option="RAW")
            time.sleep(0.3)
            self._format_header_row(ws, len(headers))

        return ws

    def _format_header_row(self, ws: gspread.Worksheet, col_count: int) -> None:
        """Beri warna biru pada baris header dan bold teks."""
        try:
            ws.format(
                f"A1:{chr(64 + min(col_count, 26))}1",
                {
                    "backgroundColor": HEADER_BG_COLOR,
                    "textFormat": {
                        "foregroundColor": HEADER_FG_COLOR,
                        "bold": True,
                    },
                    "horizontalAlignment": "CENTER",
                },
            )
        except Exception as e:
            logger.warning(f"Gagal memformat header '{ws.title}': {e}")

    # ─── Seed data default ────────────────────────────────────

    def seed_default_data(self) -> dict:
        """
        Isi data default jika tab masih kosong:
        - Categories: expense & income defaults
        - Settings: konfigurasi awal
        Return dict hasil seeding.
        """
        self._require_connection()
        results = {}

        # Categories
        cat_ws = self.get_worksheet("Categories")
        if cat_ws:
            existing = cat_ws.get_all_values()
            if len(existing) <= 1:  # Hanya header atau kosong
                rows = []
                for i, name in enumerate(DEFAULT_EXPENSE_CATEGORIES, 1):
                    rows.append([f"EXP{i:02d}", name, "Expense", "TRUE"])
                for i, name in enumerate(DEFAULT_INCOME_CATEGORIES, 1):
                    rows.append([f"INC{i:02d}", name, "Income", "TRUE"])
                cat_ws.append_rows(rows, value_input_option="RAW")
                results["categories"] = f"{len(rows)} kategori ditambahkan"
                logger.info(f"Seed categories: {len(rows)} baris")
            else:
                results["categories"] = "sudah ada data"

        # Settings
        set_ws = self.get_worksheet("Settings")
        if set_ws:
            existing = set_ws.get_all_values()
            if len(existing) <= 1:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rows = [
                    ["currency", "IDR", "Mata uang"],
                    ["timezone", "Asia/Jakarta", "Timezone aplikasi"],
                    ["initialized_at", now, "Tanggal inisialisasi AllenVault"],
                    ["version", "1.0.0", "Versi AllenVault"],
                ]
                set_ws.append_rows(rows, value_input_option="RAW")
                results["settings"] = f"{len(rows)} setting ditambahkan"
                logger.info("Seed settings selesai")
            else:
                results["settings"] = "sudah ada data"

        return results

    # ─── CRUD: Transactions ───────────────────────────────────

    def append_transaction(self, tx: dict) -> bool:
        """
        Tambah satu baris transaksi ke tab Transactions.
        Return True jika berhasil.
        """
        self._require_connection()
        ws = self.get_worksheet(SHEET_TRANSACTIONS)
        if not ws:
            logger.error("Tab Transactions tidak ditemukan.")
            return False
        try:
            headers = SHEET_HEADERS[SHEET_TRANSACTIONS]
            row = [str(tx.get(h, "")) for h in headers]
            ws.append_row(row, value_input_option="USER_ENTERED")
            self._cache.pop("transactions_all", None)
            logger.info(f"Transaksi {tx.get('transaction_id')} disimpan ke Sheets.")
            return True
        except APIError as e:
            logger.error(f"Gagal menyimpan transaksi: {e}")
            return False

    def get_transactions(
        self,
        limit: int = 100,
        status: str = "Confirmed",
        force_refresh: bool = False,
    ) -> list[dict]:
        """
        Baca transaksi dari tab Transactions dengan caching in-memory 30 detik untuk hemat kuota.
        Return list of dicts dengan key = nama kolom header.
        """
        now = time.time()
        cache_key = "transactions_all"
        if not force_refresh and cache_key in self._cache and (now - self._cache_time.get(cache_key, 0) < self._cache_ttl):
            records = self._cache[cache_key]
            if status:
                records = [r for r in records if r.get("status") == status]
            return records[-limit:]

        self._require_connection()
        ws = self.get_worksheet(SHEET_TRANSACTIONS)
        if not ws:
            return self._cache.get(cache_key, [])[-limit:]
        try:
            records = ws.get_all_records(expected_headers=SHEET_HEADERS[SHEET_TRANSACTIONS])
            self._cache[cache_key] = records
            self._cache_time[cache_key] = now
            if status:
                records = [r for r in records if r.get("status") == status]
            return records[-limit:]
        except Exception as e:
            logger.error(f"Gagal membaca transaksi: {e}")
            if cache_key in self._cache:
                logger.warning("Menggunakan cache transaksi sebelumnya (fallback 429/error).")
                records = self._cache[cache_key]
                if status:
                    records = [r for r in records if r.get("status") == status]
                return records[-limit:]
            return []

    # ─── CRUD: Accounts ───────────────────────────────────────

    def get_accounts(self, active_only: bool = True, force_refresh: bool = False) -> list[dict]:
        """Baca semua akun dari tab Accounts dengan caching in-memory."""
        now = time.time()
        cache_key = "accounts_all"
        if not force_refresh and cache_key in self._cache and (now - self._cache_time.get(cache_key, 0) < self._cache_ttl):
            records = self._cache[cache_key]
            if active_only:
                records = [r for r in records if str(r.get("is_active", "")).upper() == "TRUE"]
            return records

        self._require_connection()
        ws = self.get_worksheet(SHEET_ACCOUNTS)
        if not ws:
            return self._cache.get(cache_key, [])
        try:
            records = ws.get_all_records()
            self._cache[cache_key] = records
            self._cache_time[cache_key] = now
            if active_only:
                records = [r for r in records if str(r.get("is_active", "")).upper() == "TRUE"]
            return records
        except Exception as e:
            logger.error(f"Gagal membaca akun: {e}")
            if cache_key in self._cache:
                logger.warning("Menggunakan cache akun sebelumnya (fallback 429/error).")
                records = self._cache[cache_key]
                if active_only:
                    records = [r for r in records if str(r.get("is_active", "")).upper() == "TRUE"]
                return records
            return []

    def append_account(self, account: dict) -> bool:
        """Tambah akun baru ke tab Accounts."""
        self._require_connection()
        ws = self.get_worksheet(SHEET_ACCOUNTS)
        if not ws:
            return False
        try:
            headers = SHEET_HEADERS[SHEET_ACCOUNTS]
            row = [str(account.get(h, "")) for h in headers]
            ws.append_row(row, value_input_option="USER_ENTERED")
            self._cache.pop("accounts_all", None)
            return True
        except APIError as e:
            logger.error(f"Gagal menambah akun: {e}")
            return False

    # ─── CRUD: Categories ─────────────────────────────────────

    def get_categories(self, tx_type: Optional[str] = None) -> list[dict]:
        """Baca kategori, opsional filter berdasarkan type (Income/Expense)."""
        self._require_connection()
        ws = self.get_worksheet("Categories")
        if not ws:
            return []
        try:
            records = ws.get_all_records()
            records = [r for r in records if str(r.get("is_active", "")).upper() == "TRUE"]
            if tx_type:
                records = [r for r in records if r.get("type") == tx_type]
            return records
        except Exception as e:
            logger.error(f"Gagal membaca kategori: {e}")
            return []

    # ─── CRUD: Settings ───────────────────────────────────────

    def get_setting(self, key: str) -> Optional[str]:
        """Ambil nilai setting berdasarkan key."""
        self._require_connection()
        ws = self.get_worksheet("Settings")
        if not ws:
            return None
        try:
            records = ws.get_all_records()
            for r in records:
                if r.get("setting_key") == key:
                    return str(r.get("setting_value", ""))
        except Exception as e:
            logger.error(f"Gagal membaca setting: {e}")
        return None

    # ─── CRUD: Receipt Items ──────────────────────────────────

    def append_receipt_items(self, items: list[dict]) -> bool:
        """Simpan daftar item struk ke tab Receipt_Items."""
        self._require_connection()
        ws = self.get_worksheet("Receipt_Items")
        if not ws:
            return False
        try:
            headers = SHEET_HEADERS["Receipt_Items"]
            rows = [[str(item.get(h, "")) for h in headers] for item in items]
            ws.append_rows(rows, value_input_option="USER_ENTERED")
            return True
        except APIError as e:
            logger.error(f"Gagal menyimpan receipt items: {e}")
            return False

    # ─── CRUD: Budgets ────────────────────────────────────────

    def get_budgets(self, month: Optional[str] = None, force_refresh: bool = False) -> list[dict]:
        """Baca anggaran dari tab Budgets, opsional filter berdasarkan month (YYYY-MM)."""
        now = time.time()
        cache_key = "budgets_all"
        if not force_refresh and cache_key in self._cache and (now - self._cache_time.get(cache_key, 0) < self._cache_ttl):
            records = self._cache[cache_key]
            if month:
                records = [r for r in records if str(r.get("month", "")).strip() == month]
            return records

        self._require_connection()
        ws = self.get_worksheet(SHEET_BUDGETS)
        if not ws:
            return self._cache.get(cache_key, [])
        try:
            records = ws.get_all_records()
            self._cache[cache_key] = records
            self._cache_time[cache_key] = now
            if month:
                records = [r for r in records if str(r.get("month", "")).strip() == month]
            return records
        except Exception as e:
            logger.error(f"Gagal membaca budgets: {e}")
            if cache_key in self._cache:
                logger.warning("Menggunakan cache budgets sebelumnya (fallback 429/error).")
                records = self._cache[cache_key]
                if month:
                    records = [r for r in records if str(r.get("month", "")).strip() == month]
                return records
            return []

    def upsert_budget(self, month: str, category: str, amount: float) -> bool:
        """Tambah atau update anggaran untuk kategori dan bulan tertentu di tab Budgets."""
        self._require_connection()
        ws = self.get_worksheet(SHEET_BUDGETS)
        if not ws:
            return False
        try:
            records = ws.get_all_records()
            for idx, r in enumerate(records, start=2):  # baris 1 adalah header
                if (str(r.get("month", "")).strip() == month and 
                    str(r.get("category", "")).strip().lower() == category.lower()):
                    # Kolom 4 adalah budget_amount
                    ws.update_cell(idx, 4, amount)
                    self._cache.pop("budgets_all", None)
                    logger.info(f"Budget {category} ({month}) diupdate ke {amount}")
                    return True

            budget_id = f"BGT-{uuid.uuid4().hex[:6].upper()}"
            ws.append_row([budget_id, month, category, amount], value_input_option="USER_ENTERED")
            self._cache.pop("budgets_all", None)
            logger.info(f"Budget baru {category} ({month}) ditambahkan: {amount}")
            return True
        except Exception as e:
            logger.error(f"Gagal menyimpan budget: {e}")
            return False

    # ─── Healthcheck ──────────────────────────────────────────

    def ping(self) -> bool:
        """Test koneksi dengan membaca metadata spreadsheet."""
        try:
            self._require_connection()
            _ = self._spreadsheet.title
            return True
        except Exception:
            return False


# ─── Singleton instance ───────────────────────────────────────
_client: Optional[GoogleSheetsClient] = None


def get_client() -> GoogleSheetsClient:
    """
    Return singleton GoogleSheetsClient yang sudah terkoneksi.
    Panggil ini dari mana saja untuk mendapatkan client.
    """
    global _client
    if _client is None:
        _client = GoogleSheetsClient()
    if not _client.is_connected():
        _client.connect()
    return _client

