"""
AllenVault — Main Entry Point
Inisialisasi dan menjalankan Telegram bot.
"""

import logging
import sys

import config
from config import setup_logging, validate_config
from database.db import init_db
from integrations.google_sheets import get_client as get_sheets_client

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from bot.handlers import (
    cmd_start,
    cmd_help,
    cmd_myid,
    cmd_cancel,
    cmd_summary,
    cmd_balance,
    cmd_accounts,
    cmd_addaccount,
    cmd_history,
    cmd_sync,
    cmd_income,
    cmd_expense,
    cmd_transfer,
    cmd_budget,
    cmd_report,
    cmd_chart,
    handle_text,
    handle_callback,
    handle_photo,
    handle_error,
)


def main() -> None:
    # 1. Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("AllenVault — Personal Finance Assistant")
    logger.info("=" * 50)

    # 2. Validasi konfigurasi
    errors = validate_config()
    if errors:
        logger.error("Konfigurasi tidak lengkap:")
        for err in errors:
            logger.error(f"  ✗ {err}")
        logger.error(
            "\nSalin .env.example ke .env dan isi semua nilai yang diperlukan."
        )
        sys.exit(1)

    # 3. Inisialisasi database SQLite
    try:
        init_db()
    except Exception as e:
        logger.error(f"Gagal menginisialisasi database: {e}")
        sys.exit(1)

    # 4. Koneksi ke Google Sheets
    logger.info("Menghubungkan ke Google Sheets...")
    sheets = get_sheets_client()
    if sheets.is_connected():
        logger.info("Google Sheets terhubung ✓")
    else:
        logger.warning(
            "Google Sheets tidak terhubung saat startup. "
            "Bot tetap berjalan — akan retry saat ada transaksi."
        )

    # 5. Buat Telegram Application
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # 6. Daftarkan handlers
    # Command handlers
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("myid",     cmd_myid))
    app.add_handler(CommandHandler("cancel",   cmd_cancel))
    app.add_handler(CommandHandler("summary",  cmd_summary))
    app.add_handler(CommandHandler("balance",    cmd_balance))
    app.add_handler(CommandHandler("accounts",   cmd_accounts))
    app.add_handler(CommandHandler("addaccount", cmd_addaccount))
    app.add_handler(CommandHandler("history",    cmd_history))
    app.add_handler(CommandHandler("sync",       cmd_sync))
    app.add_handler(CommandHandler("income",     cmd_income))
    app.add_handler(CommandHandler("expense",    cmd_expense))
    app.add_handler(CommandHandler("transfer",   cmd_transfer))
    app.add_handler(CommandHandler("budget",     cmd_budget))
    app.add_handler(CommandHandler("report",     cmd_report))
    app.add_handler(CommandHandler("chart",      cmd_chart))

    # Callback query handler (Inline button clicks: confirm, cancel, edit, etc.)
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Text message handler (non-command)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Photo handler
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Error handler
    app.add_error_handler(handle_error)

    # 7. Jalankan bot
    logger.info(f"Bot berjalan. Allowed users: {config.ALLOWED_USER_IDS}")
    logger.info("Tekan Ctrl+C untuk berhenti.")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()

