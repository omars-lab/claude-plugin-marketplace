#!/usr/bin/env python3
"""Derive a compact slug from OCR text for screenshot renaming.

Usage:
    python3 slugify_ocr.py --text "OCR content here" [--max-words 5] [--max-chars 40]

Output:
    Plain text slug (e.g. "batch-ocr-processed-files")
"""
import sys
import re
import unicodedata

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "it", "this", "that", "was", "are", "be", "by",
    "from", "as", "into", "about", "has", "have", "had", "not", "are",
    "you", "your", "we", "our", "i", "my", "me", "he", "she", "they",
    "if", "so", "do", "did", "all", "its", "up", "out", "can", "will",
    "just", "no", "more", "also", "than", "then", "when", "where", "which",
    "who", "what", "how", "any", "some", "would", "been", "s", "t", "re",
}

# Boilerplate OCR strings that aren't meaningful slugs
BOILERPLATE = re.compile(
    r"^(screenshot|screen|desktop|untitled|clipboard|image|file|"
    r"am|pm|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)$",
    re.IGNORECASE,
)


def slugify(text: str, max_words: int = 5, max_chars: int = 40) -> str:
    if not text or not text.strip():
        return "untitled"

    # Normalize unicode, lowercase
    text = unicodedata.normalize("NFKD", text).lower()

    # Extract alphanumeric tokens (include hyphens within words)
    tokens = re.findall(r"[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?", text)

    # Filter stopwords and boilerplate
    words = [
        t for t in tokens
        if t not in STOPWORDS and not BOILERPLATE.match(t) and len(t) > 1
    ]

    if not words:
        return "untitled"

    # Take first max_words, join with hyphens, truncate
    slug = "-".join(words[:max_words])
    if len(slug) > max_chars:
        # Truncate at last hyphen boundary
        slug = slug[:max_chars]
        last_hyphen = slug.rfind("-")
        if last_hyphen > max_chars // 2:
            slug = slug[:last_hyphen]

    return slug or "untitled"


def main():
    args = sys.argv[1:]
    text = ""
    max_words = 5
    max_chars = 40

    if "--text" in args:
        idx = args.index("--text")
        text = args[idx + 1]
    if "--max-words" in args:
        idx = args.index("--max-words")
        max_words = int(args[idx + 1])
    if "--max-chars" in args:
        idx = args.index("--max-chars")
        max_chars = int(args[idx + 1])

    print(slugify(text, max_words, max_chars))


if __name__ == "__main__":
    main()
