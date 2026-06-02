"""
Client question message generator.

Produces a copy-paste-ready message from IDK (unanswered) questions
in 8 format combos: English/Hebrew x Formal/Casual x SMS/Email.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# ── Weight ordering (most → least important) ──────────────────────────
WEIGHT_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

Language = Literal["en", "he"]
Tone = Literal["formal", "casual"]
Format = Literal["sms", "email"]


@dataclass
class MessageOptions:
    language: Language = "en"
    tone: Tone = "formal"
    format: Format = "email"
    client_name: str = "client"
    sender_name: str = ""
    max_primary: int = 5


# ── Sorting ───────────────────────────────────────────────────────────

def sort_by_weight(idk_questions: dict) -> list[dict]:
    """Return IDK question dicts sorted by weight, excluding internal-only."""
    items = [v for v in idk_questions.values() if not v.get("internal_only")]
    return sorted(items, key=lambda q: WEIGHT_ORDER.get(q.get("weight", "low"), 99))


# ── Template fragments ────────────────────────────────────────────────

_GREETINGS = {
    ("en", "formal"): "Dear {name},",
    ("en", "casual"):  "Hi {name},",
    ("he", "formal"): "שלום {name},",
    ("he", "casual"):  "היי {name},",
}

_INTROS = {
    ("en", "formal", "email"): (
        "Following our conversation, I'd like to clarify a few details "
        "so I can put together an accurate quote for you."
    ),
    ("en", "formal", "sms"): "A few items I'd like to clarify:",
    ("en", "casual", "email"): (
        "Just following up on our chat — there are a few things "
        "I'd love to nail down so the quote is spot-on."
    ),
    ("en", "casual", "sms"): "Quick follow-up on a few things:",
    ("he", "formal", "email"): (
        "בעקבות שיחתנו, אשמח להבהיר מספר פרטים "
        "כדי שאוכל להכין עבורך הצעת מחיר מדויקת."
    ),
    ("he", "formal", "sms"): "מספר פרטים שאשמח להבהיר:",
    ("he", "casual", "email"): (
        "רציתי לחזור על כמה דברים מהשיחה שלנו — "
        "ככה שאוכל להכין הצעת מחיר מדויקת."
    ),
    ("he", "casual", "sms"): "המשך קצר לשיחה שלנו:",
}

_OVERFLOW_HEADERS = {
    ("en", "formal"): "Additionally, there are a few more items we'll need to discuss later:",
    ("en", "casual"):  "We'll also get to these when we chat next:",
    ("he", "formal"): "בנוסף, ישנם מספר נושאים נוספים שנצטרך לדון בהם בהמשך:",
    ("he", "casual"):  "גם על אלה נדבר בהמשך:",
}

_SIGNOFFS = {
    ("en", "formal", "email"): "Looking forward to your response.\nBest regards,\n{sender}",
    ("en", "casual", "email"):  "Let me know when you get a chance!\nCheers,\n{sender}",
    ("he", "formal", "email"): "מחכה לתשובתך.\nבברכה,\n{sender}",
    ("he", "casual", "email"):  "תעדכן/י אותי כשנוח!\n{sender}",
    ("en", "formal", "sms"): "",
    ("en", "casual", "sms"):  "",
    ("he", "formal", "sms"): "",
    ("he", "casual", "sms"):  "",
}


# ── Generator ─────────────────────────────────────────────────────────

def _question_label(q: dict, language: Language) -> str:
    if language == "he":
        return q.get("label_he") or q.get("label", "")
    return q.get("label", "")


def _format_primary(questions: list[dict], language: Language, fmt: Format) -> str:
    lines = []
    for i, q in enumerate(questions, 1):
        label = _question_label(q, language)
        if fmt == "email":
            lines.append(f"  {i}. {label}")
        else:
            lines.append(f"- {label}")
    return "\n".join(lines)


def _format_overflow(questions: list[dict], language: Language) -> str:
    lines = []
    for q in questions:
        label = _question_label(q, language)
        lines.append(f"  • {label}")
    return "\n".join(lines)


def generate_client_message(
    idk_questions: dict,
    options: MessageOptions | None = None,
    output_path: Path | None = None,
) -> str:
    """
    Build a client-facing message from IDK questions.

    Returns the message string.  Optionally writes it to *output_path*.
    """
    if options is None:
        options = MessageOptions()

    sorted_qs = sort_by_weight(idk_questions)
    if not sorted_qs:
        return ""

    lang = options.language
    tone = options.tone
    fmt = options.format
    name = options.client_name or "client"

    parts: list[str] = []

    # Greeting (email only)
    if fmt == "email":
        parts.append(_GREETINGS[(lang, tone)].format(name=name))
        parts.append("")

    # Intro
    parts.append(_INTROS[(lang, tone, fmt)])
    parts.append("")

    # Split primary / overflow
    primary = sorted_qs[: options.max_primary]
    overflow = sorted_qs[options.max_primary :]

    # Primary questions
    parts.append(_format_primary(primary, lang, fmt))

    # Overflow
    if overflow:
        parts.append("")
        parts.append(_OVERFLOW_HEADERS[(lang, tone)])
        parts.append(_format_overflow(overflow, lang))

    # Sign-off
    signoff = _SIGNOFFS.get((lang, tone, fmt), "")
    if signoff:
        sender = options.sender_name or ""
        parts.append("")
        parts.append(signoff.format(sender=sender))

    message = "\n".join(parts)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(message, encoding="utf-8")

    return message
