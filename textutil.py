"""Text helpers: tidy what comes in from the MUSH and what goes back out."""
import re
import unicodedata

_PUNCT = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2013": "-", "\u2014": "--", "\u2015": "--",
    "\u2026": "...", "\u00a0": " ", "\u2022": "-",
}
_PUNCT_TABLE = str.maketrans(_PUNCT)

# Characters the MUSH could treat as softcode. Removed from every reply.
_UNSAFE_TABLE = str.maketrans("", "", "$%[]{}#\\")

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_input(value):
    """Player/context text -> one tidy line."""
    text = str(value if value is not None else "").translate(_PUNCT_TABLE)
    text = _CONTROL.sub(" ", text.replace("\n", " ").replace("\t", " "))
    return re.sub(r" {2,}", " ", text).strip()


def clean_reply(text, ascii_only=True, max_chars=1500):
    """Model output -> text that is safe and tidy to emit in a MUSH."""
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate(_PUNCT_TABLE)
    if ascii_only:
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = _CONTROL.sub("", text)
    text = text.replace("*", "")                    # no markdown / asterisk actions
    text = text.replace("&", " and ").translate(_UNSAFE_TABLE)
    lines = [re.sub(r"[ \t]{2,}", " ", ln).strip() for ln in text.split("\n")]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if max_chars and len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].rstrip(",;:-") + "..."
    return text
