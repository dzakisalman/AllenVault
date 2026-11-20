"""
services/budget_service.py
Business logic untuk manajemen anggaran belanja (Budgeting) dan pemantauan batas pengeluaran.
Mendukung visualisasi progress bar dan peringatan over-budget.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from config import TIMEZONE, DEFAULT_EXPENSE_CATEGORIES
from integrations.google_sheets import get_client
from services.report_service import get_financial_summary, _parse_amount
from utils.formatters import format_currency

logger = logging.getLogger(__name__)


CATEGORY_ALIASES = {
    "makan": "Makanan & Minuman",
    "makanan": "Makanan & Minuman",
    "minum": "Makanan & Minuman",
    "f&b": "Makanan & Minuman",
    "food": "Makanan & Minuman",
    "transport": "Transportasi",
    "transportasi": "Transportasi",
    "ojol": "Transportasi",
    "bensin": "Transportasi",
    "belanja": "Belanja",
    "shopping": "Belanja",
    "tagihan": "Tagihan & Utilitas",
    "utilitas": "Tagihan & Utilitas",
    "listrik": "Tagihan & Utilitas",
    "air": "Tagihan & Utilitas",
    "wifi": "Tagihan & Utilitas",
    "pulsa": "Tagihan & Utilitas",
    "kesehatan": "Kesehatan",
    "obat": "Kesehatan",
    "dokter": "Kesehatan",
    "hiburan": "Hiburan",
    "nonton": "Hiburan",
    "game": "Hiburan",
    "pendidikan": "Pendidikan",
    "kursus": "Pendidikan",
    "buku": "Pendidikan",
    "perawatan": "Perawatan Diri",
    "skincare": "Perawatan Diri",
    "salon": "Perawatan Diri",
    "rumah": "Rumah Tangga",
    "kos": "Rumah Tangga",
    "kontrakan": "Rumah Tangga",
    "investasi": "Investasi",
    "lain": "Lain-lain",
    "lainnya": "Lain-lain",
}


def match_category(query: str) -> Optional[str]:
    """Cocokkan input pengguna ke kategori pengeluaran standar."""
    q = query.strip().lower()
    if q in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[q]

    for cat in DEFAULT_EXPENSE_CATEGORIES:
        if q == cat.lower() or q in cat.lower():
            return cat
    return None


def generate_progress_bar(percentage: float, length: int = 10) -> str:
    """Generate visual string progress bar [██████░░░░]."""
    filled_len = int(round(length * min(percentage, 100) / 100))
    bar = "█" * filled_len + "░" * (length - filled_len)
    return f"[{bar}]"


def get_budget_overview(month: Optional[str] = None) -> dict:
    """
    Hitung status anggaran vs realisasi pengeluaran untuk bulan tertentu (default: bulan ini).
    """
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    target_month = month or now.strftime("%Y-%m")

    # 1. Ambil data anggaran dari Google Sheets
    client = get_client()
    raw_budgets = client.get_budgets(month=target_month)

    budgets_map = {}
    for b in raw_budgets:
        cat = b.get("category")
        amt = _parse_amount(b.get("budget_amount", 0))
        if cat and amt > 0:
            budgets_map[cat] = amt

    # 2. Ambil realisasi pengeluaran bulan ini
    summary = get_financial_summary(period="month")
    actual_spent_map = {}
    for item in summary.get("category_breakdown", []):
        actual_spent_map[item["category"]] = item["amount"]

    # 3. Gabungkan anggaran dengan realisasi
    items = []
    total_budget = 0.0
    total_spent = 0.0

    for cat_name, budget_amt in budgets_map.items():
        spent = actual_spent_map.get(cat_name, 0.0)
        remaining = budget_amt - spent
        pct = (spent / budget_amt * 100) if budget_amt > 0 else 0.0

        if pct >= 100:
            status = "exceeded"
            status_text = "🔴 Over budget"
        elif pct >= 80:
            status = "warning"
            status_text = "🟡 Waspada"
        else:
            status = "ok"
            status_text = "🟢 Aman"

        items.append({
            "category": cat_name,
            "budget": budget_amt,
            "spent": spent,
            "remaining": remaining,
            "percentage": round(pct, 1),
            "progress_bar": generate_progress_bar(pct),
            "status": status,
            "status_text": status_text,
        })

        total_budget += budget_amt
        total_spent += spent

    # Urutkan berdasarkan persentase penggunaan tertinggi
    items.sort(key=lambda x: x["percentage"], reverse=True)

    total_remaining = total_budget - total_spent
    total_pct = (total_spent / total_budget * 100) if total_budget > 0 else 0.0

    month_dt = datetime.strptime(target_month, "%Y-%m")
    month_name = month_dt.strftime("%B %Y")

    return {
        "month": target_month,
        "month_label": month_name,
        "items": items,
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_remaining": total_remaining,
        "total_percentage": round(total_pct, 1),
        "total_progress_bar": generate_progress_bar(total_pct),
        "has_budgets": len(items) > 0,
    }


def format_budget_message(overview: dict) -> str:
    """Format dictionary anggaran menjadi pesan Telegram yang rapi."""
    month_label = overview.get("month_label", "Bulan Ini")
    items = overview.get("items", [])

    if not items:
        return (
            f"🎯 *Anggaran Keuangan — {month_label}*\n\n"
            f"ℹ️ Belum ada anggaran yang diatur untuk bulan ini.\n\n"
            f"💡 *Cara Mengatur Anggaran:*\n"
            f"Ketik: `/budget set <kategori> <nominal>`\n\n"
            f"*Contoh:*\n"
            f"• `/budget set makan 2jt`\n"
            f"• `/budget set transport 500rb`\n"
            f"• `/budget set belanja 1.5jt`"
        )

    lines = [
        f"🎯 *Pemantauan Anggaran — {month_label}*\n",
    ]

    for item in items:
        cat = item["category"]
        bar = item["progress_bar"]
        spent_str = format_currency(item["spent"])
        budget_str = format_currency(item["budget"])
        pct = item["percentage"]
        status = item["status_text"]

        lines.append(f"*{cat}* {status}")
        lines.append(f"{bar} *{pct}%*")
        lines.append(f"Terpakai: {spent_str} / {budget_str}\n")

    tot_spent = format_currency(overview["total_spent"])
    tot_bgt = format_currency(overview["total_budget"])
    tot_rem = format_currency(abs(overview["total_remaining"]))
    rem_sign = "Sisa" if overview["total_remaining"] >= 0 else "Defisit"
    tot_pct = overview["total_percentage"]
    tot_bar = overview["total_progress_bar"]

    lines.append("─────────────────────────")
    lines.append(f"📊 *Total Anggaran Keseluruhan:*")
    lines.append(f"{tot_bar} *{tot_pct}%*")
    lines.append(f"• Total Terpakai: *{tot_spent}* dari *{tot_bgt}*")
    lines.append(f"• {rem_sign}: *{tot_rem}*\n")
    lines.append("💡 _Gunakan `/budget set <kategori> <nominal>` untuk menambah atau mengubah anggaran._")

    return "\n".join(lines)


def set_category_budget(category_query: str, amount_val: float, month: Optional[str] = None) -> tuple[bool, str, dict]:
    """
    Atur nominal anggaran untuk kategori tertentu.
    """
    matched_cat = match_category(category_query)
    if not matched_cat:
        return (
            False,
            f"Kategori '{category_query}' tidak dikenali. Pilih salah satu dari: {', '.join(DEFAULT_EXPENSE_CATEGORIES)}",
            {},
        )

    if amount_val <= 0:
        return False, "Nominal anggaran harus lebih besar dari 0.", {}

    tz = ZoneInfo(TIMEZONE)
    target_month = month or datetime.now(tz).strftime("%Y-%m")

    client = get_client()
    ok = client.upsert_budget(target_month, matched_cat, amount_val)
    if ok:
        return (
            True,
            f"✅ Anggaran *{matched_cat}* untuk bulan *{target_month}* berhasil diatur ke *{format_currency(amount_val)}*.",
            {"category": matched_cat, "amount": amount_val, "month": target_month},
        )
    return False, "⚠️ Gagal menyimpan anggaran ke Google Sheets.", {}

