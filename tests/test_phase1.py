"""
Tests — Phase 1: Unit tests untuk utils dan config.
Jalankan dengan: python -m pytest tests/ -v
"""

import pytest
from utils.parser import parse_amount, detect_transaction_type, parse_transaction_text
from utils.formatters import format_currency, format_date, format_transaction_preview
from utils.validators import is_valid_amount, is_valid_date, sanitize_text, is_duplicate_transaction


class TestParser:
    def test_parse_amount_ribu(self):
        assert parse_amount("25 ribu") == 25_000.0

    def test_parse_amount_juta(self):
        assert parse_amount("1.5 juta") == 1_500_000.0

    def test_parse_amount_rb(self):
        assert parse_amount("150rb") == 150_000.0

    def test_parse_amount_rp(self):
        assert parse_amount("Rp85.000") == 85_000.0

    def test_parse_amount_k(self):
        assert parse_amount("18k") == 18_000.0

    def test_parse_amount_none(self):
        assert parse_amount("tidak ada angka") is None

    def test_detect_expense(self):
        assert detect_transaction_type("beli makan siang") == "Expense"

    def test_detect_income(self):
        assert detect_transaction_type("dapat gaji bulan ini") == "Income"

    def test_detect_transfer(self):
        assert detect_transaction_type("transfer ke DANA") == "Transfer"

    def test_detect_none(self):
        assert detect_transaction_type("halo bot") is None

    def test_parse_transaction_expense(self):
        result = parse_transaction_text("beli kopi 18 ribu")
        assert result["type"] == "Expense"
        assert result["amount"] == 18_000.0
        assert result["source"] == "Text"

    def test_parse_transaction_income(self):
        result = parse_transaction_text("dapat gaji 3 juta masuk Mandiri")
        assert result["type"] == "Income"
        assert result["amount"] == 3_000_000.0


class TestFormatters:
    def test_format_currency_basic(self):
        assert format_currency(25000) == "Rp25.000"

    def test_format_currency_million(self):
        assert format_currency(1_500_000) == "Rp1.500.000"

    def test_format_currency_zero(self):
        assert format_currency(0) == "Rp0"

    def test_format_date(self):
        result = format_date("2026-11-19")
        assert "November" in result or "19" in result

    def test_format_transaction_preview_expense(self):
        tx = {
            "type": "Expense",
            "amount": 25000,
            "category": "Makanan",
            "account": "BCA",
            "date": "2026-11-19",
        }
        preview = format_transaction_preview(tx)
        assert "Expense" in preview
        assert "25.000" in preview


class TestValidators:
    def test_valid_amount(self):
        assert is_valid_amount(25000) is True
        assert is_valid_amount(0) is False
        assert is_valid_amount(-100) is False
        assert is_valid_amount("abc") is False

    def test_valid_date(self):
        assert is_valid_date("2026-11-19") is True
        assert is_valid_date("19-11-2026") is False
        assert is_valid_date("not-a-date") is False

    def test_sanitize_text(self):
        assert sanitize_text("  Hello  ") == "Hello"
        assert len(sanitize_text("x" * 1000, max_length=10)) == 10

    def test_duplicate_detection_same(self):
        existing = [{
            "type": "Expense", "amount": "25000",
            "account": "BCA", "date": "2026-11-19", "time": "10:00:00"
        }]
        new_tx = {
            "type": "Expense", "amount": 25000,
            "account": "BCA", "date": "2026-11-19", "time": "10:00:30"
        }
        assert is_duplicate_transaction(existing, new_tx) is True

    def test_duplicate_detection_different_amount(self):
        existing = [{
            "type": "Expense", "amount": "25000",
            "account": "BCA", "date": "2026-11-19", "time": "10:00:00"
        }]
        new_tx = {
            "type": "Expense", "amount": 30000,
            "account": "BCA", "date": "2026-11-19", "time": "10:00:00"
        }
        assert is_duplicate_transaction(existing, new_tx) is False

