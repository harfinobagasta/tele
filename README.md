# 📡 Telegram Channel Cloner + Auto-Translator (24/7 GitHub Actions)

Menyalin semua konten (teks, foto, video, dokumen/file, sticker, poll) dari channel sumber secara real-time ke channel milikmu, dengan **penerjemah otomatis dari Bahasa Mandarin/Cina/Lainnya ke Bahasa Inggris**, dan **berjalan 24/7 di GitHub Actions tanpa perlu VPS**.

---

## 📌 Fitur Utama

- **Sumber Monitor:** `@pk_fns` dan `@pk_oa` (bisa ditambah di config)
- **Auto-Translate ke Bahasa Inggris:** Teks atau caption media berbahasa Mandarin/Cina otomatis diterjemahkan ke Bahasa Inggris secara instan (tanpa API key berbayar).
- **Semua Tipe Konten:** Foto resolusi penuh, video, file/dokumen, voice note, sticker, poll, dan editan pesan.
- **Gratis 24/7 via GitHub Actions (Tanpa VPS):**
  - Mengatasi batas 6 jam GitHub Actions secara otomatis: script akan men-trigger workflow baru di menit ke-330 (5.5 jam) sebelum masa jalan habis.
  - Terdapat cron watchdog otomatis setiap 5 jam sebagai pengaman cadangan.

---

## 🚀 Panduan Setup 24/7 di GitHub Actions (Tanpa VPS)

### Langkah 1: Buat `SESSION_STRING` di PC Lokal

Karena GitHub Actions berjalan tanpa antarmuka terminal (headless), login Telegram dilakukan sekali di PC untuk mendapatkan token session:

1. Buka terminal di folder project:
   ```powershell
   python generate_session.py
   ```
2. Masukkan:
   - `API_ID` & `API_HASH` (dari [my.telegram.org](https://my.telegram.org))
   - Nomor HP akun Telegram (format internasional, contoh: `+628123456789`)
   - Kode OTP Telegram yang masuk ke aplikasi Telegram kamu
3. Script akan mencetak string panjang **`SESSION_STRING`** dan otomatis menyimpannya di file `.env`.

---

### Langkah 2: Buat GitHub Personal Access Token (PAT)

Token ini diperlukan agar GitHub Actions bisa men-trigger workflow baru secara otomatis setiap 5.5 jam:

1. Buka GitHub -> Klik avatar profil (kanan atas) -> **Settings**
2. Scroll ke bawah paling kiri, klik **Developer settings** -> **Personal access tokens** -> **Tokens (classic)**
3. Klik **Generate new token (classic)**:
   - Note: `telegram-cloner-token`
   - Expiration: `No expiration`
   - Centang opsi: **`workflow`** dan **`repo`**
4. Klik **Generate token** -> **Salin token tersebut** (formatnya diawali `ghp_...`).

---

### Langkah 3: Upload Project ke GitHub

1. Buat repository baru di GitHub (bisa **Private**).
2. Jalankan perintah ini di terminal folder project:
   ```bash
   git init
   git add .
   git commit -m "feat: telegram cloner auto-translator"
   git branch -M main
   git remote add origin https://github.com/USERNAME/NAMA_REPO.git
   git push -u origin main
   ```
   *(File `.env` dan file `.session` tidak akan ter-upload karena sudah diamankan oleh `.gitignore`)*

---

### Langkah 4: Masukkan Secrets di GitHub Repository

1. Di repository GitHub kamu, buka tab **Settings** -> menu sebelah kiri **Secrets and variables** -> **Actions**.
2. Klik tombol hijau **New repository secret**, tambahkan variabel berikut satu per satu:

| Nama Secret | Nilai / Value |
|-------------|---------------|
| `API_ID` | Angka API ID dari my.telegram.org |
| `API_HASH` | String API Hash dari my.telegram.org |
| `SESSION_STRING` | String panjang hasil dari `generate_session.py` |
| `DEST_CHANNEL` | Username channel tujuan kamu (tanpa @) |
| `SOURCE_CHANNELS` | `pk_fns,pk_oa` |
| `GH_TOKEN` | Token GitHub Personal Access Token (`ghp_...`) dari Langkah 2 |

---

### Langkah 5: Aktifkan Bot

1. Buka tab **Actions** di repository GitHub kamu.
2. Di sebelah kiri, klik workflow **Telegram 24/7 Cloner & Translator**.
3. Klik menu dropdown **Run workflow** -> pilih branch `main` -> klik tombol hijau **Run workflow**.

✅ **Selesai!**
Bot akan langsung aktif memantau `@pk_fns` & `@pk_oa`. Setiap ada update teks/file/gambar berbahasa Mandarin, bot akan menerjemahkannya ke Bahasa Inggris dan langsung mengirimkannya ke channel tujuan kamu. Setiap 5.5 jam, bot akan auto-retrigger sendiri agar tetap berjalan tanpa pernah mati.

---

## 💻 Menjalankan di Komputer Lokal (Alternatif)

Jika ingin menjalankan langsung di laptop/PC:
```powershell
# 1. Jalankan monitoring real-time
python cloner.py

# 2. Atau jika ingin menyalin riwayat pesan lama yang sudah ada sebelumnya:
python clone_history.py
```
