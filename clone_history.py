"""
╔══════════════════════════════════════════════════════╗
║  HISTORY CLONER + AUTO TRANSLATOR (1 MONTH FILTER)   ║
║  - Filter: Hanya menyalin pesan 30 hari terakhir     ║
║  - Terjemahan Otomatis: Mandarin/Cina -> English     ║
║  - Preservasi Hyperlink & Referral Links Asli (HTML) ║
║  - Urutan: Terlama ke Terbaru (kronologis)           ║
╚══════════════════════════════════════════════════════╝
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from pyrogram import Client, enums
from pyrogram.types import Message
from pyrogram.errors import FloodWait, RPCError

from translator import translate_to_english, format_html_and_translate

# ─── Logging ─────────────────────────────────────────
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            LOG_DIR / f"history_{datetime.now():%Y%m%d}.log",
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("history")

# ─── Config ──────────────────────────────────────────
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE_NUMBER", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
DEST_CHANNEL = os.getenv("DEST_CHANNEL", "")
SOURCE_CHANNELS_RAW = os.getenv("SOURCE_CHANNELS", "pk_fns,pk_oa")
SOURCE_CHANNELS = [ch.strip() for ch in SOURCE_CHANNELS_RAW.split(",") if ch.strip()]

HISTORY_DAYS = int(os.getenv("HISTORY_DAYS", "30"))

if SESSION_STRING:
    app = Client(
        name="channel_cloner",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True,
    )
else:
    app = Client(
        name="channel_cloner",
        api_id=API_ID,
        api_hash=API_HASH,
        phone_number=PHONE,
        workdir=str(Path(__file__).parent),
    )


async def send_single_message_translated(dest_id: int, msg: Message) -> bool:
    for attempt in range(3):
        try:
            # 1. Pesan teks murni dengan format/link
            if msg.text:
                html_en = format_html_and_translate(msg.text, msg.entities)
                if len(html_en) > 4000:
                    chunks = [html_en[i:i+4000] for i in range(0, len(html_en), 4000)]
                    for chunk in chunks:
                        await app.send_message(
                            dest_id,
                            chunk,
                            parse_mode=enums.ParseMode.HTML,
                            disable_web_page_preview=False,
                        )
                else:
                    await app.send_message(
                        dest_id,
                        html_en,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=False,
                    )
                return True

            # 2. Pesan media
            elif (
                msg.photo
                or msg.video
                or msg.document
                or msg.audio
                or msg.animation
                or msg.voice
                or msg.video_note
            ):
                caption_en = None
                overflow_text = None
                if msg.caption:
                    caption_en = format_html_and_translate(msg.caption, msg.caption_entities)
                    if len(caption_en) > 1024:
                        overflow_text = caption_en
                        caption_en = caption_en[:1020] + "..."

                copied = await msg.copy(
                    dest_id,
                    caption=caption_en,
                    parse_mode=enums.ParseMode.HTML if caption_en else None,
                )

                if overflow_text and copied:
                    reply_id = copied.id if hasattr(copied, "id") else None
                    await app.send_message(
                        dest_id,
                        f"📄 Full Translation:\n\n{overflow_text}",
                        parse_mode=enums.ParseMode.HTML,
                        reply_to_message_id=reply_id,
                    )
                return True

            # 3. Poll
            elif msg.poll:
                q_en = translate_to_english(msg.poll.question)
                opts_en = [translate_to_english(opt.text) for opt in msg.poll.options]
                await app.send_poll(
                    dest_id, question=q_en, options=opts_en, is_anonymous=msg.poll.is_anonymous
                )
                return True
            else:
                await msg.copy(dest_id)
                return True

        except FloodWait as e:
            log.warning(f"⏳ FloodWait: menunggu {e.value} detik...")
            await asyncio.sleep(e.value + 1)
        except Exception as e:
            log.warning(f"⚠️ Gagal salin pesan ID {msg.id} (attempt {attempt+1}): {e}")
            await asyncio.sleep(1)

    return False


async def clone_channel_history(source: str, dest_id: int, cutoff_date: datetime) -> dict:
    try:
        if source.lstrip("-").isdigit():
            chat = await app.get_chat(int(source))
        else:
            chat = await app.get_chat(source)
    except Exception as e:
        log.error(f"❌ Gagal akses @{source}: {e}")
        return {"source": source, "total": 0, "forwarded": 0, "failed": 0}

    source_name = chat.title or source
    log.info("")
    log.info("=" * 60)
    log.info(f"📡 Mengumpulkan pesan dari: {source_name} (@{source})")
    log.info(f"   Batas waktu: sejak {cutoff_date.strftime('%Y-%m-%d %H:%M:%S UTC')} (30 hari terakhir)")
    log.info("=" * 60)

    matched_messages: list[Message] = []
    total_scanned = 0

    async for msg in app.get_chat_history(chat.id):
        total_scanned += 1
        msg_date = msg.date
        if msg_date.tzinfo is None:
            msg_date = msg_date.replace(tzinfo=timezone.utc)

        if msg_date < cutoff_date:
            break

        if msg.text or msg.media or msg.poll:
            matched_messages.append(msg)

        if total_scanned % 100 == 0:
            log.info(f"   ... {total_scanned} pesan dipindai, {len(matched_messages)} masuk kriteria 1 bulan")

    matched_messages.reverse()
    total = len(matched_messages)
    log.info(f"📊 Total pesan 1 bulan terakhir yang akan disalin: {total}")

    forwarded = 0
    failed = 0

    for i, msg in enumerate(matched_messages, 1):
        ok = await send_single_message_translated(dest_id, msg)
        if ok:
            forwarded += 1
        else:
            failed += 1

        if i % 25 == 0 or i == total:
            pct = (i / total) * 100
            log.info(
                f"   [{i}/{total}] {pct:.1f}% — "
                f"✅ {forwarded} disalin & diterjemahkan, ❌ {failed} gagal"
            )

        await asyncio.sleep(0.8)

    return {
        "source": source_name,
        "total": total,
        "forwarded": forwarded,
        "failed": failed,
    }


async def main() -> None:
    if API_ID == 0 or not API_HASH or not DEST_CHANNEL:
        log.error("❌ Konfigurasi belum lengkap! Periksa file .env.")
        sys.exit(1)

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)

    log.info("=" * 60)
    log.info(f"  TELEGRAM HISTORY CLONER ({HISTORY_DAYS} HARI TERAKHIR)")
    log.info(f"  Target Salin: Mulai {cutoff_date.strftime('%Y-%m-%d')} s/d sekarang")
    log.info("=" * 60)

    async with app:
        try:
            if DEST_CHANNEL.lstrip("-").isdigit():
                dest_id = int(DEST_CHANNEL)
            else:
                dest_chat = await app.get_chat(DEST_CHANNEL)
                dest_id = dest_chat.id
            log.info(f"📌 Channel tujuan: {DEST_CHANNEL} (ID: {dest_id})")
        except Exception as e:
            log.error(f"❌ Gagal akses channel tujuan '{DEST_CHANNEL}': {e}")
            sys.exit(1)

        results = []
        for source in SOURCE_CHANNELS:
            result = await clone_channel_history(source, dest_id, cutoff_date)
            results.append(result)

        log.info("")
        log.info("=" * 60)
        log.info("  📊 HASIL AKHIR CLONE HISTORY (1 BULAN)")
        log.info("=" * 60)
        total_all = sum(r["total"] for r in results)
        fwd_all = sum(r["forwarded"] for r in results)
        fail_all = sum(r["failed"] for r in results)
        for r in results:
            log.info(
                f"  📡 {r['source']}: {r['forwarded']}/{r['total']} berhasil disalin ({r['failed']} gagal)"
            )
        log.info(f"  ─────────────────────────────")
        log.info(f"  TOTAL: {fwd_all}/{total_all} disalin ke {DEST_CHANNEL}")
        log.info("=" * 60)


if __name__ == "__main__":
    app.run(main())
