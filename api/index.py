"""
api/index.py
FastAPI Serverless Backend untuk AllenVault Web Dashboard.
Siap di-deploy ke Vercel atau dijalankan secara lokal dengan Uvicorn.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

# Pastikan root direktori ada di sys.path agar modul project bisa di-import
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import config
from integrations.google_sheets import get_client
from services.report_service import get_financial_summary, get_monthly_trend_data, _parse_amount
from services.account_service import get_all_balances
from services.budget_service import get_budget_overview

app = FastAPI(
    title="AllenVault Dashboard API",
    description="Backend API untuk Web Dashboard AllenVault Personal Finance",
    version="1.0.0",
)

# Enable CORS agar frontend bisa fetch tanpa kendala
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    """Health check dan status koneksi spreadsheet."""
    sheets = get_client()
    return {
        "status": "healthy",
        "sheets_connected": sheets.is_connected(),
        "timestamp": datetime.now(ZoneInfo(config.TIMEZONE)).isoformat(),
        "version": "1.0.0",
    }


@app.get("/api/overview")
def get_overview(
    period: str = Query(default="month", description="today | week | month | year | all"),
    refresh: bool = Query(default=False),
):
    """
    Mengambil data ringkasan keuangan lengkap untuk dashboard:
    - Ringkasan periode (Income, Expense, Net Cashflow, Category Breakdown)
    - Saldo semua akun
    - Tren 6 bulan terakhir
    - Status anggaran (budgets)
    """
    try:
        client = get_client()
        if refresh:
            client._cache.clear()
            client._cache_time.clear()

        # 1. Ringkasan keuangan
        summary = get_financial_summary(period=period)
        
        # 2. Saldo akun
        raw_accounts = get_all_balances()
        total_balance = sum(float(a.get("balance", 0.0)) for a in raw_accounts)
        accounts_data = {
            "total_balance": total_balance,
            "accounts": raw_accounts,
        }
        
        # 3. Tren 6 bulan terakhir
        trend_data = get_monthly_trend_data(months_count=6)
        
        # 4. Status anggaran bulan ini
        budget_data = get_budget_overview()

        return {
            "period": period,
            "summary": summary,
            "accounts": accounts_data,
            "trend": trend_data,
            "budgets": budget_data,
        }
    except Exception as e:
        logger.error(f"Gagal overview: {e}")
        # Jangan lempar 500 jika ada cache atau error 429
        raise HTTPException(status_code=500, detail=f"Gagal mengambil overview data: {str(e)}")


@app.get("/api/transactions")
def get_transactions(
    limit: int = Query(default=100, le=500),
    category: Optional[str] = None,
    tx_type: Optional[str] = None,
    search: Optional[str] = None,
    refresh: bool = Query(default=False),
):
    """
    Mengambil daftar transaksi terbaru dari Google Sheets dengan filter opsional.
    """
    try:
        sheets = get_client()
        if refresh:
            sheets._cache.clear()
            sheets._cache_time.clear()
        txs = sheets.get_transactions(limit=limit, status="Confirmed")
        
        # Urutkan terbaru di atas (reverse)
        results = list(reversed(txs))

        # Normalisasi amount jadi float numerik
        for t in results:
            t["amount_raw"] = t.get("amount")
            t["amount"] = _parse_amount(t.get("amount", 0))

        if tx_type:
            results = [t for t in results if str(t.get("type", "")).lower() == tx_type.lower()]
            
        if category:
            results = [t for t in results if str(t.get("category", "")).lower() == category.lower()]
            
        if search:
            q = search.lower().strip()
            results = [
                t for t in results
                if q in str(t.get("description", "")).lower()
                or q in str(t.get("merchant", "")).lower()
                or q in str(t.get("category", "")).lower()
                or q in str(t.get("account", "")).lower()
            ]

        return {
            "count": len(results),
            "transactions": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil transaksi: {str(e)}")


@app.get("/api/accounts")
def get_accounts():
    """Mengambil daftar akun dan saldo terkini."""
    try:
        return get_all_balances()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil akun: {str(e)}")


@app.get("/api/budgets")
def get_budgets(month: Optional[str] = None):
    """Mengambil status anggaran kategori vs pengeluaran aktual."""
    try:
        return get_budget_overview(month=month)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil budgets: {str(e)}")


# ─── Static files serving untuk Local Development ─────────────
PUBLIC_DIR = ROOT_DIR / "public"
if PUBLIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(PUBLIC_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        index_file = PUBLIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "AllenVault Dashboard API is running. Public index.html not found."}

