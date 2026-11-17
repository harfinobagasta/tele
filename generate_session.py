"""
Generator Pyrogram String Session untuk GitHub Actions.
Jalankan file ini SEKALI di PC lokal kamu:
    python generate_session.py

Setelah login, script ini akan menghasilkan SESSION_STRING.
Salin SESSION_STRING tersebut ke GitHub Repository Secrets!
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pyrogram import Client

load_dotenv()

API_ID = os.getenv("API_ID", "")
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE_NUMBER", "")


def main():
    print("=" * 60)
    print("  TELEGRAM STRING SESSION GENERATOR")
    print("  (Untuk deploy di GitHub Actions tanpa perlu VPS)")
    print("=" * 60)

    api_id_val = API_ID
    if not api_id_val or api_id_val == "12345678" or api_id_val == "0":
        api_id_val = input("Masukkan API_ID (dari my.telegram.org): ").strip()

    api_hash_val = API_HASH
    if not api_hash_val or api_hash_val == "your_api_hash_here":
        api_hash_val = input("Masukkan API_HASH (dari my.telegram.org): ").strip()

    phone_val = PHONE
    if not phone_val or phone_val.startswith("+628xxxx"):
        phone_val = input("Masukkan Nomor HP Telegram (contoh: +628123456789): ").strip()

    if not api_id_val or not api_hash_val or not phone_val:
        print("❌ Data tidak boleh kosong!")
        sys.exit(1)

    print("\n⏳ Menghubungkan ke Telegram...")
    app = Client(
        name="session_generator",
        api_id=int(api_id_val),
        api_hash=api_hash_val,
        phone_number=phone_val,
        in_memory=True,
    )

    with app:
        session_string = app.export_session_string()

    print("\n" + "=" * 60)
    print("✅ BERHASIL! SESSION_STRING KAMU:")
    print("=" * 60)
    print(session_string)
    print("=" * 60)

    # Simpan juga ke file .env lokal agar otomatis tercatat
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        if "SESSION_STRING=" in content:
            lines = content.splitlines()
            new_lines = [
                f"SESSION_STRING={session_string}"
                if line.startswith("SESSION_STRING=")
                else line
                for line in lines
            ]
            content = "\n".join(new_lines)
        else:
            content += f"\nSESSION_STRING={session_string}\n"
        env_path.write_text(content, encoding="utf-8")
        print("\n💾 SESSION_STRING juga otomatis tersimpan di file .env lokal!")

    print("\n👉 LANGKAH SELANJUTNYA:")
    print("1. Buka repository kamu di GitHub -> Settings -> Secrets and variables -> Actions")
    print("2. Buat secret baru bernama 'SESSION_STRING' dan paste kode di atas.")
    print("3. Buat juga secret 'API_ID', 'API_HASH', 'DEST_CHANNEL', 'SOURCE_CHANNELS', dan 'GH_TOKEN'.")


if __name__ == "__main__":
    main()
