"""
Utils — Formatters
Fungsi-fungsi untuk memformat data ke tampilan yang ramah pengguna.
"""

from datetime import datetime


def format_currency(amount: float, prefix: str = "Rp") -> str:
    """Format angka menjadi format mata uang Indonesia."""
    try:
        val = float(amount)
        return f"{prefix}{val:,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return f"{prefix}0"


def format_date(date_str: str, fmt_in: str = "%Y-%m-%d", fmt_out: str = "%d %B %Y") -> str:
    """
    Konversi format tanggal.
    Default: '2026-11-19' → '19 November 2026'
    """
    MONTHS_ID = {
        "January": "Januari", "February": "Februari", "March": "Maret",
        "April": "April", "May": "Mei", "June": "Juni",
        "July": "Juli", "August": "Agustus", "September": "September",
        "October": "Oktober", "November": "November", "December": "Desember",
    }
    try:
        dt = datetime.strptime(str(date_str).strip(), fmt_in)
        result = dt.strftime(fmt_out)
        for en, id_ in MONTHS_ID.items():
            result = result.replace(en, id_)
        return result
    except (ValueError, TypeError):
        return str(date_str)


def format_transaction_preview(tx: dict) -> str:
    """
    Format preview transaksi untuk pesan konfirmasi.
    Mengembalikan string siap kirim ke Telegram (Markdown).
    """
    tx_type = tx.get("type", "Expense")
    type_emoji = {"Income": "📥", "Expense": "📤", "Transfer": "🔄"}.get(tx_type, "💳")

    amount = format_currency(tx.get("amount", 0))
    date_display = format_date(tx.get("date", ""))

    lines = [
        f"{type_emoji} *Transaksi Terdeteksi*\n",
        f"• *Tipe:* {tx_type}",
        f"• *Nominal:* {amount}",
    ]

    if tx_type == "Transfer":
        lines.append(f"• *Dari Akun:* {tx.get('from_account') or '_(Belum dipilih)_'}")
        lines.append(f"• *Ke Akun:* {tx.get('to_account') or '_(Belum dipilih)_'}")
    else:
        lines.append(f"• *Kategori:* {tx.get('category') or 'Lain-lain'}")
        lines.append(f"• *Akun:* {tx.get('account') or '_(Belum dipilih)_'}")
        if tx.get("merchant"):
            lines.append(f"• *Merchant:* {tx.get('merchant')}")

    if tx.get("description"):
        lines.append(f"• *Keterangan:* {tx.get('description')}")
    lines.append(f"• *Tanggal:* {date_display}")

    return "\n".join(lines)


def format_confirmed_receipt(tx: dict, account_balances: dict = None) -> str:
    """Format struk transaksi yang berhasil disimpan."""
    tx_type = tx.get("type", "Expense")
    type_emoji = {"Income": "📥", "Expense": "📤", "Transfer": "🔄"}.get(tx_type, "💳")
    amount = format_currency(tx.get("amount", 0))

    lines = [
        "✅ *Transaksi Berhasil Disimpan!*\n",
        f"{type_emoji} *{tx_type}*: {amount}",
    ]

    if tx_type == "Transfer":
        lines.append(f"• Dari: *{tx.get('from_account', '-')}*")
        lines.append(f"• Ke: *{tx.get('to_account', '-')}*")
    else:
        lines.append(f"• Kategori: {tx.get('category', 'Lain-lain')}")
        lines.append(f"• Akun: {tx.get('account', '-')}")

    if tx.get("description"):
        lines.append(f"• Keterangan: {tx.get('description')}")

    # Tampilkan saldo akun terkini jika tersedia
    if account_balances:
        lines.append("\n💰 *Saldo Terkini:*")
        for acc_name, bal in account_balances.items():
            lines.append(f"• {acc_name}: {format_currency(bal)}")

    return "\n".join(lines)


def format_balance_overview(balances: list[dict]) -> str:
    """Format daftar saldo semua akun."""
    if not balances:
        return (
            "💰 *Informasi Saldo*\n\n"
            "Belum ada akun terdaftar.\n"
            "Gunakan `/addaccount <Nama Akun> <Tipe> <Saldo Awal>` untuk menambah akun baru.\n"
            "Contoh: `/addaccount BCA Bank 1000000`"
        )

    total_balance = sum(b.get("balance", 0.0) for b in balances)
    lines = ["💰 *Saldo Akun Keuangan*\n"]

    for b in balances:
        name = b.get("account_name", "-")
        acc_type = b.get("account_type", "")
        bal = b.get("balance", 0.0)
        emoji = {"Bank": "🏦", "E-Wallet": "📱", "Cash": "💵"}.get(acc_type, "💳")
        lines.append(f"{emoji} *{name}*: {format_currency(bal)}")

    lines.append("\n" + "─" * 25)
    lines.append(f"💵 *Total Kekayaan:* {format_currency(total_balance)}")
    return "\n".join(lines)


def format_history_list(transactions: list[dict]) -> str:
    """Format daftar riwayat transaksi terakhir."""
    if not transactions:
        return "📋 *Riwayat Transaksi*\n\nBelum ada riwayat transaksi yang tercatat."

    lines = ["📋 *Riwayat Transaksi Terakhir*\n"]
    for tx in transactions:
        tx_type = tx.get("type", "Expense")
        emoji = {"Income": "🟢", "Expense": "🔴", "Transfer": "🔵"}.get(tx_type, "⚪")
        amount = format_currency(tx.get("amount", 0))
        date = tx.get("date", "")
        desc = tx.get("description") or tx.get("category") or tx_type
        acc = tx.get("account") or f"{tx.get('from_account')} → {tx.get('to_account')}"
        lines.append(f"{emoji} *{amount}* — {desc}")
        lines.append(f"   _{date} • {acc}_\n")

    return "\n".join(lines)


def format_batch_preview(transactions: list[dict]) -> str:
    """Format preview untuk beberapa transaksi sekaligus (Batch)."""
    count = len(transactions)
    total_amount = sum(float(tx.get("amount", 0)) for tx in transactions)

    lines = [f"📋 *{count} Transaksi Terdeteksi (Batch)*\n"]
    for idx, tx in enumerate(transactions, 1):
        tx_type = tx.get("type", "Expense")
        emoji = {"Income": "📥", "Expense": "📤", "Transfer": "🔄"}.get(tx_type, "💳")
        amount = format_currency(tx.get("amount", 0))
        desc = tx.get("description") or tx.get("category") or "Transaksi"
        acc = tx.get("account") or (f"{tx.get('from_account')} → {tx.get('to_account')}" if tx_type == "Transfer" else "Cash")
        cat = tx.get("category") or "Lain-lain"
        date_str = format_date(tx.get("date", ""))

        lines.append(f"{idx}. {emoji} *{desc}* — {amount}")
        lines.append(f"   • _{cat} • {acc} • {date_str}_\n")

    lines.append("─" * 25)
    lines.append(f"💵 *Total Transaksi:* {format_currency(total_amount)}")
    return "\n".join(lines)
