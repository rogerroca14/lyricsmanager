"""Simple i18n system. Call set_language('es'|'en') at startup."""

from __future__ import annotations
from i18n.strings import STRINGS

_lang = "es"


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in STRINGS else "en"


def t(key: str) -> str:
    """Translate a key to the current language, fallback to English."""
    return STRINGS.get(_lang, {}).get(key) or STRINGS.get("en", {}).get(key, key)
