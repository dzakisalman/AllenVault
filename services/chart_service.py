"""
services/chart_service.py
Pembuatan visualisasi grafik keuangan menggunakan Matplotlib.
Grafik di-render ke bytes buffer (PNG) beresolusi tinggi untuk dikirim langsung via Telegram.
"""

import io
import logging
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # Mode headless tanpa GUI
import matplotlib.pyplot as plt
import numpy as np

from utils.formatters import format_currency

logger = logging.getLogger(__name__)

# Warna palet modern & kontras
PALETTE_COLORS = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
]


def generate_category_pie_chart(category_breakdown: list[dict], period_title: str = "Bulan Ini") -> Optional[bytes]:
    """
    Generate Donut Chart pengeluaran per kategori.
    Return PNG bytes atau None jika tidak ada data pengeluaran.
    """
    if not category_breakdown:
        return None

    # Ambil maksimal 7 kategori teratas, sisanya gabungkan ke 'Lainnya' jika banyak
    labels = []
    sizes = []
    amounts = []

    top_n = category_breakdown[:6]
    other = category_breakdown[6:]

    for item in top_n:
        labels.append(item["category"])
        sizes.append(item["amount"])
        amounts.append(item["amount"])

    if other:
        other_total = sum(it["amount"] for it in other)
        labels.append("Lainnya")
        sizes.append(other_total)
        amounts.append(other_total)

    total_expense = sum(sizes)
    if total_expense <= 0:
        return None

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)

    # Donut Chart
    colors = PALETTE_COLORS[:len(labels)]
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct=lambda pct: f"{pct:.1f}%" if pct > 4 else "",
        pctdistance=0.75,
        startangle=140,
        colors=colors,
        wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
    )

    for at in autotexts:
        at.set_fontsize(10)
        at.set_weight("bold")
        at.set_color("#333333")

    for t in texts:
        t.set_fontsize(10)

    # Judul dan total di tengah donut
    ax.text(
        0, 0,
        f"Total\n{format_currency(total_expense)}",
        ha="center", va="center",
        fontsize=12, fontweight="bold",
        color="#2C3E50"
    )

    ax.set_title(
        f"Pengeluaran Berdasarkan Kategori — {period_title}",
        fontsize=13, fontweight="bold", pad=20, color="#1A252C"
    )

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_income_vs_expense_chart(monthly_data: list[dict]) -> Optional[bytes]:
    """
    Generate Bar Chart perbandingan Pemasukan vs Pengeluaran per bulan.
    """
    if not monthly_data:
        return None

    months = [item["month"] for item in monthly_data]
    incomes = [item["income"] for item in monthly_data]
    expenses = [item["expense"] for item in monthly_data]

    if sum(incomes) == 0 and sum(expenses) == 0:
        return None

    x = np.arange(len(months))
    width = 0.35

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)

    rects1 = ax.bar(x - width/2, incomes, width, label="Pemasukan", color="#2ECC71", edgecolor="white")
    rects2 = ax.bar(x + width/2, expenses, width, label="Pengeluaran", color="#E74C3C", edgecolor="white")

    ax.set_xlabel("Periode Bulan", fontsize=11, fontweight="bold", labelpad=10)
    ax.set_ylabel("Nominal (Rp)", fontsize=11, fontweight="bold", labelpad=10)
    ax.set_title("Pemasukan vs Pengeluaran Bulanan", fontsize=13, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(months, fontsize=10)
    ax.legend(frameon=True, facecolor="white", edgecolor="#DDDDDD")

    # Format y-axis dengan pemisah ribuan
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{int(x):,}"))

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_monthly_trend_chart(monthly_data: list[dict]) -> Optional[bytes]:
    """
    Generate Line Chart tren pengeluaran bulanan.
    """
    if not monthly_data:
        return None

    months = [item["month"] for item in monthly_data]
    expenses = [item["expense"] for item in monthly_data]

    if sum(expenses) == 0:
        return None

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)

    ax.plot(months, expenses, marker="o", linewidth=2.5, color="#E67E22", markersize=7, label="Pengeluaran")

    # Label angka di setiap titik
    for i, txt in enumerate(expenses):
        if txt > 0:
            ax.annotate(
                format_currency(txt),
                (months[i], expenses[i]),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=9,
                fontweight="bold",
            )

    ax.set_xlabel("Bulan", fontsize=11, fontweight="bold", labelpad=10)
    ax.set_ylabel("Total Pengeluaran (Rp)", fontsize=11, fontweight="bold", labelpad=10)
    ax.set_title("Tren Pengeluaran Bulanan", fontsize=13, fontweight="bold", pad=15)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{int(x):,}"))

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

