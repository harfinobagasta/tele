"""
Modul Translator Otomatis: Mandarin/Cina/Lainnya -> Bahasa Inggris.
Mendukung:
1. Terjemahan teks murni
2. Preservasi Hyperlink Telegram (TEXT_LINK / referral link tersembunyi)
3. Preservasi format teks HTML (bold, italic, code, blockquote)
"""

import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Optional, List

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
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
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
    """Menerjemahkan teks ke Bahasa Inggris (fallback ke teks asli jika gagal)."""
    if not text or not text.strip():
        return text

    has_non_ascii = any(ord(c) > 127 for c in text)

    translated = _translate_google_gtx(text)
    if translated and translated.strip():
        return translated

    if has_non_ascii:
        fallback = _translate_mymemory(text)
        if fallback and fallback.strip():
            return fallback

    return text


def format_html_and_translate(text: Optional[str], entities: Optional[List] = None) -> Optional[str]:
    """
    Mengubah pesan Telegram beserta entities (hyperlink, bold, code)
    menjadi HTML yang diterjemahkan ke Bahasa Inggris tanpa merusak
    URL referral tersembunyi (TEXT_LINK).
    """
    if not text:
        return text

    # Jika tidak ada formatting entities, cukup terjemahkan teks biasa
    if not entities:
        return translate_to_english(text)

    # 1. Konversi pesan asli beserta entities ke HTML format
    try:
        from pyrogram.parser.html import HTML
        html_text = HTML.unparse(text, entities)
    except Exception as e:
        log.warning(f"Gagal unparse HTML entities: {e}")
        return translate_to_english(text)

    # 2. Masking link <a href="URL">ANCHOR</a> agar URL referral tidak dimodifikasi oleh translator
    link_pattern = re.compile(r'<a\s+href="([^"]+)">([\s\S]*?)</a>', re.IGNORECASE)
    placeholders = {}

    def link_replacer(m):
        idx = len(placeholders)
        token = f"ZZZLINK{idx}ZZZ"
        url = m.group(1)
        anchor = m.group(2)
        # Jika anchor bukan URL, terjemahkan juga label teksnya
        if not anchor.startswith("http://") and not anchor.startswith("https://") and not anchor.startswith("@") and not anchor.startswith("t.me"):
            tr_anchor = translate_to_english(anchor) or anchor
        else:
            tr_anchor = anchor
        placeholders[token] = f'<a href="{url}">{tr_anchor}</a>'
        return token

    masked_text = link_pattern.sub(link_replacer, html_text)

    # 3. Terjemahkan teks yang sudah dimask ke Bahasa Inggris
    translated = translate_to_english(masked_text)

    # 4. Kembalikan semua tag <a href="URL"> persis dengan URL referral aslinya
    for token, original_link in placeholders.items():
        pattern = re.compile(re.escape(token), re.IGNORECASE)
        translated = pattern.sub(original_link, translated)

    return translated
