"""
Keyboard module — Inline dan Reply keyboards untuk Telegram bot.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from config import TIMEZONE

# ─── Callback data constants ──────────────────────────────────
CB_CONFIRM = "confirm"
CB_EDIT = "edit"
CB_CANCEL = "cancel"
CB_SEL_ACC = "sel_acc"
CB_SEL_CAT = "sel_cat"
CB_SEL_DATE = "sel_date"
CB_EDIT_FIELD = "edit_field"


def confirm_keyboard(session_key: str) -> InlineKeyboardMarkup:
    """Keyboard konfirmasi transaksi dengan tombol Confirm / Edit / Cancel."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Konfirmasi", callback_data=f"{CB_CONFIRM}:{session_key}"),
            InlineKeyboardButton("✏️ Edit",       callback_data=f"{CB_EDIT}:{session_key}"),
            InlineKeyboardButton("❌ Batalkan",   callback_data=f"{CB_CANCEL}:{session_key}"),
        ]
    ])


def missing_account_keyboard(session_key: str, existing_accounts: list[dict] = None) -> InlineKeyboardMarkup:
    """
    Keyboard pilihan akun saat pengguna mencatat transaksi tanpa menyebutkan akun.
    Menampilkan akun yang sudah terdaftar atau akun populer.
    """
    rows = []
    if existing_accounts:
        # Tampilkan akun-akun yang sudah ada
        acc_names = [a.get("account_name") for a in existing_accounts if a.get("account_name")]
        for i in range(0, len(acc_names), 2):
            row = [
                InlineKeyboardButton(name, callback_data=f"{CB_SEL_ACC}:{session_key}:account:{name}")
                for name in acc_names[i:i+2]
            ]
            rows.append(row)
    else:
        # Default pilihan populer
        rows = [
            [
                InlineKeyboardButton("💵 Cash", callback_data=f"{CB_SEL_ACC}:{session_key}:account:Cash"),
                InlineKeyboardButton("🏦 BCA", callback_data=f"{CB_SEL_ACC}:{session_key}:account:BCA"),
            ],
            [
                InlineKeyboardButton("📱 GoPay", callback_data=f"{CB_SEL_ACC}:{session_key}:account:GoPay"),
                InlineKeyboardButton("📱 DANA", callback_data=f"{CB_SEL_ACC}:{session_key}:account:DANA"),
            ],
            [
                InlineKeyboardButton("🏦 Mandiri", callback_data=f"{CB_SEL_ACC}:{session_key}:account:Mandiri"),
                InlineKeyboardButton("📱 OVO", callback_data=f"{CB_SEL_ACC}:{session_key}:account:OVO"),
            ],
        ]

    rows.append([InlineKeyboardButton("❌ Batalkan", callback_data=f"{CB_CANCEL}:{session_key}")])
    return InlineKeyboardMarkup(rows)


def edit_menu_keyboard(session_key: str) -> InlineKeyboardMarkup:
    """Menu pilihan field yang ingin diedit."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📂 Ganti Kategori", callback_data=f"{CB_EDIT_FIELD}:{session_key}:category"),
            InlineKeyboardButton("💳 Ganti Akun",     callback_data=f"{CB_EDIT_FIELD}:{session_key}:account"),
        ],
        [
            InlineKeyboardButton("📅 Ganti Tanggal",  callback_data=f"{CB_EDIT_FIELD}:{session_key}:date"),
            InlineKeyboardButton("💰 Ganti Nominal",  callback_data=f"{CB_EDIT_FIELD}:{session_key}:amount"),
        ],
        [
            InlineKeyboardButton("⬅️ Kembali ke Konfirmasi", callback_data=f"show_confirm:{session_key}"),
        ]
    ])


def date_picker_keyboard(session_key: str) -> InlineKeyboardMarkup:
    """Keyboard pemilihan tanggal cepat."""
    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz)
    d0 = today.strftime("%Y-%m-%d")
    d1 = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    d2 = (today - timedelta(days=2)).strftime("%Y-%m-%d")
    d3 = (today - timedelta(days=3)).strftime("%Y-%m-%d")

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Hari Ini", callback_data=f"{CB_SEL_DATE}:{session_key}:{d0}"),
            InlineKeyboardButton("📅 Kemarin",  callback_data=f"{CB_SEL_DATE}:{session_key}:{d1}"),
        ],
        [
            InlineKeyboardButton("📅 2 Hari Lalu", callback_data=f"{CB_SEL_DATE}:{session_key}:{d2}"),
            InlineKeyboardButton("📅 3 Hari Lalu", callback_data=f"{CB_SEL_DATE}:{session_key}:{d3}"),
        ],
        [
            InlineKeyboardButton("⬅️ Kembali", callback_data=f"show_confirm:{session_key}"),
        ]
    ])


def category_picker_keyboard(session_key: str, categories: list[str]) -> InlineKeyboardMarkup:
    """Keyboard pemilihan kategori (2 kolom)."""
    rows = []
    for i in range(0, len(categories), 2):
        row = [
            InlineKeyboardButton(cat, callback_data=f"{CB_SEL_CAT}:{session_key}:{cat}")
            for cat in categories[i:i+2]
        ]
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Kembali", callback_data=f"show_confirm:{session_key}")])
    return InlineKeyboardMarkup(rows)


def report_period_keyboard() -> InlineKeyboardMarkup:
    """Keyboard pemilihan periode laporan keuangan."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Hari Ini",   callback_data="rep_period:today"),
            InlineKeyboardButton("📅 Minggu Ini", callback_data="rep_period:week"),
        ],
        [
            InlineKeyboardButton("📅 Bulan Ini",  callback_data="rep_period:month"),
            InlineKeyboardButton("📅 Tahun Ini",  callback_data="rep_period:year"),
        ],
        [
            InlineKeyboardButton("📈 Buka Grafik Visual", callback_data="chart_menu"),
        ]
    ])


def chart_selection_keyboard() -> InlineKeyboardMarkup:
    """Keyboard pemilihan jenis grafik visual."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🥧 Kategori Pengeluaran", callback_data="chart_gen:category"),
        ],
        [
            InlineKeyboardButton("📊 Pemasukan vs Pengeluaran", callback_data="chart_gen:in_vs_out"),
        ],
        [
            InlineKeyboardButton("📈 Tren Pengeluaran Bulanan", callback_data="chart_gen:trend"),
        ],
        [
            InlineKeyboardButton("⬅️ Kembali ke Laporan", callback_data="rep_period:month"),
        ]
    ])


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard menu utama (muncul di bawah chat)."""
    return ReplyKeyboardMarkup(
        [
            ["📊 Ringkasan", "💰 Saldo", "🎯 Anggaran"],
            ["➕ Pemasukan", "➖ Pengeluaran", "🔄 Transfer"],
            ["📋 Riwayat", "📈 Laporan"],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
