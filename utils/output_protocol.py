"""Parser for the fixed dollar-separated chat bubble protocol."""

import re
import unicodedata

# Recognize a single suffix, including modifiers, joined emoji and flags.
_EMOJI_BASE = (
    r"[\u00a9\u00ae\u203c\u2049\u2122\u2139\u2194-\u2199\u21a9\u21aa"
    r"\u231a\u231b\u2328\u23cf\u23e9-\u23f3\u23f8-\u23fa\u24c2"
    r"\u25aa\u25ab\u25b6\u25c0\u25fb-\u25fe\u2600-\u27bf"
    r"\u2934\u2935\u2b05-\u2b07\u2b1b\u2b1c\u2b50\u2b55\u3030\u303d\u3297\u3299"
    r"\U0001f004\U0001f0cf\U0001f170-\U0001f171\U0001f17e-\U0001f17f"
    r"\U0001f18e\U0001f191-\U0001f19a\U0001f201-\U0001f251"
    r"\U0001f300-\U0001f3fa\U0001f400-\U0001faff]"
)
_EMOJI_UNIT = _EMOJI_BASE + r"\ufe0f?[\U0001f3fb-\U0001f3ff]?"
_EMOJI_SUFFIX = re.compile(
    rf"(?:[\U0001f1e6-\U0001f1ff]{{2}}|[0-9#*]\ufe0f?\u20e3|"
    rf"{_EMOJI_UNIT}(?:\u200d{_EMOJI_UNIT})*)$"
)


class OutputProtocol:
    @staticmethod
    def parse(text: str) -> list[str]:
        """Normalize harmless whitespace and reject ambiguous formatting.

        Args:
            text: Complete final model response, not tool arguments or results.

        Returns:
            One to three non-empty chat bubbles.

        Raises:
            ValueError: The response violates the fixed output protocol.
        """
        text = text.strip()
        if any(
            token in text
            for token in ("\n", "\r", "\\n", "<br", "```", "**", "（", "）", "(", ")")
        ):
            raise ValueError("Multiline, markup, or stage directions are not allowed")
        if re.search(r"(^|\$)\s*(?:#{1,6}\s|[-*>]\s|\d+[.)]\s)", text):
            raise ValueError("Lists and headings are not allowed")
        suffix = _EMOJI_SUFFIX.search(text)
        emoji = suffix.group() if suffix else ""
        if suffix:
            text = text[: suffix.start()].rstrip()
        if re.search(_EMOJI_BASE, text) or any(
            unicodedata.category(c) == "So"
            or c in "\ufe0e\ufe0f\u200d\u20e3"
            or "\U0001f3fb" <= c <= "\U0001f3ff"
            for c in text
        ):
            raise ValueError("Only one emoji at the end of the response is allowed")
        bubbles = [part.strip().rstrip("。.").rstrip() for part in text.split("$")]
        if not 1 <= len(bubbles) <= 3 or any(not part for part in bubbles):
            raise ValueError("Expected one to three non-empty bubbles")
        bubbles[-1] += emoji
        return bubbles
