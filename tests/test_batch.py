"""
Tests — Batch Transaction Input
Jalankan dengan: python -m pytest tests/test_batch.py -v
"""

import pytest
import uuid
from utils.formatters import format_batch_preview, format_currency
from database.db import (
    init_db,
    save_confirmation_session,
    get_confirmation_session,
    delete_confirmation_session,
)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


class TestBatchTransactions:
    def test_format_batch_preview(self):
        txs = [
            {
                "type": "Expense",
                "amount": 20000,
                "description": "Soto",
                "account": "ShopeePay",
                "category": "Makanan & Minuman",
                "date": "2026-11-18",
            },
            {
                "type": "Expense",
                "amount": 15000,
                "description": "Bakso",
                "account": "ShopeePay",
                "category": "Makanan & Minuman",
                "date": "2026-11-18",
            },
            {
                "type": "Expense",
                "amount": 60000,
                "description": "Celana",
                "account": "Mandiri",
                "category": "Belanja",
                "date": "2026-11-18",
            },
        ]

        preview = format_batch_preview(txs)
        assert "3 Transaksi Terdeteksi (Batch)" in preview
        assert "Soto" in preview
        assert "Rp20.000" in preview
        assert "Bakso" in preview
        assert "Rp15.000" in preview
        assert "Celana" in preview
        assert "Rp60.000" in preview
        assert "Rp95.000" in preview  # Total
        assert "ShopeePay" in preview
        assert "Mandiri" in preview

    def test_batch_session_lifecycle(self):
        user_id = 12345
        session_key = f"batch_{uuid.uuid4().hex[:6]}"
        data = {
            "transactions": [
                {"amount": 20000, "description": "Soto", "type": "Expense"},
                {"amount": 15000, "description": "Bakso", "type": "Expense"},
            ]
        }

        # 1. Simpan sesi batch
        assert save_confirmation_session(user_id, session_key, data, session_type="batch") is True

        # 2. Ambil sesi batch
        fetched = get_confirmation_session(session_key)
        assert fetched is not None
        assert fetched.get("_session_type") == "batch"
        assert len(fetched["transactions"]) == 2
        assert fetched["transactions"][0]["amount"] == 20000

        # 3. Hapus sesi batch
        assert delete_confirmation_session(session_key) is True
        assert get_confirmation_session(session_key) is None

