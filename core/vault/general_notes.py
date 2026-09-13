import re

# Türkçe sesli komut kalıpları
GENERAL_NOTE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"genel\s+not(lar(a|ı)?)?\s*(e|a)?\s*kle",
        r"genel\s+not(lar(a|ı)?)?\s+olarak",          # "genel not olarak ..."
        r"genel\s+nota\s+",                             # "genel nota ekle"
        r"bunu\s+genel\s+not(lar(a|ı)?)?",
        r"şunu\s+genel\s+not(lar(a|ı)?)?",
        r"genel\s+not(lar(a|ı)?)?\s*(olarak\s+)?kaydet",
        r"genel\s+not(lar(a|ı)?)?\s*(e|a)?\s*yaz",
        r"genel\s+not\s+olarak\s+.*ekle",               # "genel not olarak ... ekle"
    )
]

STRIP_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"[,.\s]*genel\s+not(lar(a|ı)?)?\s+olarak\s+şunu\s+eklemelisin[.]?",
        r"[,.\s]*genel\s+not(lar(a|ı)?)?\s+olarak\s+",
        r"[,.\s]*bunu\s+genel\s+not(lar(a|ı)?)?\s*(e|a)?\s*kle[.]?",
        r"[,.\s]*şunu\s+genel\s+not(lar(a|ı)?)?\s*(e|a)?\s*kle[.]?",
        r"[,.\s]*genel\s+not(lar(a|ı)?)?\s*(e|a)?\s*kle[.]?",
        r"[,.\s]*genel\s+not(lar(a|ı)?)?\s*(olarak\s+)?kaydet[.]?",
        r"[,.\s]*genel\s+not(lar(a|ı)?)?\s*(e|a)?\s*yaz[.]?",
        r"[,.\s]*genel\s+nota\s+",
        r"^genel\s+not(lar(a|ı)?)?\s*(e|a)?\s*kle\s*[:]\s*",
        r"[,.\s]*eklemelisin[.]?\s*$",
        r"[,.\s]*ekle[.]?\s*$",
    )
]


def is_general_note_command(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    return any(p.search(text) for p in GENERAL_NOTE_PATTERNS)


def extract_general_note(text: str) -> str:
    note = text.strip()
    for pat in STRIP_PATTERNS:
        note = pat.sub("", note).strip()
    note = note.strip(" .,-–—")
    note = re.sub(r",?\s*bunu\s*$", "", note, flags=re.IGNORECASE).strip()
    note = re.sub(r"^:\s*", "", note).strip()
    note = re.sub(r"^şunu\s+", "", note, flags=re.IGNORECASE).strip()
    return note if len(note) > 3 else text.strip()
