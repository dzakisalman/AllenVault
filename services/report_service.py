"""
services/report_service.py
Business logic untuk analisis data keuangan dan pembuatan laporan.
Mendukung filter periode harian, mingguan, bulanan, tahunan, serta breakdown per kategori.
"""

import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

from config import TIMEZONE
from integrations.google_sheets import get_client
from utils.formatters import format_currency, format_date

logger = logging.getLogger(__name__)


def _parse_amount(val) -> float:
    """Helper konversi string/angka amount ke float (mendukung 'Rp21.999', '50.000', 50000, dll)."""
    try:
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        if s.endswith(",00") or s.endswith(".00"):
            s = s[:-3]
        cleaned = re.sub(r"[^\d]", "", s)
        return float(cleaned) if cleaned else 0.0
    except (ValueError, TypeError):
        return 0.0


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse format tanggal YYYY-MM-DD ke datetime."""
    try:
        return datetime.strptime(str(date_str).strip(), "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def get_financial_summary(period: str = "month", target_date: Optional[datetime] = None) -> dict:
    """
    Hitung ringkasan keuangan berdasarkan filter periode:
    - 'today': Hari ini
    - 'week': 7 hari terakhir / minggu berjalan (Senin - Minggu)
    - 'month': Bulan ini (default)
    - 'year': Tahun ini
    - 'all': Semua transaksi

    Return dict metrics lengkap.
    """
    tz = ZoneInfo(TIMEZONE)
    now = target_date or datetime.now(tz)
    now_date_str = now.strftime("%Y-%m-%d")
    current_month_str = now.strftime("%Y-%m")
    current_year_str = now.strftime("%Y")

    # Rentang minggu berjalan (Senin s/d Minggu)
    start_of_week = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)

    client = get_client()
    transactions = client.get_transactions(limit=1000, status="Confirmed")

    filtered_txs = []
    for tx in transactions:
        tx_date_str = str(tx.get("date", "")).strip()
        tx_dt = _parse_date(tx_date_str)
        if not tx_dt:
            continue

        if period == "today":
            if tx_date_str == now_date_str:
                filtered_txs.append(tx)
        elif period == "week":
            if start_of_week.date() <= tx_dt.date() <= end_of_week.date():
                filtered_txs.append(tx)
        elif period == "month":
            if tx_date_str.startswith(current_month_str):
                filtered_txs.append(tx)
        elif period == "year":
            if tx_date_str.startswith(current_year_str):
                filtered_txs.append(tx)
        elif period == "all":
            filtered_txs.append(tx)

    # Hitung agregasi
    total_income = 0.0
    total_expense = 0.0
    category_expenses = {}
    category_incomes = {}
    account_expenses = {}

    for tx in filtered_txs:
        amt = _parse_amount(tx.get("amount", 0))
        tx_type = tx.get("type", "Expense")
        cat = tx.get("category") or "Lain-lain"
        acc = tx.get("account") or "Cash"

        if tx_type == "Income":
            total_income += amt
            category_incomes[cat] = category_incomes.get(cat, 0.0) + amt
        elif tx_type == "Expense":
            total_expense += amt
            category_expenses[cat] = category_expenses.get(cat, 0.0) + amt
            account_expenses[acc] = account_expenses.get(acc, 0.0) + amt
        # Transfer tidak dihitung sebagai income/expense

    net_cashflow = total_income - total_expense

    # Urutkan kategori pengeluaran terbesar
    sorted_cat_expenses = sorted(category_expenses.items(), key=lambda x: x[1], reverse=True)
    cat_breakdown = []
    for cat_name, cat_total in sorted_cat_expenses:
        pct = (cat_total / total_expense * 100) if total_expense > 0 else 0
        cat_breakdown.append({
            "category": cat_name,
            "amount": cat_total,
            "percentage": round(pct, 1),
        })

    # Label nama periode dalam bahasa Indonesia
    period_labels = {
        "today": f"Hari Ini ({format_date(now_date_str)})",
        "week": f"Minggu Ini ({start_of_week.strftime('%d')} - {end_of_week.strftime('%d %b %Y')})",
        "month": f"Bulan Ini ({now.strftime('%B %Y')})",
        "year": f"Tahun Ini ({current_year_str})",
        "all": "Semua Waktu",
    }

    return {
        "period": period,
        "period_label": period_labels.get(period, period.title()),
        "total_income": total_income,
        "total_expense": total_expense,
        "net_cashflow": net_cashflow,
        "transaction_count": len(filtered_txs),
        "category_breakdown": cat_breakdown,
        "account_expenses": account_expenses,
        "raw_transactions": filtered_txs,
    }


def format_report_message(report: dict) -> str:
    """Format dictionary ringkasan keuangan menjadi pesan Telegram yang informatif dan elegan."""
    label = report.get("period_label", "Laporan Keuangan")
    income = report.get("total_income", 0.0)
    expense = report.get("total_expense", 0.0)
    net = report.get("net_cashflow", 0.0)
    count = report.get("transaction_count", 0)
    cats = report.get("category_breakdown", [])

    net_sign = "+" if net >= 0 else "-"
    net_status = "🟢 Surplus" if net >= 0 else "🔴 Defisit"

    lines = [
        f"📊 *Laporan Keuangan — {label}*\n",
        f"📥 *Total Pemasukan:* {format_currency(income)}",
        f"📤 *Total Pengeluaran:* {format_currency(expense)}",
        f"─────────────────────────",
        f"💵 *Net Cash Flow:* {net_sign}{format_currency(abs(net))} ({net_status})",
        f"🔢 *Jumlah Transaksi:* {count} transaksi\n",
    ]

    if cats:
        lines.append("📂 *Pengeluaran per Kategori:*")
        # Emoji kategori populer
        cat_emojis = {
            "Makanan & Minuman": "🍔",
            "Transportasi": "🚗",
            "Belanja": "🛍️",
            "Tagihan & Utilitas": "💡",
            "Kesehatan": "💊",
            "Hiburan": "🎬",
            "Investasi": "📈",
            "Pendidikan": "📚",
            "Perawatan Diri": "💈",
            "Rumah Tangga": "🏠",
            "Lain-lain": "📦",
        }
        for idx, item in enumerate(cats, 1):
            name = item["category"]
            amt = format_currency(item["amount"])
            pct = item["percentage"]
            emoji = cat_emojis.get(name, "🔹")
            lines.append(f"{idx}. {emoji} *{name}*: {amt} _({pct}%)_")
    else:
        lines.append("ℹ️ _Belum ada transaksi pengeluaran pada periode ini._")

    return "\n".join(lines)


def get_monthly_trend_data(months_count: int = 6) -> list[dict]:
    """
    Ambil perbandingan pemasukan vs pengeluaran per bulan selama N bulan terakhir.
    Berguna untuk generate grafik tren bulanan.
    """
    client = get_client()
    transactions = client.get_transactions(limit=1000, status="Confirmed")

    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)

    # Buat daftar bulan N terakhir (misal: ['2026-06', ..., '2026-11'])
    month_keys = []
    for i in range(months_count - 1, -1, -1):
        dt = (now.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        month_keys.append(dt.strftime("%Y-%m"))
    month_keys = sorted(list(set(month_keys)))[-months_count:]

    data = {m: {"month": m, "income": 0.0, "expense": 0.0} for m in month_keys}

    for tx in transactions:
        tx_date = str(tx.get("date", ""))[:7]  # YYYY-MM
        if tx_date in data:
            amt = _parse_amount(tx.get("amount", 0))
            t_type = tx.get("type", "Expense")
            if t_type == "Income":
                data[tx_date]["income"] += amt
            elif t_type == "Expense":
                data[tx_date]["expense"] += amt

    return [data[m] for m in month_keys]

