# 🚀 Panduan Menjalankan & Deploy AllenVault Web Dashboard

Dashboard web modern untuk visualisasi data keuangan AllenVault langsung dari Google Sheets.

---

## 💻 1. Menjalankan Dashboard di Komputer Lokal

Kamu bisa langsung menjalankan dashboard di komputermu dengan satu perintah:

```bash
python run_dashboard.py
```

* Browser kamu akan otomatis terbuka ke: **`http://127.0.0.1:8000`**
* Data otomatis tersinkronisasi secara langsung (*real-time*) dengan Google Sheets AllenVault.

---

## ☁️ 2. Cara Deploy Gratis ke Vercel (Online 24/7)

Vercel memungkinkan dashboard kamu online dan bisa diakses dari HP atau laptop kapan saja melalui URL gratis (misal: `https://allenvault.vercel.app`).

### Langkah 1: Push Project ke GitHub
1. Pastikan file rahasia (`.env` dan `credentials.json`) tidak ter-commit ke GitHub (sudah diatur aman di `.gitignore`).
2. Buat repositori baru di GitHub (misal: `allenvault`).
3. Push kode AllenVault ke repositori GitHub tersebut:
   ```bash
   git init
   git add .
   git commit -m "AllenVault bot & web dashboard"
   git branch -M main
   git remote add origin https://github.com/<username-kamu>/allenvault.git
   git push -u origin main
   ```

---

### Langkah 2: Hubungkan ke Vercel
1. Buka [Vercel](https://vercel.com) dan login dengan akun GitHub kamu.
2. Klik tombol **"Add New..."** ➔ **"Project"**.
3. Pilih repositori **allenvault** yang baru saja kamu buat.

---

### Langkah 3: Masukkan Environment Variables di Vercel
Di halaman konfigurasi project Vercel sebelum deploy, buka bagian **Environment Variables** dan tambahkan variabel berikut:

| Key | Value / Isi |
|---|---|
| `GOOGLE_SPREADSHEET_ID` | `1KA0IFnpjNF--QG0El9PownhonCCo3PBp0fQGvmlPYzw` |
| `TIMEZONE` | `Asia/Jakarta` |
| `GOOGLE_SERVICE_ACCOUNT_JSON_RAW` | Salin **seluruh isi teks file `credentials.json`** dan tempel di sini |

> 🔒 **Keamanan:** Memasukkan isi `credentials.json` ke *Environment Variables* Vercel adalah standar keamanan industri cloud agar private key tidak pernah bocor ke publik atau repository GitHub.

---

### Langkah 4: Klik Deploy!
1. Klik tombol **"Deploy"**.
2. Tunggu sekitar 1–2 menit hingga proses build selesai.
3. Dashboard kamu sudah aktif dan bisa langsung dibuka dari domain Vercel yang diberikan!

