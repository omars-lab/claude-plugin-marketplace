"""quote.py — the word-for-word quote check.

    from quote import quote_ok
    quote_ok(item["quote"], caption)      # the quote is really in the caption

No script in this plugin calls a model. The model steps are plugin agents (agents/*.md) that read
a batch file and write an answers file; scripts prepare the batches and check the answers. This
check is how an answer's quote is held to the caption, so no place or item is made up.

Standard library only.
"""

import re
import unicodedata


def norm(s):
    """Lower-case, fold styled letters ("𝐁𝐞𝐚𝐜𝐡" is "Beach"), straighten curly quotes, collapse whitespace:
    the quote-matching rule."""
    s = unicodedata.normalize("NFKC", s or "").replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_ok(quote, text):
    """True when the quote appears in the text word for word (case, quotes, spacing aside)."""
    return bool(quote and quote.strip()) and norm(quote) in norm(text)
