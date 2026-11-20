"""
tests/test_reports_charts.py
Unit tests untuk report_service dan chart_service (Phase 5 & 6).
"""

from unittest.mock import patch, MagicMock
from datetime import datetime

from services.report_service import (
    _parse_amount,
    _parse_date,
    get_financial_summary,
    format_report_message,
    get_monthly_trend_data,
)
from services.chart_service import (
    generate_category_pie_chart,
    generate_income_vs_expense_chart,
    generate_monthly_trend_chart,
)


class TestReportService:
    def test_parse_amount(self):
        assert _parse_amount(50000) == 50000.0
        assert _parse_amount("50.000") == 50000.0
        assert _parse_amount("50,000") == 50000.0
        assert _parse_amount("invalid") == 0.0
        assert _parse_amount(None) == 0.0

    def test_parse_date(self):
        dt = _parse_date("2026-11-19")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 11
        assert dt.day == 19
        assert _parse_date("invalid-date") is None

    @patch("services.report_service.get_client")
    def test_get_financial_summary(self, mock_get_client):
        mock_sheets = MagicMock()
        mock_sheets.get_transactions.return_value = [
            {"date": "2026-11-19", "type": "Expense", "amount": 25000, "category": "Makanan & Minuman", "account": "BCA"},
            {"date": "2026-11-19", "type": "Expense", "amount": 15000, "category": "Transportasi", "account": "GoPay"},
            {"date": "2026-11-19", "type": "Income", "amount": 100000, "category": "Gaji", "account": "BCA"},
            {"date": "2026-11-18", "type": "Expense", "amount": 30000, "category": "Makanan & Minuman", "account": "Cash"},
        ]
        mock_get_client.return_value = mock_sheets

        ref_date = datetime(2026, 11, 19, 12, 0, 0)

        # Test today
        summary_today = get_financial_summary(period="today", target_date=ref_date)
        assert summary_today["total_income"] == 100000.0
        assert summary_today["total_expense"] == 40000.0
        assert summary_today["net_cashflow"] == 60000.0
        assert summary_today["transaction_count"] == 3

        # Test month
        summary_month = get_financial_summary(period="month", target_date=ref_date)
        assert summary_month["total_income"] == 100000.0
        assert summary_month["total_expense"] == 70000.0
        assert summary_month["net_cashflow"] == 30000.0
        assert len(summary_month["category_breakdown"]) == 2

    def test_format_report_message(self):
        report = {
            "period_label": "Bulan Ini (November 2026)",
            "total_income": 5000000.0,
            "total_expense": 2000000.0,
            "net_cashflow": 3000000.0,
            "transaction_count": 5,
            "category_breakdown": [
                {"category": "Makanan & Minuman", "amount": 1200000.0, "percentage": 60.0},
                {"category": "Transportasi", "amount": 800000.0, "percentage": 40.0},
            ],
        }
        msg = format_report_message(report)
        assert "Laporan Keuangan" in msg
        assert "Total Pemasukan" in msg
        assert "Surplus" in msg
        assert "Makanan & Minuman" in msg


class TestChartService:
    def test_generate_category_pie_chart(self):
        categories = [
            {"category": "Makanan & Minuman", "amount": 50000, "percentage": 50.0},
            {"category": "Transportasi", "amount": 30000, "percentage": 30.0},
            {"category": "Belanja", "amount": 20000, "percentage": 20.0},
        ]
        png_bytes = generate_category_pie_chart(categories, period_title="Uji Coba")
        assert png_bytes is not None
        assert png_bytes.startswith(b"\x89PNG")

    def test_generate_category_pie_chart_empty(self):
        assert generate_category_pie_chart([]) is None
        assert generate_category_pie_chart([{"category": "Test", "amount": 0}]) is None

    def test_generate_income_vs_expense_chart(self):
        data = [
            {"month": "2026-09", "income": 5000000, "expense": 3000000},
            {"month": "2026-10", "income": 5000000, "expense": 3500000},
            {"month": "2026-11", "income": 6000000, "expense": 2500000},
        ]
        png_bytes = generate_income_vs_expense_chart(data)
        assert png_bytes is not None
        assert png_bytes.startswith(b"\x89PNG")

    def test_generate_income_vs_expense_chart_empty(self):
        assert generate_income_vs_expense_chart([]) is None
        assert generate_income_vs_expense_chart([{"month": "2026-11", "income": 0, "expense": 0}]) is None

    def test_generate_monthly_trend_chart(self):
        data = [
            {"month": "2026-09", "income": 5000000, "expense": 3000000},
            {"month": "2026-10", "income": 5000000, "expense": 3500000},
            {"month": "2026-11", "income": 6000000, "expense": 2500000},
        ]
        png_bytes = generate_monthly_trend_chart(data)
        assert png_bytes is not None
        assert png_bytes.startswith(b"\x89PNG")

