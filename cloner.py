"""
╔══════════════════════════════════════════════════════╗
║  TELEGRAM CHANNEL CLONER + AUTO TRANSLATOR           ║
║  - Sumber: @pk_fns, @pk_oa                           ║
║  - Terjemahan Otomatis: Mandarin/Cina -> English     ║
║  - Support: PC Lokal & GitHub Actions 24/7           ║
║  - Auto-retrigger sebelum limit 6 jam GitHub selesai ║
║  - Smart Caption Truncation (>1024 chars)            ║
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
MAX_RUNTIME_MINUTES = int(os.getenv("MAX_RUNTIME_MINUTES", "330"))

SOURCE_CHANNELS: list[str] = [
    ch.strip() for ch in SOURCE_CHANNELS_RAW.split(",") if ch.strip()
]


def validate_config() -> None:
    errors = []
    if API_ID == 0:
        errors.append("API_ID belum diisi")
    if not API_HASH:
        errors.append("API_HASH belum diisi")
    if not DEST_CHANNEL:
        errors.append("DEST_CHANNEL belum diisi")
    if not SOURCE_CHANNELS:
        errors.append("SOURCE_CHANNELS kosong")

    if IS_GITHUB_ACTIONS and not SESSION_STRING:
        errors.append("SESSION_STRING wajib diisi untuk GitHub Actions!")

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
    for attempt in range(3):
        try:
            # 1. Pesan teks
            if msg.text:
                translated_text = translate_to_english(msg.text)
                if translated_text != msg.text:
                    stats.translated += 1

                # Jika teks > 4096 (batas Telegram), kirim bertahap
                if len(translated_text) > 4000:
                    chunks = [translated_text[i:i+4000] for i in range(0, len(translated_text), 4000)]
                    for chunk in chunks:
                        await app.send_message(chat_id=dest_chat_id, text=chunk, disable_web_page_preview=False)
                else:
                    await app.send_message(chat_id=dest_chat_id, text=translated_text, disable_web_page_preview=False)
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
                overflow_text = None
                if msg.caption:
                    new_caption = translate_to_english(msg.caption)
                    if new_caption != msg.caption:
                        stats.translated += 1

                    # Handle batas caption media Telegram (1024 karakter)
                    if len(new_caption) > 1024:
                        overflow_text = new_caption
                        new_caption = new_caption[:1020] + "..."

                copied = await msg.copy(chat_id=dest_chat_id, caption=new_caption)

                # Jika ada teks panjang yang terpotong di caption, kirim pesan lanjutan
                if overflow_text and copied:
                    await app.send_message(
                        chat_id=dest_chat_id,
                        text=f"📄 Full Translation:\n\n{overflow_text}",
                        reply_to_message_id=copied.id if hasattr(copied, "id") else None,
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

            # 4. Tipe lainnya
            else:
                await msg.copy(chat_id=dest_chat_id)
                return True

        except FloodWait as e:
            log.warning(f"⏳ FloodWait: tunggu {e.value} detik...")
            await asyncio.sleep(e.value + 1)
        except ChatWriteForbidden:
            log.error("❌ Akun tidak memiliki izin menulis di channel tujuan! Jadikan admin.")
            return False
        except MessageIdInvalid:
            log.warning("⚠️ Pesan telah dihapus dari channel sumber.")
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
