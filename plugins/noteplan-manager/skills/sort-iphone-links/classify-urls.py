#!/usr/bin/env python3
"""
classify-urls.py
Classify URLs by topic using domain heuristics.

Usage:
  python3 classify-urls.py <url>              # classify a single URL
  python3 classify-urls.py --file <links.md>  # classify all URLs found in a markdown file
  echo "https://example.com" | python3 classify-urls.py -  # classify from stdin

Output: JSON with {url, category, confidence, reason}

Used by: sort-iphone-links
"""

import sys
import re
import json
import argparse
from urllib.parse import urlparse


# ── Domain → category mapping ─────────────────────────────────────────────────
# Each entry: (domain_pattern, category, reason)
# Checked in order — first match wins.

DOMAIN_RULES: list[tuple[str, str, str]] = [
    # GenAI / ML
    ("openai.com", "GenAI", "OpenAI"),
    ("anthropic.com", "GenAI", "Anthropic"),
    ("huggingface.co", "GenAI", "HuggingFace"),
    ("deepmind.google", "GenAI", "DeepMind"),
    ("mistral.ai", "GenAI", "Mistral"),
    ("cohere.com", "GenAI", "Cohere"),
    ("replicate.com", "GenAI", "Replicate"),
    ("together.ai", "GenAI", "Together AI"),
    ("perplexity.ai", "GenAI", "Perplexity"),
    ("claude.ai", "GenAI", "Claude"),
    ("gemini.google.com", "GenAI", "Gemini"),
    ("llamafile", "GenAI", "LlamaFile"),
    ("ollama.com", "GenAI", "Ollama"),
    ("langchain.com", "GenAI", "LangChain"),
    ("llamaindex.ai", "GenAI", "LlamaIndex"),
    # AWS
    ("aws.amazon.com", "AWS", "AWS"),
    ("awsstatic.com", "AWS", "AWS static"),
    ("docs.aws.amazon.com", "AWS", "AWS docs"),
    ("repost.aws", "AWS", "AWS repost"),
    ("workshops.aws", "AWS", "AWS workshop"),
    # Software / Dev tools
    ("github.com", "Software", "GitHub"),
    ("gitlab.com", "Software", "GitLab"),
    ("stackoverflow.com", "Software", "Stack Overflow"),
    ("dev.to", "Software", "dev.to"),
    ("hashnode.dev", "Software", "Hashnode"),
    ("npmjs.com", "Software", "npm"),
    ("pypi.org", "Software", "PyPI"),
    ("docs.python.org", "Software", "Python docs"),
    ("developer.mozilla.org", "Software", "MDN"),
    ("react.dev", "Software", "React"),
    ("nextjs.org", "Software", "Next.js"),
    ("vercel.com", "Software", "Vercel"),
    ("supabase.com", "Software", "Supabase"),
    ("planetscale.com", "Software", "PlanetScale"),
    ("fly.io", "Software", "Fly.io"),
    # Career
    ("linkedin.com/jobs", "Career", "LinkedIn jobs"),
    ("linkedin.com", "Career", "LinkedIn"),
    ("levels.fyi", "Career", "Levels.fyi"),
    ("glassdoor.com", "Career", "Glassdoor"),
    ("indeed.com", "Career", "Indeed"),
    ("layoffs.fyi", "Career", "Layoffs tracker"),
    ("blind", "Career", "Blind"),
    # Business / Entrepreneurship
    ("ycombinator.com", "Business", "Y Combinator"),
    ("techcrunch.com", "Business", "TechCrunch"),
    ("starterstory.com", "Business", "Starter Story"),
    ("indiehackers.com", "Business", "Indie Hackers"),
    ("microacquire.com", "Business", "MicroAcquire"),
    # Tools / Productivity
    ("notion.so", "Tools", "Notion"),
    ("obsidian.md", "Tools", "Obsidian"),
    ("raycast.com", "Tools", "Raycast"),
    ("alfredapp.com", "Tools", "Alfred"),
    ("zapier.com", "Tools", "Zapier"),
    ("make.com", "Tools", "Make"),
    ("airtable.com", "Tools", "Airtable"),
    # Leadership / Management
    ("hbr.org", "Leadership", "HBR"),
    ("lethain.com", "Leadership", "Will Larson"),
    ("scarletink.com", "Leadership", "ScarletInk"),
    ("manager-tools.com", "Leadership", "Manager Tools"),
    ("svpg.com", "Leadership", "SVPG"),
    # Motivation / Self-improvement
    ("jamesclear.com", "Motivation", "James Clear"),
    ("fs.blog", "Motivation", "Farnam Street"),
    ("paulgraham.com", "Motivation", "Paul Graham"),
    ("masterclass.com", "Motivation", "MasterClass"),
    # Shopping / Products
    ("amazon.com", "Shopping", "Amazon"),
    ("amazon.co", "Shopping", "Amazon"),
    ("etsy.com", "Shopping", "Etsy"),
    ("ebay.com", "Shopping", "eBay"),
    ("wirecutter.com", "Shopping", "Wirecutter"),
    # Entertainment
    ("netflix.com", "Entertainment", "Netflix"),
    ("imdb.com", "Entertainment", "IMDB"),
    ("rottentomatoes.com", "Entertainment", "Rotten Tomatoes"),
    ("twitch.tv", "Entertainment", "Twitch"),
    # YouTube — special: classify by channel/topic not just domain
    ("youtube.com", "GenAI", "YouTube — check title for actual topic"),
    ("youtu.be", "GenAI", "YouTube short link — check title"),
    # Services / SaaS
    ("stripe.com", "Services", "Stripe"),
    ("plaid.com", "Services", "Plaid"),
    ("cloudflare.com", "Services", "Cloudflare"),
    ("1password.com", "Services", "1Password"),
    ("bitwarden.com", "Services", "Bitwarden"),
    # Good Reads / Long-form
    ("substack.com", "Good Reads", "Substack"),
    ("medium.com", "Good Reads", "Medium"),
    ("lesswrong.com", "Good Reads", "LessWrong"),
    ("aeon.co", "Good Reads", "Aeon"),
    ("theatlantic.com", "Good Reads", "The Atlantic"),
    ("newyorker.com", "Good Reads", "New Yorker"),
    ("wired.com", "Good Reads", "Wired"),
    # References / Education
    ("coursera.org", "References", "Coursera"),
    ("udemy.com", "References", "Udemy"),
    ("khanacademy.org", "References", "Khan Academy"),
    ("wikipedia.org", "References", "Wikipedia"),
    ("arxiv.org", "References", "arXiv"),
]

# Path-based refinements for YouTube
YOUTUBE_PATH_RULES: list[tuple[str, str]] = [
    ("@", "Good Reads"),       # channel page
    ("playlist", "References"), # playlists tend to be educational
]


def classify_url(url: str) -> dict:
    """Classify a URL and return {url, category, confidence, reason}."""
    try:
        parsed = urlparse(url)
    except Exception:
        return {"url": url, "category": "References", "confidence": "low", "reason": "parse error"}

    domain = parsed.netloc.lower().lstrip("www.")
    path = parsed.path.lower()

    for pattern, category, reason in DOMAIN_RULES:
        if pattern in domain:
            # Refine YouTube by path
            if "youtube" in domain or "youtu.be" in domain:
                for path_pat, path_cat in YOUTUBE_PATH_RULES:
                    if path_pat in path:
                        return {"url": url, "category": path_cat, "confidence": "medium", "reason": f"YouTube ({path_pat})"}
                return {"url": url, "category": "GenAI", "confidence": "low",
                        "reason": "YouTube — topic unknown without title"}
            return {"url": url, "category": category, "confidence": "high", "reason": reason}

    # Fallback: no match
    return {"url": url, "category": "References", "confidence": "low", "reason": f"unknown domain: {domain}"}


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from markdown text."""
    # Matches http(s):// URLs
    return re.findall(r'https?://[^\s\)\]\"\']+', text)


def main():
    parser = argparse.ArgumentParser(description="Classify URLs by topic")
    parser.add_argument("url", nargs="?", help="Single URL to classify, or - for stdin")
    parser.add_argument("--file", help="Markdown file to extract and classify URLs from")
    parser.add_argument("--format", choices=["json", "tsv", "plain"], default="plain")
    args = parser.parse_args()

    urls = []

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
        urls = extract_urls(text)
    elif args.url == "-" or (not args.url and not sys.stdin.isatty()):
        text = sys.stdin.read()
        # If it looks like a single URL, classify it; otherwise extract all
        text = text.strip()
        if text.startswith("http"):
            urls = [text]
        else:
            urls = extract_urls(text)
    elif args.url:
        urls = [args.url]
    else:
        parser.print_help()
        sys.exit(1)

    results = [classify_url(u) for u in urls]

    if args.format == "json":
        print(json.dumps(results, indent=2))
    elif args.format == "tsv":
        print("url\tcategory\tconfidence\treason")
        for r in results:
            print(f"{r['url']}\t{r['category']}\t{r['confidence']}\t{r['reason']}")
    else:
        for r in results:
            conf_icon = "✓" if r["confidence"] == "high" else "~"
            print(f"{conf_icon} [{r['category']}] {r['reason']}")
            print(f"  {r['url']}")


if __name__ == "__main__":
    main()
