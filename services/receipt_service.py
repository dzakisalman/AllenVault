"""
services/receipt_service.py
Modul OCR & ekstraksi struk belanja menggunakan Google Gemini AI.
Mengekstrak merchant, tanggal, total bayar, kategori, dan daftar item belanjaan.
"""

import io
import json
import logging
import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, TIMEZONE
from integrations.google_sheets import get_client
from services.transaction_service import commit_transaction
from utils.formatters import format_currency, format_date

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_FALLBACK_MODEL = "gemini-3.8-flash"

RECEIPT_PROMPT = """Kamu adalah sistem OCR dan analisis struk belanja/nota/receipt keuangan Indonesia.
Analisis gambar struk belanja berikut dengan sangat teliti dan ekstrak informasinya ke dalam format JSON murni.

Aturan Ekstraksi:
1. `merchant`: Nama toko, minimarket, atau restoran (contoh: Indomaret, Alfamart, Starbucks, Superindo, dll). Jika tidak jelas, gunakan "Struk Belanja".
2. `date`: Tanggal transaksi dalam format "YYYY-MM-DD". Jika tanggal tidak terlihat jelas atau buram, gunakan tanggal hari ini: "{today}".
3. `total_amount`: Total akhir yang dibayarkan (angka bulat tanpa titik/koma/Rp). Utamakan baris TOTAL / GRAND TOTAL / TOTAL BAYAR / TUNAI / DEBIT.
4. `category`: Kategori pengeluaran yang paling cocok dari daftar ini:
   ["Makanan & Minuman", "Belanja", "Transportasi", "Kesehatan", "Tagihan & Utilitas", "Hiburan", "Rumah Tangga", "Perawatan Diri", "Lain-lain"].
5. `items`: Daftar barang belanjaan yang dibeli. Tiap barang harus memiliki:
   - `item_name`: Nama barang/produk (rapi dan jelas)
   - `quantity`: Jumlah unit/kuantitas (angka integer, default 1)
   - `unit_price`: Harga satuan per barang (angka bulat)
   - `subtotal`: Total harga untuk barang tersebut (`quantity * unit_price`, angka bulat)
   Jika rincian barang sulit dibaca tapi totalnya ada, buat 1 item ringkasan dengan `subtotal` = `total_amount`.
6. `is_readable`: boolean (true jika ini gambar struk/nota dan ada informasi pembayaran; false jika foto bukan struk atau terlalu buram untuk dibaca).

Format JSON yang HARUS dikembalikan (HANYA JSON, tanpa markdown, tanpa teks pengantar):
{{
  "is_readable": true,
  "merchant": "Nama Toko",
  "date": "YYYY-MM-DD",
  "total_amount": 85000,
  "category": "Belanja",
  "items": [
    {{"item_name": "Air Mineral", "quantity": 2, "unit_price": 5000, "subtotal": 10000}},
    {{"item_name": "Roti Tawar", "quantity": 1, "unit_price": 15000, "subtotal": 15000}}
  ]
}}
"""


def _clean_json_response(text: str) -> str:
    """Membersihkan kode markdown dari respons LLM."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_receipt_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> Optional[dict]:
    """
    Kirim foto struk ke Gemini AI untuk diekstrak menjadi data terstruktur.
    Return dictionary hasil ekstraksi atau None jika gagal.
    """
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY belum diisi di .env")
        return None

    tz = ZoneInfo(TIMEZONE)
    today_str = datetime.now(tz).strftime("%Y-%m-%d")
    prompt = RECEIPT_PROMPT.format(today=today_str)

    client = genai.Client(api_key=GEMINI_API_KEY)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[image_part, prompt],
        )
    except Exception as e_primary:
        logger.warning(f"Model {GEMINI_MODEL} gagal ({e_primary}), mencoba fallback {GEMINI_FALLBACK_MODEL}")
        try:
            response = client.models.generate_content(
                model=GEMINI_FALLBACK_MODEL,
                contents=[image_part, prompt],
            )
        except Exception as e_secondary:
            logger.error(f"Semua model Gemini gagal untuk ekstraksi struk: {e_secondary}")
            return None

    try:
        raw_text = _clean_json_response(response.text)
        data = json.loads(raw_text)

        if not data.get("is_readable", False):
            logger.info("Gemini mendeteksi gambar tidak terbaca sebagai struk.")
            return {"is_readable": False}

        # Validasi minimal
        total = data.get("total_amount")
        if not total or float(total) <= 0:
            logger.warning("Struk tidak memiliki total yang valid.")
            return None

        # Normalisasi tipe data
        data["total_amount"] = int(float(total))
        if not data.get("date"):
            data["date"] = today_str

        # Pastikan items memiliki struktur konsisten
        cleaned_items = []
        for it in data.get("items", []):
            try:
                name = str(it.get("item_name", "Barang")).strip()
                qty = int(it.get("quantity", 1))
                if qty <= 0:
                    qty = 1
                price = int(float(it.get("unit_price", 0)))
                sub = int(float(it.get("subtotal", qty * price)))
                if sub <= 0 and price > 0:
                    sub = qty * price
                cleaned_items.append({
                    "item_name": name,
                    "quantity": qty,
                    "unit_price": price,
                    "subtotal": sub,
                })
            except (ValueError, TypeError):
                continue

        if not cleaned_items:
            cleaned_items.append({
                "item_name": f"Belanja di {data.get('merchant', 'Toko')}",
                "quantity": 1,
                "unit_price": data["total_amount"],
                "subtotal": data["total_amount"],
            })

        data["items"] = cleaned_items
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Gagal parse JSON dari respons Gemini: {e}\nRaw: {response.text}")
        return None
    except Exception as e:
        logger.error(f"Error saat memproses struk: {e}")
        return None


def format_receipt_preview(receipt_data: dict) -> str:
    """Format preview struk belanja untuk konfirmasi Telegram."""
    merchant = receipt_data.get("merchant", "Toko")
    date_display = format_date(receipt_data.get("date", ""))
    total_str = format_currency(receipt_data.get("total_amount", 0))
    cat = receipt_data.get("category", "Belanja")
    acc = receipt_data.get("account") or "_(Belum dipilih)_"

    lines = [
        "🧾 *Struk Belanja Terdeteksi*\n",
        f"• *Merchant:* {merchant}",
        f"• *Tanggal:* {date_display}",
        f"• *Kategori:* {cat}",
        f"• *Akun:* {acc}",
        f"• *Total Bayar:* {total_str}\n",
        "🛒 *Rincian Barang:*"
    ]

    items = receipt_data.get("items", [])
    for idx, item in enumerate(items, 1):
        name = item.get("item_name", "Barang")
        qty = item.get("quantity", 1)
        sub = format_currency(item.get("subtotal", 0))
        lines.append(f"{idx}. {name} ({qty}x) — {sub}")

    return "\n".join(lines)


def commit_receipt(receipt_data: dict, user_id: int = 0) -> tuple[bool, str, dict]:
    """
    Menyimpan struk yang telah dikonfirmasi ke Google Sheets:
    1. Transaksi induk ke tab `Transactions`
    2. Rincian item belanja ke tab `Receipt_Items`
    """
    total = receipt_data.get("total_amount", 0)
    tx_id = f"REC-{uuid.uuid4().hex[:8].upper()}"

    tx = {
        "transaction_id": tx_id,
        "date": receipt_data.get("date"),
        "time": datetime.now(ZoneInfo(TIMEZONE)).strftime("%H:%M:%S"),
        "type": "Expense",
        "category": receipt_data.get("category", "Belanja"),
        "description": f"Belanja di {receipt_data.get('merchant', 'Toko')}",
        "amount": total,
        "payment_method": receipt_data.get("account", "Cash"),
        "account": receipt_data.get("account", "Cash"),
        "merchant": receipt_data.get("merchant", ""),
        "source": "Receipt",
        "status": "Confirmed",
    }

    # 1. Simpan transaksi utama
    ok, mode, saved_tx = commit_transaction(tx, user_id=user_id)
    if not ok:
        return False, mode, tx

    # 2. Simpan rincian barang ke tab Receipt_Items
    items_to_save = []
    for it in receipt_data.get("items", []):
        items_to_save.append({
            "item_id": f"ITM-{uuid.uuid4().hex[:8].upper()}",
            "transaction_id": tx_id,
            "item_name": it.get("item_name", "Barang"),
            "quantity": str(it.get("quantity", 1)),
            "unit_price": str(it.get("unit_price", 0)),
            "subtotal": str(it.get("subtotal", 0)),
        })

    if items_to_save:
        try:
            client = get_client()
            client.append_receipt_items(items_to_save)
            logger.info(f"{len(items_to_save)} receipt items disimpan ke Sheets untuk TX {tx_id}")
        except Exception as e:
            logger.error(f"Gagal simpan receipt items ke Sheets: {e}")

    return True, mode, saved_tx

