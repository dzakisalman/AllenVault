"""
services/account_service.py
Business logic untuk manajemen akun keuangan.
Semua perhitungan saldo dilakukan di Python — TIDAK oleh AI.
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from config import TIMEZONE
from integrations.google_sheets import get_client

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")


# ─── Ambil data akun ──────────────────────────────────────────

def get_all_accounts(active_only: bool = True) -> list[dict]:
    """Ambil semua akun dari Google Sheets."""
    try:
        client = get_client()
        return client.get_accounts(active_only=active_only)
    except Exception as e:
        logger.error(f"Gagal ambil akun: {e}")
        return []


def get_account_by_name(name: str) -> Optional[dict]:
    """Cari akun berdasarkan nama (case-insensitive, partial match)."""
    accounts = get_all_accounts()
    name_lower = name.lower().strip()
    for acc in accounts:
        if acc.get("account_name", "").lower() == name_lower:
            return acc
    # Partial match
    for acc in accounts:
        if name_lower in acc.get("account_name", "").lower():
            return acc
    return None


def find_account_from_text(text: str) -> Optional[dict]:
    """
    Coba temukan akun yang disebutkan dalam teks transaksi.
    Contoh: "pakai BCA" → akun BCA
    """
    if not text:
        return None
    accounts = get_all_accounts()
    text_lower = text.lower()
    for acc in accounts:
        name = acc.get("account_name", "").lower()
        if name and name in text_lower:
            return acc
    return None


# ─── Tambah akun ──────────────────────────────────────────────

def add_account(
    name: str,
    acc_type: str = "Bank",
    initial_balance: float = 0.0,
) -> tuple[bool, str]:
    """
    Tambah akun baru ke Google Sheets.
    Return (success, message).
    """
    name = name.strip()
    if not name:
        return False, "Nama akun tidak boleh kosong."

    # Cek duplikasi
    existing = get_account_by_name(name)
    if existing:
        return False, f"Akun '{name}' sudah ada."

    # Validasi tipe
    valid_types = {"Bank", "E-Wallet", "Cash"}
    if acc_type not in valid_types:
        acc_type = "Bank"

    account_id = f"ACC-{uuid.uuid4().hex[:6].upper()}"
    account = {
        "account_id": account_id,
        "account_name": name,
        "account_type": acc_type,
        "initial_balance": str(int(initial_balance)),
        "is_active": "TRUE",
    }

    try:
        client = get_client()
        ok = client.append_account(account)
        if ok:
            logger.info(f"Akun baru ditambahkan: {name} ({acc_type}), saldo awal: {initial_balance}")
            return True, account_id
        return False, "Gagal menyimpan akun ke Google Sheets."
    except Exception as e:
        logger.error(f"Error tambah akun: {e}")
        return False, f"Error: {e}"


# ─── Hitung saldo ─────────────────────────────────────────────

def calculate_balance(account_name: str) -> float:
    """
    Hitung saldo akun berdasarkan:
    Initial Balance + Income - Expense + Transfer In - Transfer Out
    Semua perhitungan dilakukan Python, bukan AI.
    """
    try:
        client = get_client()

        # Ambil initial balance dari Accounts
        accounts = client.get_accounts(active_only=False)
        initial = 0.0
        for acc in accounts:
            if acc.get("account_name", "").lower() == account_name.lower():
                try:
                    initial = float(acc.get("initial_balance", 0))
                except (ValueError, TypeError):
                    initial = 0.0
                break

        # Ambil semua transaksi confirmed
        ws = client.get_worksheet("Transactions")
        if not ws:
            return initial

        records = ws.get_all_records()
        confirmed = [r for r in records if r.get("status") == "Confirmed"]

        balance = initial
        name_lower = account_name.lower()

        for tx in confirmed:
            try:
                raw_amt = str(tx.get("amount", 0)).strip()
                if raw_amt.endswith(",00") or raw_amt.endswith(".00"):
                    raw_amt = raw_amt[:-3]
                cleaned = re.sub(r"[^\d]", "", raw_amt)
                amount = float(cleaned) if cleaned else 0.0
            except (ValueError, TypeError):
                continue

            tx_type = tx.get("type", "")
            account = str(tx.get("account", "")).lower()
            from_acc = str(tx.get("from_account", "")).lower()
            to_acc = str(tx.get("to_account", "")).lower()

            if tx_type == "Income" and account == name_lower:
                balance += amount
            elif tx_type == "Expense" and account == name_lower:
                balance -= amount
            elif tx_type == "Transfer":
                if from_acc == name_lower:
                    balance -= amount
                if to_acc == name_lower:
                    balance += amount

        return balance

    except Exception as e:
        logger.error(f"Gagal hitung saldo '{account_name}': {e}")
        return 0.0


def get_all_balances() -> list[dict]:
    """
    Hitung saldo semua akun aktif dalam SATU kali baca Google Sheets (efisien & hemat kuota API).
    Return list of {account_name, account_type, balance}.
    """
    try:
        client = get_client()
        accounts = client.get_accounts(active_only=False)
        confirmed_txs = client.get_transactions(limit=2000, status="Confirmed")

        balances = {}
        account_info = {}
        for acc in accounts:
            name = acc.get("account_name", "")
            if not name:
                continue
            try:
                init = float(acc.get("initial_balance", 0))
            except (ValueError, TypeError):
                init = 0.0
            lower = name.lower().strip()
            balances[lower] = init
            account_info[lower] = {
                "account_name": name,
                "account_type": acc.get("account_type", "Bank"),
                "is_active": str(acc.get("is_active", "")).upper() == "TRUE",
            }

        for tx in confirmed_txs:
            try:
                raw_amt = str(tx.get("amount", 0)).strip()
                if raw_amt.endswith(",00") or raw_amt.endswith(".00"):
                    raw_amt = raw_amt[:-3]
                cleaned = re.sub(r"[^\d]", "", raw_amt)
                amount = float(cleaned) if cleaned else 0.0
            except (ValueError, TypeError):
                continue

            tx_type = tx.get("type", "")
            account = str(tx.get("account", "")).lower().strip()
            from_acc = str(tx.get("from_account", "")).lower().strip()
            to_acc = str(tx.get("to_account", "")).lower().strip()

            if tx_type == "Income" and account in balances:
                balances[account] += amount
            elif tx_type == "Expense" and account in balances:
                balances[account] -= amount
            elif tx_type == "Transfer":
                if from_acc in balances:
                    balances[from_acc] -= amount
                if to_acc in balances:
                    balances[to_acc] += amount

        result = []
        for lower_name, info in account_info.items():
            if info["is_active"]:
                result.append({
                    "account_name": info["account_name"],
                    "account_type": info["account_type"],
                    "balance": balances.get(lower_name, 0.0),
                })
        return result
    except Exception as e:
        logger.error(f"Gagal hitung semua saldo: {e}")
        return []

