"""
Utils — Validators
Fungsi-fungsi untuk memvalidasi input sebelum disimpan.
"""

import re
from datetime import datetime


def is_valid_amount(value) -> bool:
    """Periksa apakah nilai adalah nominal yang valid (positif)."""
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def is_valid_date(date_str: str, fmt: str = "%Y-%m-%d") -> bool:
    """Periksa apakah string adalah tanggal yang valid."""
    try:
        datetime.strptime(date_str, fmt)
        return True
    except (ValueError, TypeError):
        return False


def is_valid_transaction_type(tx_type: str) -> bool:
    return tx_type in {"Income", "Expense", "Transfer"}


def sanitize_text(text: str, max_length: int = 255) -> str:
    """Bersihkan teks dari karakter berbahaya dan batasi panjangnya."""
    if not text:
        return ""
    # Hapus karakter kontrol
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", text.strip())
    return cleaned[:max_length]


def is_duplicate_transaction(
    existing_transactions: list[dict],
    new_tx: dict,
    tolerance_seconds: int = 60,
) -> bool:
    """
    Deteksi transaksi duplikat berdasarkan:
    - Jenis, jumlah, dan akun yang sama
    - Waktu berdekatan (dalam toleransi_seconds)
    """
    try:
        new_amount = float(new_tx.get("amount", 0))
        new_type = new_tx.get("type", "")
        new_account = new_tx.get("account", "")
        new_dt_str = f"{new_tx.get('date', '')} {new_tx.get('time', '00:00:00')}"
        new_dt = datetime.strptime(new_dt_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return False

    for tx in existing_transactions:
        try:
            if tx.get("type") != new_type:
                continue
            if abs(float(tx.get("amount", 0)) - new_amount) > 0.01:
                continue
            if tx.get("account", "") != new_account:
                continue
            existing_dt_str = f"{tx.get('date', '')} {tx.get('time', '00:00:00')}"
            existing_dt = datetime.strptime(existing_dt_str, "%Y-%m-%d %H:%M:%S")
            if abs((new_dt - existing_dt).total_seconds()) <= tolerance_seconds:
                return True
        except (ValueError, TypeError):
            continue

    return False

