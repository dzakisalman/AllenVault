"""
integrations/ai_client.py
Gemini AI client untuk parsing transaksi dari teks natural.
Fallback ke regex parser jika API key tidak tersedia.
"""

import json
import logging
import re
from typing import Optional

from config import GEMINI_API_KEY, TIMEZONE
from utils.parser import (
    parse_transaction_text as regex_parse,
    parse_date_from_text,
    get_today,
    get_now_time,
)

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_FALLBACK_MODEL = "gemini-3.8-flash"

EXPENSE_CATEGORIES = [
    "Makanan & Minuman", "Transportasi", "Belanja", "Kesehatan",
    "Hiburan", "Tagihan & Utilitas", "Pendidikan", "Perawatan Diri",
    "Rumah Tangga", "Lain-lain",
]
INCOME_CATEGORIES = [
    "Gaji", "Freelance", "Bisnis", "Investasi", "Hadiah", "Lain-lain",
]

PARSE_PROMPT = """Kamu adalah parser transaksi keuangan pribadi Indonesia.
Pengguna bisa mengirim SATU transaksi atau BANYAK transaksi (batch) dalam satu pesan (dipisahkan koma, kata 'dan', '&', titik koma, atau baris baru).
Ekstrak SEMUA transaksi yang valid ke dalam array 'transactions'.

Tanggal hari ini: {today}
Teks: "{text}"

Aturan penting:
1. Tanggal hari ini adalah {today}.
   - Jika teks menyebut kata 'kemarin' -> date = 1 hari sebelum {today}
   - Jika teks menyebut 'kemarin lusa' atau '2 hari lalu' -> date = 2 hari sebelum {today}
   - Jika teks menyebut 'X hari lalu' -> date = X hari sebelum {today}
   - Jika menyebut tanggal tertentu (contoh: 'tgl 15 nov', '17/11/2026') -> date = tanggal tersebut (YYYY-MM-DD)
   - Jika TIDAK menyebut keterangan hari/tanggal -> date = "{today}"
2. Normalisasi akun:
   - 'spay' / 'shopeepay' -> 'ShopeePay'
   - 'bca' -> 'BCA'
   - 'mandiri' -> 'Mandiri'
   - 'bni' -> 'BNI'
   - 'bri' -> 'BRI'
   - 'jago' -> 'Jago'
   - 'gopay' -> 'GoPay'
   - 'dana' -> 'DANA'
   - 'ovo' -> 'OVO'
   - 'cash' / 'tunai' -> 'Cash'
3. Akun pada transaksi beruntun (batch):
   - Jika sebuah transaksi dalam daftar tidak menyebutkan akun, tetapi transaksi sebelumnya dalam kelompok tersebut menyebutkan akun (contoh: 'soto 20rb spay, bakso 15rb'), gunakan akun yang sama ('ShopeePay').
   - Jika sama sekali tidak ada akun dalam pesan, gunakan null.
4. Kategori:
   - Untuk Expense dari: [{expense_cats}]
   - Untuk Income dari: [{income_cats}]
5. amount HARUS angka integer positif tanpa titik/koma/Rp.

Kembalikan HANYA JSON tanpa markdown dengan struktur:
{{
  "transactions": [
    {{
      "type": "Expense" | "Income" | "Transfer",
      "amount": <angka bulat>,
      "description": "<nama barang/tujuan>",
      "merchant": "<nama toko jika ada, null jika tidak>",
      "account": "<nama akun atau null>",
      "from_account": "<akun asal jika transfer, null jika bukan>",
      "to_account": "<akun tujuan jika transfer, null jika bukan>",
      "category": "<kategori>",
      "date": "YYYY-MM-DD"
    }}
  ]
}}"""


def _clean_json_response(text: str) -> str:
    """Bersihkan respons Gemini dari markdown code block jika ada."""
    text = text.strip()
    # Hapus ```json ... ``` wrapper
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def parse_with_gemini(text: str) -> list[dict]:
    """
    Parse teks transaksi (single atau batch) menggunakan Gemini AI.
    Return list of dicts transaksi yang valid, atau list kosong jika gagal.
    """
    if not GEMINI_API_KEY:
        return []

    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = PARSE_PROMPT.format(
            text=text,
            today=get_today(),
            expense_cats=", ".join(EXPENSE_CATEGORIES),
            income_cats=", ".join(INCOME_CATEGORIES),
        )

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
        except Exception as e_primary:
            logger.warning(f"Model {GEMINI_MODEL} gagal ({e_primary}), mencoba fallback {GEMINI_FALLBACK_MODEL}")
            response = client.models.generate_content(
                model=GEMINI_FALLBACK_MODEL,
                contents=prompt,
            )

        raw = _clean_json_response(response.text)
        data = json.loads(raw)

        raw_list = []
        if isinstance(data, dict):
            if "transactions" in data and isinstance(data["transactions"], list):
                raw_list = data["transactions"]
            elif data.get("amount"):
                raw_list = [data]
        elif isinstance(data, list):
            raw_list = data

        valid_txs = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            amt = item.get("amount")
            if amt and float(amt) > 0:
                item["amount"] = int(float(amt))
                if not item.get("type"):
                    item["type"] = "Expense"
                if not item.get("date"):
                    item["date"] = parse_date_from_text(text) or get_today()
                if not item.get("time"):
                    item["time"] = get_now_time()
                item["source"] = "Text"
                item["_parser"] = "gemini"
                valid_txs.append(item)

        if valid_txs:
            logger.info(f"Gemini berhasil mengekstrak {len(valid_txs)} transaksi.")
            return valid_txs

        return []

    except json.JSONDecodeError as e:
        logger.warning(f"Gemini JSON parse error: {e}")
        return []
    except Exception as e:
        logger.warning(f"Gemini parse gagal: {e}")
        return []


def parse_transactions(text: str) -> list[dict]:
    """
    Parse teks transaksi ke daftar transaksi.
    Mendukung SATU transaksi maupun BANYAK transaksi (batch).
    Prioritas: Gemini AI → Regex fallback.
    """
    # 1. Coba dengan Gemini AI
    results = parse_with_gemini(text)
    if results:
        return results

    # 2. Fallback regex parser
    logger.info("Menggunakan regex parser (Gemini tidak tersedia/gagal)")
    lines = [line.strip() for line in re.split(r"[\n;]", text) if line.strip()]
    if not lines:
        lines = [text]

    txs = []
    for line in lines:
        parsed = regex_parse(line)
        if parsed.get("amount") and parsed["amount"] > 0:
            parsed["_parser"] = "regex"
            txs.append(parsed)

    if not txs:
        # Jika tidak ada yang lolos filter nominal, kembalikan hasil dasar regex
        single = regex_parse(text)
        single["_parser"] = "regex"
        return [single]

    return txs


def parse_transaction(text: str) -> dict:
    """Convenience helper untuk single transaction parsing."""
    txs = parse_transactions(text)
    return txs[0] if txs else regex_parse(text)

