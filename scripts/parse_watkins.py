"""Parse Watkins American Heritage Dictionary of IE Roots (1985) epub into RAG chunks.

Reads the OCR-scanned epub, extracts dictionary entry pages (30-109),
concatenates text, splits by root entry pattern, and outputs JSON chunks
suitable for /ingest/custom.

Usage:
    python scripts/parse_watkins.py > watkins_chunks.json
"""

import json
import re
import sys

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

EPUB_PATH = r"G:\My Drive\Code\Python\Portfolio_RAG\Watkins - American Heritage Dictionary of Indo-European Roots (1985).epub"

# Dictionary entry pages (from epub inspection)
ENTRY_PAGE_START = 30
ENTRY_PAGE_END = 109


def extract_pages(book):
    """Extract text from dictionary entry pages, sorted by page number."""
    html_items = sorted(
        [item for item in book.get_items() if item.get_name().startswith("page_")],
        key=lambda x: int(x.get_name().replace("page_", "").replace(".html", "")),
    )

    pages = []
    for item in html_items:
        num = int(item.get_name().replace("page_", "").replace(".html", ""))
        if ENTRY_PAGE_START <= num <= ENTRY_PAGE_END:
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text(separator=" ", strip=True)
            # Remove the "Page NN" prefix from OCR
            text = re.sub(r"^Page \d+\s*", "", text)
            if len(text) > 10:  # skip blank pages
                pages.append((num, text))
    return pages


def split_entries(full_text):
    """Split concatenated text into individual root entries.

    Entry pattern: a root like "abel-." or "ag-." at the start of a line or
    after whitespace. Roots are lowercase, may contain hyphens, parentheses,
    and superscript numbers. They end with a period or period-space.

    Pattern: word boundary + lowercase root (with optional trailing number) + period + space + Capitalized gloss
    """
    # PIE roots in Watkins always end with a hyphen (e.g., abel-, ag-, bhel-2)
    # Pattern: root with mandatory trailing hyphen + optional number + ". " + Capitalized gloss
    entry_pattern = re.compile(
        r"(?:^|\s)"  # start or whitespace
        r"((?:[a-z]+[-()]*)*[a-z]+-"  # root: must contain and end with hyphen
        r"(?:\d+)?)"  # optional trailing number (e.g., bhel-2)
        r"\.\s+"  # period + space
        r"([A-Z])",  # start of capitalized gloss
    )

    entries = []
    matches = list(entry_pattern.finditer(full_text))

    for i, match in enumerate(matches):
        root = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        entry_text = full_text[start:end].strip()

        # Skip very short entries (likely OCR artifacts)
        if len(entry_text) < 20:
            continue

        # Skip entries that look like index items or non-root text
        # Real roots contain derivative info (Latin, Greek, Germanic, Old English, etc.)
        if not any(
            lang in entry_text
            for lang in ["Latin", "Greek", "Germanic", "English", "Sanskrit", "Celtic", "Slavic"]
        ):
            continue

        entries.append((root, entry_text))

    return entries


def make_chunks(entries):
    """Convert parsed entries into RAG-compatible chunks."""
    chunks = []
    seen_roots = set()

    for i, (root, entry_text) in enumerate(entries):
        # Deduplicate by full root string (preserves al-1 vs al-2)
        root_key = root.lower()
        if root_key in seen_roots:
            continue
        seen_roots.add(root_key)

        # Slug for ID
        root_slug = re.sub(r"[^a-z0-9]", "_", root.lower()).strip("_")

        # Truncate to 1500 chars max
        text = f"Watkins PIE Root: {entry_text}"
        if len(text) > 1500:
            text = text[:1497] + "..."

        chunk = {
            "id": f"watkins::{i:04d}::{root_slug}",
            "content": text,
            "metadata": {
                "source": "watkins",
                "source_file": "Watkins - American Heritage Dictionary of Indo-European Roots (1985).epub",
                "collection": "etymology",
                "root": root,
                "dictionary": "Watkins American Heritage Dictionary of IE Roots 1985",
            },
        }
        chunks.append(chunk)

    return chunks


def main():
    book = epub.read_epub(EPUB_PATH)
    pages = extract_pages(book)
    print(f"Extracted {len(pages)} dictionary pages", file=sys.stderr)

    # Concatenate all page text
    full_text = " ".join(text for _, text in pages)
    print(f"Total text: {len(full_text)} chars", file=sys.stderr)

    entries = split_entries(full_text)
    print(f"Parsed {len(entries)} entries", file=sys.stderr)

    chunks = make_chunks(entries)
    print(f"Generated {len(chunks)} chunks", file=sys.stderr)

    if chunks:
        print(f"First: {chunks[0]['id']} | {chunks[0]['content'][:80]}", file=sys.stderr)
        print(f"Last:  {chunks[-1]['id']} | {chunks[-1]['content'][:80]}", file=sys.stderr)

    json.dump(chunks, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
