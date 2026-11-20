# AllenVault — Personal Finance Assistant

> **Know Where Your Money Goes.**

Bot Telegram personal finance berbasis Python + Google Sheets.

## Quick Start

```bash
# 1. Clone / masuk ke folder proyek
cd allen-vault

# 2. Install dependencies
pip install -r requirements.txt

# 3. Siapkan credentials (lihat SETUP.md)
copy .env.example .env
# → edit .env dengan token & credentials kamu

# 4. Jalankan bot
python main.py

# 5. Jalankan Web Dashboard (Buka di Browser)
python run_dashboard.py
```

## Web Dashboard (Vercel-Ready)
AllenVault dilengkapi dengan web dashboard modern berbasis **FastAPI + Tailwind CSS + ApexCharts**.
* Panduan lokal & deploy gratis ke Vercel: lihat [`DEPLOY_DASHBOARD.md`](DEPLOY_DASHBOARD.md).

## Setup Lengkap

Ikuti panduan step-by-step di [`SETUP.md`](SETUP.md).

## Development Phases

| Phase | Status | Deskripsi |
|---|---|---|
| Phase 1 — Bot Foundation | ✅ Done | Telegram bot, auth, commands dasar, SQLite init |
| Phase 2 — Google Sheets | ✅ Done | Koneksi spreadsheet, tab setup, read/write, format header |
| Phase 3 — Transactions | ✅ Done | Parser teks natural (single & batch, tanggal lampau), alur konfirmasi & edit, saldo realtime, antrean offline |
| Phase 4 — Receipt Scanner | ✅ Done | OCR struk via Gemini Vision AI, item-level ke tab Receipt_Items, subtotal & merchant |
| Phase 5 — Reports | ✅ Done | Laporan keuangan /summary & /report (harian, mingguan, bulanan, tahunan), breakdown kategori & net cash flow |
| Phase 6 — Visual Charts & Dashboard | ✅ Done | Donut chart kategori, bar chart pemasukan vs pengeluaran, line chart tren bulanan via Matplotlib & Google Sheets Dashboard |
| Phase 7 — Budgeting & Testing | ✅ Done | Fitur /budget pemantauan batas anggaran & progress bar visual; 52 unit tests lengkap lulus 100% |

## Tech Stack

- **Python 3.12+**
- **python-telegram-bot 21.9**
- **Google Sheets API** (via gspread)
- **SQLite** (local cache & queue)
- **Pandas + Matplotlib** (reports & charts)
- **Gemini API** (receipt OCR — Phase 4)

## Security

- ✅ Token disimpan di `.env` (tidak di-commit)
- ✅ `credentials.json` di `.gitignore`
- ✅ User ID allowlist
- ✅ Konfirmasi wajib sebelum simpan transaksi
- ✅ Duplicate transaction detection

## Run Tests

```bash
python -m pytest tests/ -v
```

