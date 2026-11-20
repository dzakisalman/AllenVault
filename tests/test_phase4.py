"""
Tests — Phase 4: Receipt Scanner & Receipt Items
Jalankan dengan: python -m pytest tests/test_phase4.py -v
"""

import pytest
import uuid
from services.receipt_service import (
    format_receipt_preview,
    _clean_json_response,
)
from utils.formatters import format_currency


class TestPhase4Receipt:
    def test_clean_json_response(self):
        raw = "```json\n{\"merchant\": \"Indomaret\", \"total_amount\": 85000}\n```"
        cleaned = _clean_json_response(raw)
        assert cleaned.startswith("{")
        assert cleaned.endswith("}")
        assert "```" not in cleaned

    def test_format_receipt_preview(self):
        data = {
            "merchant": "Indomaret",
            "date": "2026-11-19",
            "total_amount": 85000,
            "category": "Belanja",
            "account": "BCA",
            "items": [
                {"item_name": "Air Mineral", "quantity": 2, "unit_price": 5000, "subtotal": 10000},
                {"item_name": "Roti Tawar", "quantity": 1, "unit_price": 15000, "subtotal": 15000},
                {"item_name": "Deterjen", "quantity": 1, "unit_price": 60000, "subtotal": 60000},
            ]
        }
        preview = format_receipt_preview(data)
        assert "Indomaret" in preview
        assert "Rp85.000" in preview
        assert "Air Mineral (2x)" in preview
        assert "Deterjen (1x)" in preview
        assert "BCA" in preview

