"""
Handlers module — Telegram command and message handlers untuk AllenVault.
Menangani interaksi pengguna, parsing transaksi, alur konfirmasi,
serta manajemen akun dan riwayat.
"""

import logging
import uuid
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import config
from bot.keyboards import (
    confirm_keyboard,
    missing_account_keyboard,
    edit_menu_keyboard,
    category_picker_keyboard,
    date_picker_keyboard,
    report_period_keyboard,
    chart_selection_keyboard,
    main_menu_keyboard,
    CB_CONFIRM,
    CB_EDIT,
    CB_CANCEL,
    CB_SEL_ACC,
    CB_SEL_CAT,
    CB_SEL_DATE,
    CB_EDIT_FIELD,
)
from database.db import (
    save_confirmation_session,
    get_confirmation_session,
    update_confirmation_session,
    delete_confirmation_session,
    log_activity,
)
from integrations.ai_client import parse_transaction, parse_transactions
from services.account_service import (
    get_all_accounts,
    get_all_balances,
    calculate_balance,
    add_account,
)
from services.transaction_service import commit_transaction, get_recent_history, sync_pending
from services.receipt_service import (
    extract_receipt_from_image,
    format_receipt_preview,
    commit_receipt,
)
from services.report_service import (
    get_financial_summary,
    format_report_message,
    get_monthly_trend_data,
)
from services.chart_service import (
    generate_category_pie_chart,
    generate_income_vs_expense_chart,
    generate_monthly_trend_chart,
)
from services.budget_service import (
    get_budget_overview,
    format_budget_message,
    set_category_budget,
)
from utils.parser import parse_amount
from utils.formatters import (
    format_currency,
    format_transaction_preview,
    format_confirmed_receipt,
    format_balance_overview,
    format_history_list,
    format_batch_preview,
)

logger = logging.getLogger(__name__)


# ─── Authorization decorator ─────────────────────────────────
def authorized_only(func):
    """
    Decorator: hanya izinkan user yang ada di ALLOWED_USER_IDS.
    """
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user:
            return
        if user.id not in config.ALLOWED_USER_IDS:
            logger.warning(
                f"Akses ditolak untuk user {user.id} (@{user.username})"
            )
            await update.effective_message.reply_text(
                "⛔ Maaf, kamu tidak memiliki akses ke bot ini."
            )
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


# ─── /start ───────────────────────────────────────────────────
@authorized_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk perintah /start."""
    user = update.effective_user
    text = (
        f"👋 Halo, *{user.first_name}*!\n\n"
        f"Selamat datang di *AllenVault* — Personal Finance Assistant-mu.\n\n"
        f"_Know Where Your Money Goes._\n\n"
        f"💡 *Cara cepat mencatat:*\n"
        f"Cukup kirim pesan seperti biasa, misalnya:\n"
        f"• _\"Bakmi GM 50rb pakai BCA\"_\n"
        f"• _\"Beli kopi 18k pake cash\"_\n"
        f"• _\"Dapat gaji freelance 500rb masuk Mandiri\"_\n"
        f"• _\"Transfer 200rb dari BCA ke GoPay\"_\n\n"
        f"Gunakan /help untuk melihat semua perintah."
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(),
    )
    log_activity(user.id, "CMD_START")


# ─── /help ────────────────────────────────────────────────────
@authorized_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk perintah /help."""
    text = (
        "📖 *Daftar Perintah AllenVault*\n\n"
        "*Transaksi Otomatis*\n"
        "Cukup ketik pesan bebas, contoh:\n"
        "• _\"Makan siang 25rb pakai BCA\"_\n"
        "• _\"Gaji 3 juta masuk Mandiri\"_\n"
        "• _\"Transfer 100rb dari BCA ke DANA\"_\n\n"
        "*Informasi Akun & Saldo*\n"
        "/balance — Tampilkan saldo semua akun\n"
        "/accounts — Daftar dan kelola akun\n"
        "/addaccount — Tambah akun baru\n"
        "/history — Riwayat transaksi terakhir\n\n"
        "*Perintah Transaksi Manual*\n"
        "/income `<detail>` — Catat pemasukan\n"
        "/expense `<detail>` — Catat pengeluaran\n"
        "/transfer `<detail>` — Transfer antar akun\n\n"
        "*Laporan & Visualisasi*\n"
        "/summary — Ringkasan keuangan bulan ini\n"
        "/report — Laporan keuangan (hari/minggu/bulan/tahun)\n"
        "/chart — Grafik pengeluaran per kategori & tren\n"
        "/budget — Pantau & atur anggaran belanja\n\n"
        "*Lainnya*\n"
        "/sync — Sinkronisasi transaksi antrean offline\n"
        "/myid — Tampilkan Telegram ID-mu\n"
        "/cancel — Batalkan operasi saat ini"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─── /myid ────────────────────────────────────────────────────
async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler /myid agar user dapat mengetahui ID sebelum di-allowlist."""
    user = update.effective_user
    text = (
        f"🆔 *Telegram ID-mu:*\n"
        f"`{user.id}`\n\n"
        f"Salin ID ini dan tambahkan ke `ALLOWED_USER_IDS` di file `.env`."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─── /cancel ─────────────────────────────────────────────────
@authorized_only
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Batalkan operasi atau conversation yang sedang berlangsung."""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Operasi dibatalkan.",
        reply_markup=main_menu_keyboard(),
    )


# ─── /balance ─────────────────────────────────────────────────
@authorized_only
async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tampilkan saldo semua akun keuangan aktif."""
    await update.message.reply_text("⏳ Sedang menghitung saldo...")
    balances = get_all_balances()
    text = format_balance_overview(balances)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─── /accounts ────────────────────────────────────────────────
@authorized_only
async def cmd_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tampilkan daftar akun dan panduan menambah akun."""
    accounts = get_all_accounts()
    if not accounts:
        text = (
            "🏦 *Daftar Akun Keuangan*\n\n"
            "Belum ada akun yang terdaftar.\n\n"
            "Kamu dapat menambahkan akun dengan perintah:\n"
            "`/addaccount <Nama Akun> <Tipe> <Saldo Awal>`\n\n"
            "Contoh:\n"
            "• `/addaccount BCA Bank 1000000`\n"
            "• `/addaccount Cash Cash 250000`\n"
            "• `/addaccount GoPay E-Wallet 100000`"
        )
    else:
        lines = ["🏦 *Daftar Akun Keuangan Terdaftar:*\n"]
        for a in accounts:
            name = a.get("account_name", "-")
            acc_type = a.get("account_type", "-")
            init_bal = float(a.get("initial_balance", 0) or 0)
            cur_bal = calculate_balance(name)
            emoji = {"Bank": "🏦", "E-Wallet": "📱", "Cash": "💵"}.get(acc_type, "💳")
            lines.append(f"{emoji} *{name}* ({acc_type})")
            lines.append(f"   Saldo: {format_currency(cur_bal)} (Awal: {format_currency(init_bal)})\n")
        lines.append("Tambah akun baru: `/addaccount <Nama> <Tipe> <Saldo Awal>`")
        text = "\n".join(lines)

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─── /addaccount ──────────────────────────────────────────────
@authorized_only
async def cmd_addaccount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Tambah akun baru secara manual.
    Format: /addaccount <Nama> [Tipe: Bank/E-Wallet/Cash] [Saldo Awal]
    Contoh: /addaccount BCA Bank 1500000
    """
    args = context.args
    if not args:
        await update.message.reply_text(
            "ℹ️ *Format Tambah Akun:*\n"
            "`/addaccount <Nama Akun> <Tipe: Bank/E-Wallet/Cash> <Saldo Awal>`\n\n"
            "Contoh:\n"
            "• `/addaccount BCA Bank 1000000`\n"
            "• `/addaccount GoPay E-Wallet 150000`\n"
            "• `/addaccount Cash Cash 500000`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    name = args[0]
    acc_type = args[1] if len(args) > 1 else "Bank"
    initial_balance = 0.0

    if len(args) > 2:
        try:
            # Bersihkan titik / koma
            clean_bal = args[2].replace(".", "").replace(",", "")
            initial_balance = float(clean_bal)
        except ValueError:
            initial_balance = 0.0

    # Normalisasi tipe
    if acc_type.lower() in ("ewallet", "e-wallet", "dompet"):
        acc_type = "E-Wallet"
    elif acc_type.lower() in ("cash", "tunai"):
        acc_type = "Cash"
    else:
        acc_type = "Bank"

    success, msg = add_account(name, acc_type, initial_balance)
    if success:
        await update.message.reply_text(
            f"✅ *Akun Berhasil Didaftarkan!*\n\n"
            f"• *Nama Akun:* {name}\n"
            f"• *Tipe:* {acc_type}\n"
            f"• *Saldo Awal:* {format_currency(initial_balance)}",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(f"⚠️ {msg}")


# ─── /history ─────────────────────────────────────────────────
@authorized_only
async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tampilkan riwayat transaksi terakhir."""
    txs = get_recent_history(limit=5)
    text = format_history_list(txs)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─── /sync ────────────────────────────────────────────────────
@authorized_only
async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sinkronkan transaksi antrean pending ke Google Sheets."""
    await update.message.reply_text("🔄 Memeriksa antrean sinkronisasi...")
    synced = sync_pending()
    if synced > 0:
        await update.message.reply_text(f"✅ Berhasil menyinkronkan {synced} transaksi ke Google Sheets.")
    else:
        await update.message.reply_text("✨ Semua transaksi sudah tersinkronisasi ke Google Sheets.")


# ─── Perintah belum diimplementasikan (Phase 5+) ─────────────
async def _not_implemented(update: Update, context: ContextTypes.DEFAULT_TYPE, feature: str) -> None:
    await update.message.reply_text(
        f"⏳ Fitur *{feature}* akan hadir di fase berikutnya.\n"
        f"Gunakan /help untuk melihat fitur yang sudah tersedia.",
        parse_mode=ParseMode.MARKDOWN,
    )


@authorized_only
async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ringkasan keuangan cepat (Bulan Ini)."""
    await cmd_report(update, context)


@authorized_only
async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manajemen dan pemantauan anggaran bulanan.
    Penggunaan:
      /budget — Lihat status anggaran bulan ini
      /budget set <kategori> <nominal> — Atur anggaran kategori
      Contoh: /budget set makan 2jt
    """
    args = context.args or []
    if not args:
        msg = await update.message.reply_text("⏳ Mengambil data anggaran...")
        overview = get_budget_overview()
        text = format_budget_message(overview)
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    # Kasus: /budget set <kategori> <nominal> atau /budget <kategori> <nominal>
    if args[0].lower() == "set":
        cat_tokens = args[1:-1]
        amt_token = args[-1] if len(args) > 2 else ""
        if not cat_tokens or not amt_token:
            await update.message.reply_text(
                "💡 *Format perintah:*\n"
                "`/budget set <kategori> <nominal>`\n\n"
                "*Contoh:*\n"
                "• `/budget set makan 2jt`\n"
                "• `/budget set transport 500rb`\n"
                "• `/budget set belanja 1.5jt`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        cat_query = " ".join(cat_tokens)
    elif len(args) >= 2:
        cat_query = " ".join(args[:-1])
        amt_token = args[-1]
    else:
        await update.message.reply_text(
            "💡 *Format perintah:*\n"
            "`/budget set <kategori> <nominal>`\n\n"
            "*Contoh:*\n"
            "• `/budget set makan 2jt`\n"
            "• `/budget set transport 500rb`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    parsed_amt = parse_amount(amt_token)
    if not parsed_amt or parsed_amt <= 0:
        await update.message.reply_text("⚠️ Nominal anggaran tidak valid. Contoh: `2jt`, `500rb`, `1500000`.")
        return

    status_msg = await update.message.reply_text("⏳ Menyimpan pengaturan anggaran...")
    ok, response_text, _ = set_category_budget(cat_query, parsed_amt)
    await status_msg.edit_text(response_text, parse_mode=ParseMode.MARKDOWN)


@authorized_only
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Tampilkan laporan keuangan berdasarkan periode.
    Format: /report [hari ini | minggu ini | bulan ini | tahun ini]
    """
    args = context.args or []
    period = "month"
    if args:
        arg_str = " ".join(args).lower()
        if "hari" in arg_str:
            period = "today"
        elif "minggu" in arg_str:
            period = "week"
        elif "tahun" in arg_str:
            period = "year"
        elif "semua" in arg_str:
            period = "all"

    msg = await update.message.reply_text("⏳ Menyiapkan laporan keuangan...")
    report_data = get_financial_summary(period=period)
    text = format_report_message(report_data)
    await msg.edit_text(text, reply_markup=report_period_keyboard(), parse_mode=ParseMode.MARKDOWN)


@authorized_only
async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Generate dan kirim grafik visual keuangan ke Telegram.
    Format: /chart [kategori | bulanan | tren]
    """
    msg = await update.message.reply_text("⏳ Sedang membuat grafik visual...")
    args = context.args or []
    chart_type = "category"
    if args:
        arg_str = " ".join(args).lower()
        if "tren" in arg_str or "trend" in arg_str:
            chart_type = "trend"
        elif "in" in arg_str or "vs" in arg_str or "pemasukan" in arg_str:
            chart_type = "in_vs_out"

    img_bytes = None
    caption = ""

    if chart_type == "category":
        report_data = get_financial_summary(period="month")
        img_bytes = generate_category_pie_chart(report_data["category_breakdown"], period_title="Bulan Ini")
        caption = "📊 *Grafik Pengeluaran per Kategori (Bulan Ini)*"
    elif chart_type == "in_vs_out":
        trend_data = get_monthly_trend_data(6)
        img_bytes = generate_income_vs_expense_chart(trend_data)
        caption = "📊 *Grafik Pemasukan vs Pengeluaran Bulanan*"
    elif chart_type == "trend":
        trend_data = get_monthly_trend_data(6)
        img_bytes = generate_monthly_trend_chart(trend_data)
        caption = "📈 *Grafik Tren Pengeluaran Bulanan*"

    await msg.delete()

    if not img_bytes:
        await update.message.reply_text(
            "ℹ️ Belum cukup data transaksi untuk membuat grafik ini.",
            reply_markup=chart_selection_keyboard(),
        )
        return

    await update.message.reply_photo(
        photo=img_bytes,
        caption=caption,
        reply_markup=chart_selection_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── /income, /expense, /transfer ─────────────────────────────
@authorized_only
async def cmd_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text(
            "ℹ️ *Contoh Catat Pemasukan:*\n"
            "`/income 500rb freelance desain via Mandiri`\n"
            "Atau langsung ketik tanpa command: _\"Dapat freelance 500rb via Mandiri\"_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    await _process_transaction_text(update, context, f"Dapat {text}")


@authorized_only
async def cmd_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text(
            "ℹ️ *Contoh Catat Pengeluaran:*\n"
            "`/expense 25rb makan siang pakai BCA`\n"
            "Atau langsung ketik tanpa command: _\"Beli makan 25rb pakai BCA\"_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    await _process_transaction_text(update, context, f"Beli {text}")


@authorized_only
async def cmd_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text(
            "ℹ️ *Contoh Transfer Antar Akun:*\n"
            "`/transfer 200rb dari BCA ke DANA`\n"
            "Atau langsung ketik: _\"Transfer 200rb dari BCA ke DANA\"_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    await _process_transaction_text(update, context, f"Transfer {text}")


# ─── Text message handler (Core NLP Flow) ─────────────────────
@authorized_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Menangani pesan teks natural dari pengguna.
    Mengurai transaksi, meminta kelengkapan info jika perlu,
    lalu menampilkan preview konfirmasi.
    """
    text = update.message.text.strip()
    user_id = update.effective_user.id
    logger.info(f"Pesan teks diterima dari user {user_id}: {text!r}")

    # Shortcut menu keyboard
    shortcuts = {
        "📊 Ringkasan": cmd_summary,
        "💰 Saldo":     cmd_balance,
        "➕ Pemasukan": cmd_income,
        "➖ Pengeluaran": cmd_expense,
        "🔄 Transfer":  cmd_transfer,
        "📋 Riwayat":   cmd_history,
        "📈 Laporan":   cmd_report,
        "🎯 Anggaran":  cmd_budget,
    }
    if text in shortcuts:
        await shortcuts[text](update, context)
        return

    # Deteksi teks natural bernada permintaan laporan/grafik
    text_lower = text.lower()
    if any(kw in text_lower for kw in ("grafik", "chart", "pie chart", "tren pengeluaran", "grafik pengeluaran")):
        await cmd_chart(update, context)
        return
    if any(kw in text_lower for kw in ("laporan", "rekap", "ringkasan keuangan", "laporan bulanan", "laporan bulan ini")):
        await cmd_report(update, context)
        return
    if any(kw in text_lower for kw in ("anggaran", "budget", "sisa budget", "cek budget", "status budget")):
        await cmd_budget(update, context)
        return

    await _process_transaction_text(update, context, text)


async def _process_transaction_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Helper untuk memproses teks transaksi (single maupun batch) dan menampilkan konfirmasi."""
    user = update.effective_user
    txs = parse_transactions(text)

    # 1. Cek apakah ada nominal yang terdeteksi
    if not txs or not txs[0].get("amount") or txs[0]["amount"] <= 0:
        await update.message.reply_text(
            "🤖 Saya tidak mendeteksi nominal uang dalam pesanmu.\n\n"
            "💡 *Contoh cara mencatat:*\n"
            "• _\"Bakmi GM 50rb pakai BCA\"_\n"
            "• _\"Kemarin soto 20rb spay, bakso 15rb & celana 60rb mandiri\"_\n"
            "• _\"Gaji 5 juta masuk Mandiri\"_\n"
            "• _\"Transfer 150rb dari BCA ke GoPay\"_\n\n"
            "Ketik /help untuk panduan lengkap.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # 2. Jika transaksi batch (> 1)
    if len(txs) > 1:
        session_key = f"batch_{uuid.uuid4().hex[:8]}"
        for t in txs:
            if not t.get("account") and t.get("type") != "Transfer":
                t["account"] = "Cash"

        save_confirmation_session(user.id, session_key, {"transactions": txs}, session_type="batch")
        preview_text = format_batch_preview(txs)

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        batch_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✅ Konfirmasi Semua ({len(txs)})", callback_data=f"{CB_CONFIRM}:{session_key}")],
            [InlineKeyboardButton("❌ Batalkan", callback_data=f"{CB_CANCEL}:{session_key}")],
        ])

        await update.message.reply_text(
            preview_text,
            reply_markup=batch_kb,
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # 3. Transaksi tunggal
    parsed = txs[0]
    amount = parsed.get("amount")
    session_key = uuid.uuid4().hex[:10]
    tx_type = parsed.get("type", "Expense")

    # Cek apakah akun keuangan sudah ditentukan
    if tx_type != "Transfer" and not parsed.get("account"):
        save_confirmation_session(user.id, session_key, parsed)
        existing_accounts = get_all_accounts()
        await update.message.reply_text(
            f"💳 Transaksi *{format_currency(amount)}* terdeteksi!\n"
            f"Silakan pilih akun / sumber dana yang digunakan:",
            reply_markup=missing_account_keyboard(session_key, existing_accounts),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if tx_type == "Transfer" and (not parsed.get("from_account") or not parsed.get("to_account")):
        save_confirmation_session(user.id, session_key, parsed)
        existing_accounts = get_all_accounts()
        await update.message.reply_text(
            f"🔄 Transfer *{format_currency(amount)}* terdeteksi.\n"
            f"Mohon lengkapi akun asal atau tujuan:",
            reply_markup=missing_account_keyboard(session_key, existing_accounts),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Data lengkap — tampilkan konfirmasi
    save_confirmation_session(user.id, session_key, parsed)
    preview_text = format_transaction_preview(parsed)
    await update.message.reply_text(
        preview_text,
        reply_markup=confirm_keyboard(session_key),
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── Callback Query Handler (Confirmation & Edit Actions) ─────
@authorized_only
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Menangani aksi tombol inline:
    Confirm, Cancel, Edit, Pilih Akun, Pilih Kategori.
    """
    query = update.callback_query
    await query.answer()

    data_str = query.data or ""
    parts = data_str.split(":")
    action = parts[0]
    session_key = parts[1] if len(parts) > 1 else ""

    logger.info(f"Callback query: action={action}, session_key={session_key}")

    # ── 1. BATALKAN ───────────────────────────────────────────
    if action == CB_CANCEL:
        if session_key:
            delete_confirmation_session(session_key)
        await query.edit_message_text("❌ Transaksi dibatalkan.")
        return

    # ── 2. PILIH AKUN ─────────────────────────────────────────
    if action == CB_SEL_ACC:
        # Format: sel_acc:<session_key>:<role>:<acc_name>
        role = parts[2] if len(parts) > 2 else "account"
        acc_name = parts[3] if len(parts) > 3 else "Cash"

        session_data = get_confirmation_session(session_key)
        if not session_data:
            await query.edit_message_text("⚠️ Sesi telah berakhir. Silakan ketik kembali transaksi.")
            return

        if session_data.get("type") == "Transfer":
            if not session_data.get("from_account"):
                session_data["from_account"] = acc_name
            else:
                session_data["to_account"] = acc_name
        else:
            session_data["account"] = acc_name
            session_data["payment_method"] = acc_name

        update_confirmation_session(session_key, session_data)

        # Tampilkan preview konfirmasi sesuai tipe sesi
        if session_data.get("_session_type") == "receipt":
            preview_text = format_receipt_preview(session_data)
        else:
            preview_text = format_transaction_preview(session_data)

        await query.edit_message_text(
            preview_text,
            reply_markup=confirm_keyboard(session_key),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── 3. KONFIRMASI TRANSAKSI ───────────────────────────────
    if action == CB_CONFIRM:
        session_data = get_confirmation_session(session_key)
        if not session_data:
            await query.edit_message_text("⚠️ Sesi konfirmasi telah kadaluarsa. Silakan ulangi transaksi.")
            return

        await query.edit_message_text("⏳ Menyimpan transaksi ke Google Sheets...")

        user_id = update.effective_user.id

        # ── A. Kasus Transaksi Batch (> 1) ────────────────────
        if session_data.get("_session_type") == "batch":
            batch_txs = session_data.get("transactions", [])
            saved_count = 0
            affected_accounts = set()
            lines = [f"✅ *{len(batch_txs)} Transaksi Berhasil Disimpan ke Sheets!*\n"]

            for idx, tx in enumerate(batch_txs, 1):
                ok, mode, saved = commit_transaction(tx, user_id=user_id)
                if ok:
                    saved_count += 1
                    desc = saved.get("description") or "Transaksi"
                    amt = format_currency(saved.get("amount", 0))
                    acc = saved.get("account") or "Cash"
                    lines.append(f"{idx}. {desc} — *{amt}* ({acc})")
                    if saved.get("account"):
                        affected_accounts.add(saved["account"])
                    if saved.get("from_account"):
                        affected_accounts.add(saved["from_account"])
                    if saved.get("to_account"):
                        affected_accounts.add(saved["to_account"])

            if affected_accounts:
                lines.append("\n💰 *Saldo Terkini:*")
                for acc_name in sorted(affected_accounts):
                    bal = calculate_balance(acc_name)
                    lines.append(f"• {acc_name}: {format_currency(bal)}")

            delete_confirmation_session(session_key)
            await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
            return

        # ── B. Kasus Transaksi Tunggal & Struk ─────────────────
        is_receipt = (session_data.get("_session_type") == "receipt")

        if is_receipt:
            success, mode, saved_tx = commit_receipt(session_data, user_id=user_id)
        else:
            success, mode, saved_tx = commit_transaction(session_data, user_id=user_id)

        if not success:
            await query.edit_message_text(f"❌ {mode}")
            return

        # Hitung saldo akun terkini
        account_balances = {}
        tx_type = saved_tx.get("type", "Expense")
        if tx_type == "Transfer":
            from_acc = saved_tx.get("from_account")
            to_acc = saved_tx.get("to_account")
            if from_acc:
                account_balances[from_acc] = calculate_balance(from_acc)
            if to_acc:
                account_balances[to_acc] = calculate_balance(to_acc)
        else:
            acc = saved_tx.get("account")
            if acc:
                account_balances[acc] = calculate_balance(acc)

        if is_receipt:
            items_count = len(session_data.get("items", []))
            receipt_text = (
                f"✅ *Struk Belanja Berhasil Disimpan!*\n\n"
                f"• Merchant: *{saved_tx.get('merchant', 'Toko')}*\n"
                f"• Total Bayar: *{format_currency(saved_tx.get('amount', 0))}*\n"
                f"• Akun Pembayaran: *{saved_tx.get('account', '-')}*\n"
                f"• Rincian: *{items_count} barang tercatat di tab Receipt\\_Items*\n"
            )
            if account_balances:
                receipt_text += "\n💰 *Saldo Terkini:*\n"
                for acc_name, bal in account_balances.items():
                    receipt_text += f"• {acc_name}: {format_currency(bal)}\n"
        else:
            receipt_text = format_confirmed_receipt(saved_tx, account_balances)

        if mode == "pending":
            receipt_text += "\n\n⚠️ _Tersimpan di antrean lokal (Google Sheets sedang offline)._"

        delete_confirmation_session(session_key)
        await query.edit_message_text(receipt_text, parse_mode=ParseMode.MARKDOWN)
        return

    # ── 4. MENU EDIT ──────────────────────────────────────────
    if action == CB_EDIT:
        session_data = get_confirmation_session(session_key)
        if not session_data:
            await query.edit_message_text("⚠️ Sesi konfirmasi telah kadaluarsa.")
            return
        await query.edit_message_text(
            "✏️ *Pilih bagian yang ingin diubah:*",
            reply_markup=edit_menu_keyboard(session_key),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── 5. EDIT FIELD TERTENTU ────────────────────────────────
    if action == CB_EDIT_FIELD:
        field = parts[2] if len(parts) > 2 else ""
        session_data = get_confirmation_session(session_key)
        if not session_data:
            await query.edit_message_text("⚠️ Sesi konfirmasi telah kadaluarsa.")
            return

        if field == "category":
            categories = [
                "Makanan & Minuman", "Transportasi", "Belanja",
                "Tagihan & Utilitas", "Kesehatan", "Hiburan",
                "Pendidikan", "Perawatan Diri", "Rumah Tangga", "Lain-lain",
            ]
            await query.edit_message_text(
                "📂 *Pilih Kategori Baru:*",
                reply_markup=category_picker_keyboard(session_key, categories),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        elif field == "account":
            existing = get_all_accounts()
            await query.edit_message_text(
                "💳 *Pilih Akun Baru:*",
                reply_markup=missing_account_keyboard(session_key, existing),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        elif field == "date":
            await query.edit_message_text(
                "📅 *Pilih Tanggal Transaksi:*",
                reply_markup=date_picker_keyboard(session_key),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        else:
            await query.edit_message_text(
                "💡 Untuk mengubah nominal atau deskripsi, silakan ketik ulang kalimat transaksi yang benar."
            )
            return

    # ── 6. PILIH KATEGORI (DARI EDIT) ─────────────────────────
    if action == CB_SEL_CAT:
        cat_name = parts[2] if len(parts) > 2 else "Lain-lain"
        session_data = get_confirmation_session(session_key)
        if not session_data:
            await query.edit_message_text("⚠️ Sesi konfirmasi telah kadaluarsa.")
            return

        session_data["category"] = cat_name
        update_confirmation_session(session_key, session_data)

        if session_data.get("_session_type") == "receipt":
            preview_text = format_receipt_preview(session_data)
        else:
            preview_text = format_transaction_preview(session_data)

        await query.edit_message_text(
            preview_text,
            reply_markup=confirm_keyboard(session_key),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── 7. PILIH TANGGAL (DARI EDIT) ──────────────────────────
    if action == CB_SEL_DATE:
        chosen_date = parts[2] if len(parts) > 2 else ""
        session_data = get_confirmation_session(session_key)
        if not session_data:
            await query.edit_message_text("⚠️ Sesi konfirmasi telah kadaluarsa.")
            return

        if chosen_date:
            session_data["date"] = chosen_date
            update_confirmation_session(session_key, session_data)

        if session_data.get("_session_type") == "receipt":
            preview_text = format_receipt_preview(session_data)
        else:
            preview_text = format_transaction_preview(session_data)

        await query.edit_message_text(
            preview_text,
            reply_markup=confirm_keyboard(session_key),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── 8. KEMBALI KE PREVIEW ─────────────────────────────────
    if action == "show_confirm":
        session_data = get_confirmation_session(session_key)
        if not session_data:
            await query.edit_message_text("⚠️ Sesi konfirmasi telah kadaluarsa.")
            return

        if session_data.get("_session_type") == "receipt":
            preview_text = format_receipt_preview(session_data)
        else:
            preview_text = format_transaction_preview(session_data)

        await query.edit_message_text(
            preview_text,
            reply_markup=confirm_keyboard(session_key),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── 9. GANTI PERIODE LAPORAN KEUANGAN ─────────────────────
    if action == "rep_period":
        period = parts[1] if len(parts) > 1 else "month"
        report_data = get_financial_summary(period=period)
        text = format_report_message(report_data)
        await query.edit_message_text(text, reply_markup=report_period_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return

    # ── 10. MENU PILIHAN GRAFIK ───────────────────────────────
    if action == "chart_menu":
        await query.edit_message_text(
            "📈 *Pilih Jenis Grafik Keuangan yang Ingin Dibuat:*",
            reply_markup=chart_selection_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # ── 11. GENERATE GRAFIK DARI TOMBOL ───────────────────────
    if action == "chart_gen":
        ctype = parts[1] if len(parts) > 1 else "category"
        img_bytes = None
        caption = ""

        if ctype == "category":
            report_data = get_financial_summary(period="month")
            img_bytes = generate_category_pie_chart(report_data["category_breakdown"], period_title="Bulan Ini")
            caption = "📊 *Grafik Pengeluaran per Kategori (Bulan Ini)*"
        elif ctype == "in_vs_out":
            trend_data = get_monthly_trend_data(6)
            img_bytes = generate_income_vs_expense_chart(trend_data)
            caption = "📊 *Grafik Pemasukan vs Pengeluaran Bulanan*"
        elif ctype == "trend":
            trend_data = get_monthly_trend_data(6)
            img_bytes = generate_monthly_trend_chart(trend_data)
            caption = "📈 *Grafik Tren Pengeluaran Bulanan*"

        if not img_bytes:
            await query.answer("Belum cukup data transaksi untuk membuat grafik ini.", show_alert=True)
            return

        chat_id = update.effective_chat.id
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=img_bytes,
            caption=caption,
            reply_markup=chart_selection_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return


# ─── Photo handler ────────────────────────────────────────────
@authorized_only
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menangani foto struk belanja dengan AI Gemini (Phase 4)."""
    user = update.effective_user
    photo = update.message.photo[-1]  # Resolusi tertinggi
    status_msg = await update.message.reply_text("🔍 Sedang menganalisis foto struk dengan AI Gemini...")

    try:
        file = await context.bot.get_file(photo.file_id)
        img_bytearray = await file.download_as_bytearray()
        img_bytes = bytes(img_bytearray)
    except Exception as e:
        logger.error(f"Gagal mengunduh foto struk: {e}")
        await status_msg.edit_text("⚠️ Gagal mengunduh foto dari Telegram. Silakan coba kirim ulang.")
        return

    receipt_data = extract_receipt_from_image(img_bytes)
    if not receipt_data or not receipt_data.get("is_readable", True):
        await status_msg.edit_text(
            "⚠️ *Struk Belanja Tidak Terbaca*\n\n"
            "AI tidak dapat membaca informasi total atau rincian barang dari foto ini.\n\n"
            "💡 *Tips:* \n"
            "• Pastikan foto terang dan tidak buram\n"
            "• Bagian nama toko dan total bayar terlihat jelas\n\n"
            "Silakan kirim ulang foto yang lebih jelas atau catat manual dengan teks.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    session_key = f"rec_{uuid.uuid4().hex[:8]}"
    total = receipt_data.get("total_amount", 0)

    # Jika struk belum memiliki akun pembayaran, tanyakan akun
    if not receipt_data.get("account"):
        save_confirmation_session(user.id, session_key, receipt_data, session_type="receipt")
        existing_accounts = get_all_accounts()
        await status_msg.edit_text(
            f"🧾 Struk di *{receipt_data.get('merchant', 'Toko')}* senilai *{format_currency(total)}* terdeteksi!\n\n"
            f"Silakan pilih akun pembayaran yang digunakan:",
            reply_markup=missing_account_keyboard(session_key, existing_accounts),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Jika akun sudah terdeteksi
    save_confirmation_session(user.id, session_key, receipt_data, session_type="receipt")
    preview_text = format_receipt_preview(receipt_data)
    await status_msg.edit_text(
        preview_text,
        reply_markup=confirm_keyboard(session_key),
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── Error handler ────────────────────────────────────────────
async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log error dan kirim pesan ramah ke user jika memungkinkan."""
    logger.error(f"Error saat memproses update: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Terjadi kesalahan dalam memproses permintaan. Silakan coba beberapa saat lagi."
        )
