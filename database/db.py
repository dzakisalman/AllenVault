"""
Database module — SQLite setup untuk AllenVault.
Digunakan sebagai penyimpanan sementara sebelum data dikirim ke Google Sheets,
dan sebagai fallback ketika Google Sheets sedang tidak tersedia.
"""

import sqlite3
import logging
from pathlib import Path
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Buka koneksi ke SQLite database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Akses kolom dengan nama
    conn.execute("PRAGMA journal_mode=WAL")  # Lebih aman untuk concurrent access
    return conn


def init_db() -> None:
    """
    Inisialisasi semua tabel database.
    Aman dipanggil berkali-kali (CREATE TABLE IF NOT EXISTS).
    """
    logger.info("Menginisialisasi database SQLite...")
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Tabel transaksi sementara (pending sync ke Sheets)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_transactions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id   TEXT    NOT NULL UNIQUE,
                data_json        TEXT    NOT NULL,
                retry_count      INTEGER DEFAULT 0,
                created_at       TEXT    NOT NULL,
                synced_at        TEXT,
                sync_status      TEXT    DEFAULT 'pending'
                                        CHECK(sync_status IN ('pending','synced','failed'))
            )
        """)

        # Tabel sesi konfirmasi (menyimpan transaksi yang menunggu konfirmasi user)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS confirmation_sessions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL,
                session_key      TEXT    NOT NULL UNIQUE,
                data_json        TEXT    NOT NULL,
                session_type     TEXT    NOT NULL,
                created_at       TEXT    NOT NULL,
                expires_at       TEXT    NOT NULL
            )
        """)

        # Cache akun (untuk performa tanpa harus hit Sheets tiap saat)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_cache (
                account_id       TEXT    PRIMARY KEY,
                account_name     TEXT    NOT NULL,
                account_type     TEXT,
                initial_balance  REAL    DEFAULT 0,
                is_active        INTEGER DEFAULT 1,
                cached_at        TEXT    NOT NULL
            )
        """)

        # Log aktivitas bot
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL,
                action           TEXT    NOT NULL,
                detail           TEXT,
                created_at       TEXT    NOT NULL
            )
        """)

        conn.commit()
        logger.info("Database SQLite berhasil diinisialisasi.")

    except sqlite3.Error as e:
        logger.error(f"Error saat inisialisasi database: {e}")
        raise
    finally:
        conn.close()


# ─── Confirmation Sessions ───────────────────────────────────

import json
from datetime import datetime, timedelta
from typing import Optional


def save_confirmation_session(
    user_id: int,
    session_key: str,
    data: dict,
    session_type: str = "transaction",
    expiry_minutes: int = 60,
) -> bool:
    """Simpan sesi konfirmasi transaksi ke SQLite."""
    conn = get_connection()
    try:
        now = datetime.now()
        expires = now + timedelta(minutes=expiry_minutes)
        conn.execute(
            """
            INSERT OR REPLACE INTO confirmation_sessions 
            (user_id, session_key, data_json, session_type, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                session_key,
                json.dumps(data, ensure_ascii=False),
                session_type,
                now.strftime("%Y-%m-%d %H:%M:%S"),
                expires.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Gagal menyimpan confirmation session {session_key}: {e}")
        return False
    finally:
        conn.close()


def get_confirmation_session(session_key: str) -> Optional[dict]:
    """Ambil data sesi konfirmasi berdasarkan session_key jika belum expired."""
    conn = get_connection()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.cursor()
        cur.execute(
            """
            SELECT data_json, session_type, expires_at 
            FROM confirmation_sessions
            WHERE session_key = ? AND expires_at > ?
            """,
            (session_key, now_str),
        )
        row = cur.fetchone()
        if row:
            data = json.loads(row["data_json"])
            data["_session_type"] = row["session_type"]
            return data
        return None
    except Exception as e:
        logger.error(f"Gagal mengambil confirmation session {session_key}: {e}")
        return None
    finally:
        conn.close()


def update_confirmation_session(session_key: str, data: dict) -> bool:
    """Update data dalam sesi konfirmasi."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE confirmation_sessions
            SET data_json = ?
            WHERE session_key = ?
            """,
            (json.dumps(data, ensure_ascii=False), session_key),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Gagal update confirmation session {session_key}: {e}")
        return False
    finally:
        conn.close()


def delete_confirmation_session(session_key: str) -> bool:
    """Hapus sesi konfirmasi."""
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM confirmation_sessions WHERE session_key = ?",
            (session_key,),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Gagal menghapus confirmation session {session_key}: {e}")
        return False
    finally:
        conn.close()


# ─── Pending Transactions (Fallback Queue) ────────────────────

def save_pending_transaction(transaction_id: str, data: dict) -> bool:
    """Simpan transaksi pending untuk antrean sync ke Sheets saat offline."""
    conn = get_connection()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            INSERT OR REPLACE INTO pending_transactions
            (transaction_id, data_json, retry_count, created_at, sync_status)
            VALUES (?, ?, 0, ?, 'pending')
            """,
            (transaction_id, json.dumps(data, ensure_ascii=False), now_str),
        )
        conn.commit()
        logger.info(f"Transaksi {transaction_id} disimpan ke pending queue SQLite.")
        return True
    except Exception as e:
        logger.error(f"Gagal simpan pending transaction {transaction_id}: {e}")
        return False
    finally:
        conn.close()


def get_pending_transactions() -> list[dict]:
    """Ambil daftar transaksi yang belum ter-sync ke Sheets."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT transaction_id, data_json, retry_count
            FROM pending_transactions
            WHERE sync_status = 'pending'
            ORDER BY id ASC
            """
        )
        rows = cur.fetchall()
        result = []
        for r in rows:
            data = json.loads(r["data_json"])
            data["_retry_count"] = r["retry_count"]
            result.append(data)
        return result
    except Exception as e:
        logger.error(f"Gagal membaca pending transactions: {e}")
        return []
    finally:
        conn.close()


def mark_transaction_synced(transaction_id: str) -> bool:
    """Tandai transaksi sudah tersinkronisasi ke Sheets."""
    conn = get_connection()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            UPDATE pending_transactions
            SET sync_status = 'synced', synced_at = ?
            WHERE transaction_id = ?
            """,
            (now_str, transaction_id),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Gagal update sync status {transaction_id}: {e}")
        return False
    finally:
        conn.close()


# ─── Activity Log ─────────────────────────────────────────────

def log_activity(user_id: int, action: str, detail: str = "") -> None:
    """Catat aktivitas pengguna."""
    conn = get_connection()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            INSERT INTO activity_log (user_id, action, detail, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, action, detail, now_str),
        )
        conn.commit()
    except Exception as e:
        logger.warning(f"Gagal mencatat log aktivitas: {e}")
    finally:
        conn.close()

