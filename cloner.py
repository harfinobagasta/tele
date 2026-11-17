"""
╔══════════════════════════════════════════════════════╗
║  TELEGRAM CHANNEL CLONER + AUTO TRANSLATOR           ║
║  - Sumber: @pk_fns, @pk_oa                           ║
║  - Terjemahan Otomatis: Mandarin/Cina -> English     ║
║  - Support: PC Lokal & GitHub Actions 24/7           ║
║  - Auto-retrigger sebelum limit 6 jam GitHub selesai ║
╚══════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import asyncio
import logging
import urllib.request
import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import (
    FloodWait,
    ChatWriteForbidden,
    MessageIdInvalid,
    RPCError,
)

from translator import translate_to_english

# ─── Logging Setup ───────────────────────────────────
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            LOG_DIR / f"cloner_{datetime.now():%Y%m%d}.log",
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("cloner")

# ─── Load Config ─────────────────────────────────────
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE_NUMBER", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
DEST_CHANNEL = os.getenv("DEST_CHANNEL", "")
SOURCE_CHANNELS_RAW = os.getenv("SOURCE_CHANNELS", "pk_fns,pk_oa")

# GitHub Actions auto-retrigger config
IS_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"
GH_TOKEN = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN", "")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "")
GITHUB_REF_NAME = os.getenv("GITHUB_REF_NAME", "main")
WORKFLOW_FILE = os.getenv("WORKFLOW_FILE", "cloner.yml")
# Batas waktu jalan di GitHub Actions: default 330 menit (5.5 jam, aman sebelum 6 jam)
MAX_RUNTIME_MINUTES = int(os.getenv("MAX_RUNTIME_MINUTES", "330"))

SOURCE_CHANNELS: list[str] = [
    ch.strip() for ch in SOURCE_CHANNELS_RAW.split(",") if ch.strip()
]


def validate_config() -> None:
    errors = []
    if API_ID == 0:
        errors.append("API_ID belum diisi di .env atau GitHub Secrets")
    if not API_HASH:
        errors.append("API_HASH belum diisi di .env atau GitHub Secrets")
    if not DEST_CHANNEL:
        errors.append("DEST_CHANNEL belum diisi di .env atau GitHub Secrets")
    if not SOURCE_CHANNELS:
        errors.append("SOURCE_CHANNELS kosong di .env atau GitHub Secrets")

    # Jika di GitHub Actions, SESSION_STRING wajib ada (karena tidak bisa input OTP terminal)
    if IS_GITHUB_ACTIONS and not SESSION_STRING:
        errors.append(
            "Di GitHub Actions, SESSION_STRING wajib diisi di GitHub Secrets!\n"
            "Jalankan 'python generate_session.py' di PC lokal untuk membuatnya."
        )

    if errors:
        for e in errors:
            log.error(f"❌ {e}")
        sys.exit(1)


# ─── Initialize Pyrogram Client ───────────────────────
if SESSION_STRING:
    log.info("🔑 Login menggunakan SESSION_STRING (mode headless)")
    app = Client(
        name="channel_cloner",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True,
    )
else:
    log.info("💻 Login menggunakan file session lokal")
    app = Client(
        name="channel_cloner",
        api_id=API_ID,
        api_hash=API_HASH,
        phone_number=PHONE,
        workdir=str(Path(__file__).parent),
    )


# ─── Statistik ───────────────────────────────────────
class Stats:
    def __init__(self):
        self.forwarded = 0
        self.failed = 0
        self.translated = 0
        self.started_at = datetime.now()

    def report(self) -> str:
        uptime = datetime.now() - self.started_at
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return (
            f"📊 Statistik Operasional:\n"
            f"  ✅ Dikirim ke tujuan: {self.forwarded}\n"
            f"  🌐 Diterjemahkan ke English: {self.translated}\n"
            f"  ❌ Gagal: {self.failed}\n"
            f"  ⏱️ Uptime: {hours}j {minutes}m {seconds}d"
        )


stats = Stats()
source_chat_ids: list[int] = []
dest_chat_id: int = 0


# ─── Resolve Channel IDs ─────────────────────────────
async def resolve_channels() -> None:
    global dest_chat_id
    try:
        if DEST_CHANNEL.lstrip("-").isdigit():
            dest_chat_id = int(DEST_CHANNEL)
        else:
            dest_chat = await app.get_chat(DEST_CHANNEL)
            dest_chat_id = dest_chat.id
        log.info(f"📌 Channel tujuan: {DEST_CHANNEL} (ID: {dest_chat_id})")
    except Exception as e:
        log.error(f"❌ Gagal resolve channel tujuan '{DEST_CHANNEL}': {e}")
        sys.exit(1)

    for ch in SOURCE_CHANNELS:
        try:
            if ch.lstrip("-").isdigit():
                chat_id = int(ch)
            else:
                chat = await app.get_chat(ch)
                chat_id = chat.id
            source_chat_ids.append(chat_id)
            log.info(f"📡 Channel sumber: @{ch} (ID: {chat_id})")
        except Exception as e:
            log.warning(f"⚠️ Gagal resolve channel sumber '@{ch}': {e}")

    if not source_chat_ids:
        log.error("❌ Tidak ada channel sumber yang berhasil di-resolve!")
        sys.exit(1)


# ─── Kirim Pesan dengan Terjemahan Bahasa Inggris ─────
async def copy_with_translation(msg: Message) -> bool:
    """
    Menyalin konten pesan ke channel tujuan dengan teks/caption
    diterjemahkan secara otomatis ke Bahasa Inggris.
    """
    for attempt in range(3):
        try:
            # 1. Pesan hanya teks biasa
            if msg.text:
                translated_text = translate_to_english(msg.text)
                if translated_text != msg.text:
                    stats.translated += 1
                await app.send_message(
                    chat_id=dest_chat_id,
                    text=translated_text,
                    disable_web_page_preview=False,
                )
                return True

            # 2. Pesan media (foto, video, dokumen, audio, animasi)
            elif (
                msg.photo
                or msg.video
                or msg.document
                or msg.audio
                or msg.animation
                or msg.voice
                or msg.video_note
            ):
                new_caption = None
                if msg.caption:
                    new_caption = translate_to_english(msg.caption)
                    if new_caption != msg.caption:
                        stats.translated += 1

                # Salin media dengan caption baru dalam bahasa Inggris
                await msg.copy(
                    chat_id=dest_chat_id,
                    caption=new_caption,
                )
                return True

            # 3. Pesan Poll
            elif msg.poll:
                q_en = translate_to_english(msg.poll.question)
                opts_en = [translate_to_english(opt.text) for opt in msg.poll.options]
                stats.translated += 1
                await app.send_poll(
                    chat_id=dest_chat_id,
                    question=q_en,
                    options=opts_en,
                    is_anonymous=msg.poll.is_anonymous,
                )
                return True

            # 4. Tipe lainnya (sticker, location, contact, dsb)
            else:
                await msg.copy(chat_id=dest_chat_id)
                return True

        except FloodWait as e:
            wait_time = e.value
            log.warning(f"⏳ FloodWait: menunggu {wait_time} detik...")
            await asyncio.sleep(wait_time + 1)
        except ChatWriteForbidden:
            log.error("❌ Akun tidak memiliki izin menulis di channel tujuan! Jadikan admin.")
            return False
        except MessageIdInvalid:
            log.warning("⚠️ Pesan telah dihapus dari channel sumber sebelum diproses.")
            return False
        except RPCError as e:
            log.warning(f"⚠️ RPC Error (attempt {attempt+1}): {e}")
            await asyncio.sleep(2 ** attempt)

    return False


# ─── Event Handlers ───────────────────────────────────
@app.on_message(filters.channel)
async def on_new_channel_message(client: Client, message: Message) -> None:
    if message.chat.id not in source_chat_ids:
        return

    src_name = message.chat.title or message.chat.username or str(message.chat.id)
    log.info(f"📥 [{src_name}] Pesan baru terdeteksi (ID: {message.id})")

    success = await copy_with_translation(message)
    if success:
        stats.forwarded += 1
        log.info(f"  ✅ Berhasil disalin & diterjemahkan (Total: {stats.forwarded})")
    else:
        stats.failed += 1
        log.warning(f"  ❌ Gagal menyalin pesan (Total gagal: {stats.failed})")


@app.on_edited_message(filters.channel)
async def on_edited_channel_message(client: Client, message: Message) -> None:
    if message.chat.id not in source_chat_ids:
        return

    src_name = message.chat.title or message.chat.username or str(message.chat.id)
    log.info(f"✏️ [{src_name}] Pesan diedit (ID: {message.id}) — mengirim pembaruan")

    success = await copy_with_translation(message)
    if success:
        stats.forwarded += 1
        log.info(f"  ✅ Versi terupdate berhasil dikirim ke channel tujuan.")


# ─── GitHub Actions Self-Retrigger Mechanism ─────────
def trigger_next_github_run() -> bool:
    """
    Memanggil GitHub API workflow_dispatch untuk memulai run baru
    sebelum run yang sekarang habis masa 6 jam.
    """
    if not GH_TOKEN or not GITHUB_REPOSITORY:
        log.warning("⚠️ GH_TOKEN atau GITHUB_REPOSITORY tidak ditemukan, skip auto-retrigger API.")
        return False

    url = (
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
        f"/actions/workflows/{WORKFLOW_FILE}/dispatches"
    )
    payload = json.dumps({"ref": GITHUB_REF_NAME}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {GH_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "Telegram-Cloner-AutoRetrigger",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (204, 200, 201):
                log.info("🚀 Berhasil men-trigger workflow GitHub Actions baru!")
                return True
            log.warning(f"Respon trigger GitHub API: status {resp.status}")
    except Exception as e:
        log.error(f"❌ Gagal auto-trigger run baru di GitHub: {e}")
    return False


async def runtime_watcher(stop_event: asyncio.Event) -> None:
    """
    Memantau runtime di GitHub Actions.
    Jika mendekati limit (misal 5.5 jam), trigger run baru lalu hentikan proses ini.
    """
    if not IS_GITHUB_ACTIONS:
        return

    limit_seconds = MAX_RUNTIME_MINUTES * 60
    log.info(
        f"⏱️ GitHub Actions Watcher aktif: akan re-trigger otomatis setelah {MAX_RUNTIME_MINUTES} menit (5.5 jam)."
    )

    start = time.time()
    while not stop_event.is_set():
        await asyncio.sleep(60)
        elapsed = time.time() - start
        if elapsed >= limit_seconds:
            log.info("⏰ Waktu runtime 5.5 jam tercapai! Memulai regenerasi workflow...")
            trigger_next_github_run()
            # Beri jeda 10 detik agar workflow baru sempat initialized di GitHub
            await asyncio.sleep(10)
            stop_event.set()
            break


# ─── Main Program ─────────────────────────────────────
async def main() -> None:
    validate_config()

    log.info("=" * 60)
    log.info("  TELEGRAM CLONER & AUTO-TRANSLATOR (CHINESE -> ENGLISH)")
    log.info("=" * 60)

    stop_event = asyncio.Event()

    async with app:
        await resolve_channels()

        log.info("")
        log.info("🟢 Monitoring aktif untuk channel:")
        for i, ch in enumerate(SOURCE_CHANNELS):
            log.info(f"   {i+1}. @{ch}")
        log.info(f"   ↳ Konten diterjemahkan ke English -> {DEST_CHANNEL}")
        log.info("")

        # Jalankan watcher runtime jika di GitHub Actions
        watcher_task = asyncio.create_task(runtime_watcher(stop_event))

        try:
            await stop_event.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            watcher_task.cancel()

    log.info("")
    log.info(stats.report())
    log.info("🛑 Proses cloner dihentikan dengan aman.")


if __name__ == "__main__":
    app.run(main())
