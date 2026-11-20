"""
tests/test_budget.py
Unit tests untuk budget_service (Phase 7 - Budgeting & Limits).
"""

from unittest.mock import patch, MagicMock

from services.budget_service import (
    match_category,
    generate_progress_bar,
    get_budget_overview,
    format_budget_message,
    set_category_budget,
)


class TestBudgetService:
    def test_match_category(self):
        assert match_category("makan") == "Makanan & Minuman"
        assert match_category("makanan") == "Makanan & Minuman"
        assert match_category("transport") == "Transportasi"
        assert match_category("ojol") == "Transportasi"
        assert match_category("belanja") == "Belanja"
        assert match_category("listrik") == "Tagihan & Utilitas"
        assert match_category("kategori_palsu_123") is None

    def test_generate_progress_bar(self):
        bar_0 = generate_progress_bar(0)
        assert bar_0 == "[░░░░░░░░░░]"

        bar_50 = generate_progress_bar(50)
        assert bar_50 == "[█████░░░░░]"

        bar_100 = generate_progress_bar(100)
        assert bar_100 == "[██████████]"

        bar_150 = generate_progress_bar(150)
        assert bar_150 == "[██████████]"

    @patch("services.budget_service.get_client")
    @patch("services.budget_service.get_financial_summary")
    def test_get_budget_overview(self, mock_summary, mock_get_client):
        mock_sheets = MagicMock()
        mock_sheets.get_budgets.return_value = [
            {"budget_id": "BGT-01", "month": "2026-11", "category": "Makanan & Minuman", "budget_amount": 2000000},
            {"budget_id": "BGT-02", "month": "2026-11", "category": "Transportasi", "budget_amount": 500000},
        ]
        mock_get_client.return_value = mock_sheets

        mock_summary.return_value = {
            "category_breakdown": [
                {"category": "Makanan & Minuman", "amount": 1500000.0, "percentage": 75.0},
                {"category": "Transportasi", "amount": 600000.0, "percentage": 25.0},
            ]
        }

        overview = get_budget_overview(month="2026-11")
        assert overview["has_budgets"] is True
        assert overview["total_budget"] == 2500000.0
        assert overview["total_spent"] == 2100000.0
        assert overview["total_remaining"] == 400000.0
        assert len(overview["items"]) == 2

        # Transportasi is over budget (600k / 500k = 120%)
        trans_item = next(it for it in overview["items"] if it["category"] == "Transportasi")
        assert trans_item["status"] == "exceeded"
        assert trans_item["percentage"] == 120.0

        # Makanan is 75% (ok)
        makan_item = next(it for it in overview["items"] if it["category"] == "Makanan & Minuman")
        assert makan_item["status"] == "ok"
        assert makan_item["percentage"] == 75.0

    def test_format_budget_message_empty(self):
        msg = format_budget_message({"month_label": "November 2026", "items": []})
        assert "Belum ada anggaran" in msg
        assert "/budget set" in msg

    def test_format_budget_message_populated(self):
        overview = {
            "month_label": "November 2026",
            "items": [
                {
                    "category": "Makanan & Minuman",
                    "budget": 2000000,
                    "spent": 1500000,
                    "percentage": 75.0,
                    "progress_bar": "[████████░░]",
                    "status_text": "🟢 Aman",
                }
            ],
            "total_budget": 2000000,
            "total_spent": 1500000,
            "total_remaining": 500000,
            "total_percentage": 75.0,
            "total_progress_bar": "[████████░░]",
            "has_budgets": True,
        }
        msg = format_budget_message(overview)
        assert "Pemantauan Anggaran" in msg
        assert "Makanan & Minuman" in msg
        assert "Aman" in msg
        assert "75.0%" in msg

    @patch("services.budget_service.get_client")
    def test_set_category_budget(self, mock_get_client):
        mock_sheets = MagicMock()
        mock_sheets.upsert_budget.return_value = True
        mock_get_client.return_value = mock_sheets

        ok, msg, data = set_category_budget("makan", 2000000, month="2026-11")
        assert ok is True
        assert data["category"] == "Makanan & Minuman"
        assert data["amount"] == 2000000

        # Invalid category
        ok, msg, _ = set_category_budget("kategori_salah_total", 50000)
        assert ok is False
        assert "tidak dikenali" in msg

        # Invalid amount
        ok, msg, _ = set_category_budget("makan", -100)
        assert ok is False
        assert "lebih besar dari 0" in msg

