"""
Tests — Phase 3: Transaction management, advanced parser, sessions, and balance logic.
Jalankan dengan: python -m pytest tests/test_phase3.py -v
"""

import pytest
import uuid
from utils.parser import (
    parse_amount,
    detect_transaction_type,
    detect_category,
    detect_account,
    detect_transfer_accounts,
    clean_description,
    parse_transaction_text,
)
from utils.formatters import (
    format_currency,
    format_confirmed_receipt,
    format_balance_overview,
    format_history_list,
)
from database.db import (
    init_db,
    save_confirmation_session,
    get_confirmation_session,
    update_confirmation_session,
    delete_confirmation_session,
    save_pending_transaction,
    get_pending_transactions,
    mark_transaction_synced,
)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


class TestPhase3Parser:
    def test_parse_bakmi_gm(self):
        text = "bakmi gm 50rb"
        res = parse_transaction_text(text)
        assert res["type"] == "Expense"
        assert res["amount"] == 50_000.0
        assert res["category"] == "Makanan & Minuman"
        assert res["merchant"] == "Bakmi GM"

    def test_parse_kopi_cash(self):
        text = "kopi 18k cash"
        res = parse_transaction_text(text)
        assert res["type"] == "Expense"
        assert res["amount"] == 18_000.0
        assert res["account"] == "Cash"
        assert res["category"] == "Makanan & Minuman"

    def test_parse_income_freelance(self):
        text = "dapat uang freelance 500 ribu masuk ke Mandiri"
        res = parse_transaction_text(text)
        assert res["type"] == "Income"
        assert res["amount"] == 500_000.0
        assert res["account"] == "Mandiri"
        assert res["category"] == "Freelance"

    def test_parse_transfer(self):
        text = "transfer 200 ribu dari BCA ke DANA"
        res = parse_transaction_text(text)
        assert res["type"] == "Transfer"
        assert res["amount"] == 200_000.0
        assert res["from_account"] == "BCA"
        assert res["to_account"] == "DANA"

    def test_parse_expense_with_bank(self):
        text = "beli makan 25 ribu pakai BCA"
        res = parse_transaction_text(text)
        assert res["type"] == "Expense"
        assert res["amount"] == 25_000.0
        assert res["account"] == "BCA"
        assert res["category"] == "Makanan & Minuman"

    def test_detect_transfer_accounts(self):
        from_acc, to_acc = detect_transfer_accounts("tf 50k dari GoPay ke BCA")
        assert from_acc == "GoPay"
        assert to_acc == "BCA"

    def test_clean_description(self):
        desc = clean_description("beli makan siang 25rb pakai BCA")
        assert "25rb" not in desc
        assert "BCA" not in desc


class TestConfirmationSessions:
    def test_session_lifecycle(self):
        user_id = 99999
        key = f"test_{uuid.uuid4().hex[:6]}"
        data = {"amount": 50000, "description": "Bakmi GM", "type": "Expense"}

        # 1. Simpan
        assert save_confirmation_session(user_id, key, data) is True

        # 2. Ambil
        fetched = get_confirmation_session(key)
        assert fetched is not None
        assert fetched["amount"] == 50000
        assert fetched["description"] == "Bakmi GM"

        # 3. Update
        data["amount"] = 60000
        assert update_confirmation_session(key, data) is True
        updated = get_confirmation_session(key)
        assert updated["amount"] == 60000

        # 4. Hapus
        assert delete_confirmation_session(key) is True
        assert get_confirmation_session(key) is None


class TestPendingTransactions:
    def test_pending_queue(self):
        tx_id = f"PENDING-{uuid.uuid4().hex[:6]}"
        data = {"transaction_id": tx_id, "amount": 25000, "status": "Confirmed"}

        assert save_pending_transaction(tx_id, data) is True
        pending_list = get_pending_transactions()
        matching = [t for t in pending_list if t.get("transaction_id") == tx_id]
        assert len(matching) == 1
        assert matching[0]["amount"] == 25000

        assert mark_transaction_synced(tx_id) is True
        pending_list_after = get_pending_transactions()
        assert not any(t.get("transaction_id") == tx_id for t in pending_list_after)


class TestFormattersPhase3:
    def test_format_confirmed_receipt(self):
        tx = {
            "type": "Expense",
            "amount": 50000,
            "category": "Makanan & Minuman",
            "account": "BCA",
            "description": "Bakmi GM",
        }
        balances = {"BCA": 950000}
        receipt = format_confirmed_receipt(tx, balances)
        assert "Bakmi GM" in receipt
        assert "Rp50.000" in receipt
        assert "Rp950.000" in receipt

    def test_format_balance_overview(self):
        balances = [
            {"account_name": "BCA", "account_type": "Bank", "balance": 1000000},
            {"account_name": "Cash", "account_type": "Cash", "balance": 250000},
        ]
        text = format_balance_overview(balances)
        assert "Rp1.000.000" in text
        assert "Rp250.000" in text
        assert "Rp1.250.000" in text  # Total

