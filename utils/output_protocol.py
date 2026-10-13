"""Parser for the fixed dollar-separated chat bubble protocol."""

import re
import unicodedata


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
        if any(unicodedata.category(c) == "So" for c in text):
            raise ValueError("Emoji and pictographic symbols are not allowed")
        bubbles = [part.strip().rstrip("。.").rstrip() for part in text.split("$")]
        if not 1 <= len(bubbles) <= 3 or any(not part for part in bubbles):
            raise ValueError("Expected one to three non-empty bubbles")
        return bubbles
