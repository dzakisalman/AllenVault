"""
Utils — Parser
Fungsi-fungsi untuk parsing input teks transaksi dari pengguna dalam bahasa Indonesia.
Mendukung ekstraksi nominal, tipe transaksi, kategori, akun, merchant, dan deskripsi.
"""

import re
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from config import TIMEZONE

logger = logging.getLogger(__name__)

MONTH_NAME_MAP = {
    "januari": 1, "jan": 1,
    "februari": 2, "feb": 2,
    "maret": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "agustus": 8, "ags": 8, "agu": 8,
    "september": 9, "sep": 9,
    "oktober": 10, "okt": 10,
    "november": 11, "nov": 11,
    "desember": 12, "des": 12,
}

# Daftar akun umum di Indonesia untuk pendeteksian otomatis
KNOWN_ACCOUNTS = [
    "BCA", "Mandiri", "BNI", "BRI", "CIMB", "Permata", "Danamon", "BSI",
    "Jago", "Bank Jago", "Seabank", "Blu", "Jenius", "Neo",
    "GoPay", "Gopay", "OVO", "Ovo", "DANA", "Dana", "ShopeePay", "Shopeepay", "LinkAja",
    "Cash", "Tunai", "Dompet",
]

# Keyword untuk mendeteksi jenis transaksi
INCOME_KEYWORDS = [
    "dapat", "terima", "masuk", "dapet", "income", "pemasukan",
    "gaji", "bayaran", "transfer masuk", "top up", "cashback", "thr",
    "dividen", "komisi", "bonus",
]

EXPENSE_KEYWORDS = [
    "beli", "bayar", "spend", "keluar", "pengeluaran",
    "jajan", "makan", "habis", "pakai", "pake",
    "bakmi", "kopi", "mie", "nasi", "bensin", "parkir", "rokok", "pulsa",
    "listrik", "ongkir", "gojek", "grab", "gofood", "shopeefood",
]

TRANSFER_KEYWORDS = [
    "transfer", "kirim", "pindah", "tf", "tarik tunai", "topup",
]

# Pemetaan kategori berdasarkan kata kunci
CATEGORY_KEYWORD_MAP = {
    # Expense Categories
    "Makanan & Minuman": [
        "makan", "minum", "bakmi", "mie", "nasi", "ayam", "sate", "kopi",
        "coffee", "cafe", "burger", "pizza", "boba", "warteg", "indomie",
        "roti", "martabak", "geprek", "resto", "restoran", "snack", "jajan",
        "sarapan", "lunch", "dinner", "food", "drink", "jus", "tea", "teh",
        "mcd", "kfc", "hokben", "starbucks", "janji jiwa", "fore",
    ],
    "Transportasi": [
        "bensin", "pertalite", "pertamax", "solar", "parkir", "tol",
        "gojek", "goride", "gocar", "grab", "grabcar", "grabride",
        "ojek", "krl", "mrt", "lrt", "busway", "transjakarta", "taksi",
        "tiket", "angkot", "kereta", "pesawat", "commuter",
    ],
    "Tagihan & Utilitas": [
        "listrik", "pln", "air", "pdam", "wifi", "indihome", "biznet",
        "internet", "pulsa", "kuota", "bpjs", "telkom", "iuran", "pbb",
        "langganan", "tagihan", "token listrik",
    ],
    "Kesehatan": [
        "obat", "apotek", "dokter", "klinik", "rumah sakit", "rs",
        "vitamin", "periksa", "dokter gigi", "konsultasi", "laboratorium",
        "tes darah", "swab",
    ],
    "Belanja": [
        "minimarket", "indomaret", "alfamart", "alfamidi", "supermarket",
        "baju", "pakaian", "celana", "sepatu", "tas", "belanja", "shopee",
        "tokopedia", "lazada", "tiktok shop", "mall", "hypermart",
        "superindo", "sayur", "pasar", "sembako",
    ],
    "Hiburan": [
        "bioskop", "nonton", "cinema", "xxi", "cgv", "netflix", "spotify",
        "youtube", "game", "steam", "playstation", "liburan", "hotel",
        "villa", "staycation", "karaoke", "wisata",
    ],
    "Pendidikan": [
        "buku", "kursus", "spp", "kuliah", "sekolah", "seminar", "ukt",
        "les", "bimbel", "ujian", "sertifikasi",
    ],
    "Perawatan Diri": [
        "potong rambut", "salon", "skincare", "barbershop", "gym",
        "fitness", "spa", "pijat", "massage", "facial",
    ],
    "Rumah Tangga": [
        "laundry", "sabun", "galon", "gas", "elpiji", "deterjen",
        "perabot", "alat rumah", "sapu", "pel", "tissue",
    ],
    # Income Categories
    "Gaji": ["gaji", "salary", "payroll", "upah"],
    "Freelance": ["freelance", "proyek", "project", "komisi", "fee", "side job", "klien"],
    "Bisnis": ["omset", "jualan", "laba", "keuntungan", "toko"],
    "Investasi": ["dividen", "crypto", "saham", "reksadana", "bunga", "bibit", "ajaib"],
    "Hadiah": ["hadiah", "kado", "angpao", "thr", "cashback", "bonus", "reward"],
}


def parse_amount(text: str) -> float | None:
    """
    Ekstrak jumlah uang dari teks.
    Mendukung format:
      "50rb", "50 rb", "50k", "50 k"  → 50000.0
      "25 ribu", "25ribu"            → 25000.0
      "1.5 juta", "1,5 jt"           → 1500000.0
      "Rp 85.000", "Rp85000"         → 85000.0
      "100.000", "100000"            → 100000.0
    """
    text_clean = text.lower()

    # 1. Pola: angka desimal/bulat + kata satuan (ribu/rb/k/juta/jt/miliar)
    pattern_word = r"(\d+(?:[.,]\d+)?)\s*(ribu|rb|k|juta|jt|miliar|m\b)"
    match = re.search(pattern_word, text_clean)
    if match:
        num_str = match.group(1).replace(",", ".")
        unit = match.group(2)
        try:
            val = float(num_str)
            if unit in ("ribu", "rb", "k"):
                return val * 1_000
            elif unit in ("juta", "jt", "m"):
                return val * 1_000_000
            elif unit == "miliar":
                return val * 1_000_000_000
        except ValueError:
            pass

    # 2. Pola: Rp angka (dengan titik pemisah ribuan)
    pattern_rp = r"rp\.?\s*(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+)"
    match = re.search(pattern_rp, text_clean)
    if match:
        num_str = match.group(1).replace(".", "").replace(",", ".")
        try:
            val = float(num_str)
            if val > 0:
                return val
        except ValueError:
            pass

    # 3. Pola angka ribuan biasa dengan titik (contoh: 25.000 atau 150.000)
    pattern_dotted = r"\b(\d{1,3}(?:\.\d{3})+)\b"
    match = re.search(pattern_dotted, text_clean)
    if match:
        num_str = match.group(1).replace(".", "")
        try:
            val = float(num_str)
            if val >= 100:  # Minimal 100 rupiah
                return val
        except ValueError:
            pass

    # 4. Pola angka plain (misal: 25000 atau 50000, minimal 3 digit)
    pattern_plain = r"\b(\d{3,9})\b"
    match = re.search(pattern_plain, text_clean)
    if match:
        try:
            val = float(match.group(1))
            if val >= 100:
                return val
        except ValueError:
            pass

    return None


def detect_transaction_type(text: str) -> str | None:
    """
    Deteksi jenis transaksi: Income, Expense, Transfer, atau None.
    Default ke Expense jika ada indikasi pengeluaran atau nominal tanpa kata income/transfer.
    Mengembalikan None jika teks tidak berkaitan dengan keuangan (misal: "halo bot").
    """
    text_lower = text.lower()

    if any(kw in text_lower for kw in TRANSFER_KEYWORDS):
        return "Transfer"
    if any(kw in text_lower for kw in INCOME_KEYWORDS):
        return "Income"
    if any(kw in text_lower for kw in EXPENSE_KEYWORDS):
        return "Expense"

    # Jika ada nominal terdeteksi dalam teks, asumsikan pengeluaran
    if parse_amount(text) is not None:
        return "Expense"

    return None


def detect_category(text: str, tx_type: str = "Expense") -> str | None:
    """Deteksi kategori dari kata kunci yang terdapat pada teks."""
    text_lower = text.lower()
    for cat_name, keywords in CATEGORY_KEYWORD_MAP.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                return cat_name
    return "Lain-lain"


def detect_account(text: str) -> str | None:
    """Deteksi nama akun yang disebutkan dalam teks."""
    text_lower = text.lower()
    for acc in KNOWN_ACCOUNTS:
        if re.search(r"\b" + re.escape(acc.lower()) + r"\b", text_lower):
            if acc.lower() in ("cash", "tunai", "dompet"):
                return "Cash"
            elif acc.lower() in ("bca", "bank bca"):
                return "BCA"
            elif acc.lower() in ("mandiri", "bank mandiri"):
                return "Mandiri"
            elif acc.lower() in ("gopay", "go-pay"):
                return "GoPay"
            elif acc.lower() in ("dana",):
                return "DANA"
            elif acc.lower() in ("ovo",):
                return "OVO"
            elif acc.lower() in ("shopeepay", "spay"):
                return "ShopeePay"
            elif acc.lower() in ("jago", "bank jago"):
                return "Jago"
            return acc
    return None


def detect_transfer_accounts(text: str) -> tuple[str | None, str | None]:
    """
    Deteksi akun sumber dan tujuan dari kalimat transfer.
    Contoh: "transfer 200 ribu dari BCA ke DANA"
    """
    pattern_from_to = r"(?:dari|from)\s+([a-zA-Z0-9_\-]+)\s+(?:ke|to)\s+([a-zA-Z0-9_\-]+)"
    m = re.search(pattern_from_to, text, re.IGNORECASE)
    if m:
        from_raw = m.group(1).strip()
        to_raw = m.group(2).strip()
        from_acc = detect_account(from_raw) or from_raw.upper()
        to_acc = detect_account(to_raw) or to_raw.upper()
        return from_acc, to_acc

    pattern_to_from = r"(?:ke|to)\s+([a-zA-Z0-9_\-]+).*?(?:dari|from)\s+([a-zA-Z0-9_\-]+)"
    m2 = re.search(pattern_to_from, text, re.IGNORECASE)
    if m2:
        to_raw = m2.group(1).strip()
        from_raw = m2.group(2).strip()
        from_acc = detect_account(from_raw) or from_raw.upper()
        to_acc = detect_account(to_raw) or to_raw.upper()
        return from_acc, to_acc

    # Fallback cari 2 akun pertama yang disebut
    found = []
    for acc in KNOWN_ACCOUNTS:
        if re.search(r"\b" + re.escape(acc.lower()) + r"\b", text.lower()):
            normalized = detect_account(acc) or acc
            if normalized not in found:
                found.append(normalized)
    if len(found) >= 2:
        return found[0], found[1]
    elif len(found) == 1:
        return found[0], None

    return None, None


def clean_description(text: str, amount: float | None = None) -> str:
    """
    Bersihkan teks transaksi untuk dijadikan deskripsi yang rapi.
    Menghilangkan nominal, kata depan, dan nama akun.
    """
    cleaned = text.strip()

    # Hapus prefix umum
    cleaned = re.sub(r"^(tadi|barusan|hari ini|kemarin)\s+", "", cleaned, flags=re.IGNORECASE)

    # Hapus keterangan tanggal dan waktu
    temporal_patterns = [
        r"\bkemarin\s+lusa\b",
        r"\bkemarin\b",
        r"\bsemalam\b",
        r"\btadi\s+malam\b",
        r"\b\d+\s*hari\s*lalu\b",
        r"\b(?:tgl|tanggal)?\s*\d{1,2}\s+[a-z]+(?:\s+\d{4})?\b",
        r"\b(?:tgl|tanggal)\s*\d{1,2}\b",
        r"\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b",
    ]
    for pat in temporal_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

    # Hapus bagian nominal
    patterns_to_remove = [
        r"rp\.?\s*[\d.,]+",
        r"\d+(?:[.,]\d+)?\s*(ribu|rb|k|juta|jt|miliar|m\b)",
        r"\b\d{1,3}(?:\.\d{3})+\b",
        r"\b\d{3,9}\b",
    ]
    for pat in patterns_to_remove:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

    # Hapus frasa akun: "dari BCA ke DANA", "pakai BCA", dll.
    cleaned = re.sub(r"\b(dari|from)\s+[a-zA-Z0-9_\-]+\s+(ke|to)\s+[a-zA-Z0-9_\-]+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(pakai|pake|via|lewat|dengan|menggunakan|masuk ke|masuk)\s+[a-zA-Z0-9_\-]+", "", cleaned, flags=re.IGNORECASE)

    # Hapus kata kerja awal yang tidak informatif
    cleaned = re.sub(r"^(beli|bayar|jajan|transfer|tf|dapat|terima)\s+", "", cleaned, flags=re.IGNORECASE).strip()

    # Hapus spasi berlebih dan tanda baca di ujung
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")

    # Jika setelah dibersihkan jadi kosong, fallback yang cerdas
    if not cleaned:
        cleaned = "Transaksi"

    return cleaned.capitalize()


def parse_date_from_text(text: str) -> str | None:
    """
    Ekstrak tanggal (kemarin, kemarin lusa, 3 hari lalu, atau tanggal tertentu) dari teks.
    Format pengembalian: 'YYYY-MM-DD' atau None jika tidak ditemukan.
    """
    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz)
    text_lower = text.lower()

    if re.search(r"\bkemarin lusa\b", text_lower):
        return (today - timedelta(days=2)).strftime("%Y-%m-%d")
    if re.search(r"\bkemarin\b", text_lower) or re.search(r"\bsemalam\b", text_lower):
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    m_days = re.search(r"\b(\d+)\s*hari\s*lalu\b", text_lower)
    if m_days:
        try:
            return (today - timedelta(days=int(m_days.group(1)))).strftime("%Y-%m-%d")
        except ValueError:
            pass

    m_full = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b", text_lower)
    if m_full:
        d, m, y = int(m_full.group(1)), int(m_full.group(2)), int(m_full.group(3))
        try:
            return datetime(y, m, d).strftime("%Y-%m-%d")
        except ValueError:
            pass

    m_month = re.search(r"\b(?:tgl|tanggal)?\s*(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?\b", text_lower)
    if m_month:
        day = int(m_month.group(1))
        month_str = m_month.group(2)
        year = int(m_month.group(3)) if m_month.group(3) else today.year
        if month_str in MONTH_NAME_MAP:
            try:
                return datetime(year, MONTH_NAME_MAP[month_str], day).strftime("%Y-%m-%d")
            except ValueError:
                pass

    m_tgl = re.search(r"\b(?:tgl|tanggal)\s*(\d{1,2})\b", text_lower)
    if m_tgl:
        day = int(m_tgl.group(1))
        try:
            return datetime(today.year, today.month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def get_today() -> str:
    """Return tanggal hari ini dalam format YYYY-MM-DD di timezone lokal."""
    tz = ZoneInfo(TIMEZONE)
    return datetime.now(tz).strftime("%Y-%m-%d")


def get_now_time() -> str:
    """Return waktu saat ini dalam format HH:MM:SS di timezone lokal."""
    tz = ZoneInfo(TIMEZONE)
    return datetime.now(tz).strftime("%H:%M:%S")


def parse_transaction_text(text: str) -> dict:
    """
    Parse teks transaksi informal lengkap ke dictionary transaksi.
    """
    amount = parse_amount(text)
    tx_type = detect_transaction_type(text)
    if not tx_type and amount is not None:
        tx_type = "Expense"

    category = detect_category(text, tx_type) if (tx_type and tx_type != "Transfer") else None
    account = None
    from_account = None
    to_account = None

    if tx_type == "Transfer":
        from_account, to_account = detect_transfer_accounts(text)
    else:
        account = detect_account(text)

    desc = clean_description(text, amount)
    if tx_type == "Transfer" and desc in ("Transaksi", ""):
        if from_account and to_account:
            desc = f"Transfer {from_account} ke {to_account}"
        else:
            desc = "Transfer"

    # Deteksi merchant jika deskripsi mencakup merchant populer
    merchant = None
    merchant_candidates = [
        "Indomaret", "Alfamart", "Starbucks", "KFC", "McDonalds", "McD",
        "Bakmi GM", "Fore", "Janji Jiwa", "Shopee", "Tokopedia", "Grab",
        "Gojek", "Pertamina", "Superindo",
    ]
    for m in merchant_candidates:
        if m.lower() in text.lower():
            merchant = m
            break

    result = {
        "type": tx_type,
        "amount": amount,
        "date": parse_date_from_text(text) or get_today(),
        "time": get_now_time(),
        "description": desc,
        "category": category,
        "account": account,
        "from_account": from_account,
        "to_account": to_account,
        "merchant": merchant,
        "payment_method": account,
        "source": "Text",
    }
    return result
