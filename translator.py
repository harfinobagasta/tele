"""
Modul Translator Otomatis: Mandarin/Cina/Lainnya -> Bahasa Inggris.
Menggunakan multi-backend (Google Translate gtx + MyMemory) tanpa perlu API key.
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Optional

try:
    from deep_translator import MyMemoryTranslator
except ImportError:
    MyMemoryTranslator = None

log = logging.getLogger("translator")


def _translate_google_gtx(text: str) -> Optional[str]:
    """Translate menggunakan endpoint Google Translate public gtx."""
    try:
        encoded = urllib.parse.quote(text)
        url = (
            f"https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl=auto&tl=en&dt=t&q={encoded}"
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # Format data[0] adalah list of [translated_chunk, original_chunk, ...]
            if data and isinstance(data, list) and data[0]:
                translated_parts = [
                    part[0] for part in data[0] if part and part[0] is not None
                ]
                return "".join(translated_parts)
    except Exception as e:
        log.warning(f"Google gtx translate gagal: {e}")
    return None


def _translate_mymemory(text: str) -> Optional[str]:
    """Fallback translator menggunakan MyMemory."""
    if not MyMemoryTranslator:
        return None
    try:
        # MyMemory works best on chunks <= 500 chars
        chunks = [text[i : i + 450] for i in range(0, len(text), 450)]
        results = []
        for ch in chunks:
            res = MyMemoryTranslator(source="auto", target="en").translate(ch)
            results.append(res)
        return " ".join(results)
    except Exception as e:
        log.warning(f"MyMemory translate gagal: {e}")
    return None


def translate_to_english(text: Optional[str]) -> Optional[str]:
    """
    Menerjemahkan teks (Mandarin, Cina, atau bahasa lain) ke Bahasa Inggris.
    Jika teks sudah dalam bahasa Inggris atau kosong, akan tetap utuh.
    """
    if not text or not text.strip():
        return text

    # Cek apakah ada karakter non-ASCII (seperti Hanzi Cina/Mandarin)
    has_non_ascii = any(ord(c) > 127 for c in text)

    # Coba Google gtx dulu
    translated = _translate_google_gtx(text)
    if translated and translated.strip():
        return translated

    # Fallback ke MyMemory jika ada non-ASCII
    if has_non_ascii:
        fallback = _translate_mymemory(text)
        if fallback and fallback.strip():
            return fallback

    # Jika semua gagal, kembalikan teks asli agar tidak hilang konten
    return text
