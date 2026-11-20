"""
services/transaction_service.py
Business logic untuk manajemen dan validasi transaksi keuangan.
Menangani deduplikasi, komitmen ke Google Sheets, antrean offline SQLite,
dan sinkronisasi data.
"""

import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from config import TIMEZONE
from integrations.google_sheets import get_client
from services.account_service import get_account_by_name, add_account, calculate_balance
from database.db import (
    save_pending_transaction,
    get_pending_transactions,
    mark_transaction_synced,
    log_activity,
)
from utils.validators import is_valid_amount, is_valid_date, is_duplicate_transaction

logger = logging.getLogger(__name__)


def _now() -> tuple[str, str]:
    """Mengembalikan tanggal dan waktu saat ini di timezone lokal."""
    tz = ZoneInfo(TIMEZONE)
    dt = datetime.now(tz)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")


def ensure_account_exists(account_name: str) -> None:
    """
    Jika akun belum terdaftar di Google Sheets, daftarkan otomatis
    dengan saldo awal 0 agar tidak terjadi inkonsistensi saldo.
    """
    if not account_name:
        return

    existing = get_account_by_name(account_name)
    if not existing:
        # Tentukan tipe berdasarkan nama
        name_lower = account_name.lower()
        if any(w in name_lower for w in ("gopay", "ovo", "dana", "shopeepay", "linkaja")):
            acc_type = "E-Wallet"
        elif any(w in name_lower for w in ("cash", "tunai", "dompet")):
            acc_type = "Cash"
        else:
            acc_type = "Bank"

        logger.info(f"Mendaftarkan akun baru otomatis: {account_name} ({acc_type})")
        add_account(name=account_name, acc_type=acc_type, initial_balance=0.0)


def commit_transaction(tx: dict, user_id: int = 0) -> tuple[bool, str, dict]:
    """
    Menyimpan transaksi yang sudah dikonfirmasi ke Google Sheets.
    Jika Google Sheets offline / error, simpan ke antrean pending SQLite.

    Return: (success: bool, status_message: str, saved_tx: dict)
    """
    # 1. Validasi nominal
    amount = tx.get("amount")
    if not is_valid_amount(amount):
        return False, "Nominal transaksi tidak valid.", tx

    amount_float = float(amount)
    tx["amount"] = int(amount_float) if amount_float.is_integer() else amount_float

    # 2. Tanggal & ID
    today_str, time_str = _now()
    if not tx.get("date") or not is_valid_date(str(tx.get("date"))):
        tx["date"] = today_str
    if not tx.get("time"):
        tx["time"] = time_str

    if not tx.get("transaction_id"):
        tx["transaction_id"] = f"TX-{uuid.uuid4().hex[:8].upper()}"

    tx["status"] = "Confirmed"
    tx["created_at"] = f"{tx['date']} {tx['time']}"

    # 3. Pastikan akun terdaftar di Accounts sheet
    tx_type = tx.get("type", "Expense")
    if tx_type == "Transfer":
        if tx.get("from_account"):
            ensure_account_exists(tx["from_account"])
        if tx.get("to_account"):
            ensure_account_exists(tx["to_account"])
    else:
        if tx.get("account"):
            ensure_account_exists(tx["account"])

    # 4. Cek duplikasi transaksi
    try:
        client = get_client()
        recent_txs = client.get_transactions(limit=20, status="Confirmed")
        if is_duplicate_transaction(recent_txs, tx, tolerance_seconds=90):
            logger.warning(f"Transaksi terdeteksi duplikat: {tx}")
            return False, "⚠️ Transaksi serupa baru saja dicatat (terdeteksi duplikat).", tx
    except Exception as e:
        logger.warning(f"Tidak dapat memeriksa duplikasi transaksi: {e}")

    # 5. Simpan ke Google Sheets
    sheets_success = False
    try:
        client = get_client()
        sheets_success = client.append_transaction(tx)
    except Exception as e:
        logger.error(f"Gagal append transaksi ke Sheets: {e}")
        sheets_success = False

    if sheets_success:
        log_activity(user_id, "TRANSACTION_SAVED_SHEETS", f"ID: {tx['transaction_id']}")
        return True, "sheets", tx
    else:
        # Fallback ke antrean SQLite
        save_pending_transaction(tx["transaction_id"], tx)
        log_activity(user_id, "TRANSACTION_SAVED_PENDING", f"ID: {tx['transaction_id']}")
        return True, "pending", tx


def sync_pending() -> int:
    """
    Sinkronisasi antrean transaksi pending di SQLite ke Google Sheets.
    Mengembalikan jumlah transaksi yang berhasil disinkronisasi.
    """
    pending = get_pending_transactions()
    if not pending:
        return 0

    client = get_client()
    if not client.is_connected():
        if not client.connect():
            return 0

    synced_count = 0
    for tx in pending:
        try:
            ok = client.append_transaction(tx)
            if ok:
                mark_transaction_synced(tx["transaction_id"])
                synced_count += 1
                logger.info(f"Sync transaksi {tx['transaction_id']} berhasil.")
        except Exception as e:
            logger.error(f"Gagal sync transaksi {tx.get('transaction_id')}: {e}")

    return synced_count


def get_recent_history(limit: int = 5) -> list[dict]:
    """Ambil riwayat transaksi terakhir dari Google Sheets."""
    try:
        client = get_client()
        txs = client.get_transactions(limit=limit, status="Confirmed")
        return list(reversed(txs))  # Terbaru di atas
    except Exception as e:
        logger.error(f"Gagal mengambil riwayat transaksi: {e}")
        return []

