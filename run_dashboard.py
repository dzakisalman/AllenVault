"""
run_dashboard.py
Script untuk menjalankan AllenVault Web Dashboard di komputer lokal.
Membuka browser otomatis ke http://127.0.0.1:8000.
"""

import sys
import time
import webbrowser
import threading
import uvicorn

def open_browser():
    time.sleep(1.2)
    url = "http://127.0.0.1:8000"
    print(f"\n🌐 Membuka browser: {url} ...\n")
    webbrowser.open(url)

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Memulai AllenVault Web Dashboard...")
    print("📍 URL: http://127.0.0.1:8000")
    print("Tekan Ctrl+C untuk menghentikan server.")
    print("=" * 60)

    # Buka browser di background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Jalankan server Uvicorn
    uvicorn.run("api.index:app", host="127.0.0.1", port=8000, reload=False)

