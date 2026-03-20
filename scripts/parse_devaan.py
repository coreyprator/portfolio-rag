"""Parse de Vaan Etymological Dictionary of Latin (2008) PDF into RAG chunks.

Entry format: headword 'meaning' [grammar] (source+)
Followed by: derivatives, PIE reconstruction, IE cognates, bibliography.

Usage:
    python scripts/parse_devaan.py > devaan_chunks.json
"""

import json
import re
import sys

import pdfplumber

PDF_PATH = r"G:\My Drive\Code\Python\Portfolio_RAG\de Vaan - Etymological Dictionary of Latin (2008).pdf"
SOURCE_FILE = "de Vaan - Etymological Dictionary of Latin (2008).pdf"

# Dictionary pages: skip front matter (~1-28) and index (~800+)
ENTRY_PAGE_START = 29
ENTRY_PAGE_END = 800

# Running header pattern: "word NNN" or "NNN word" lines at top of page
RUNNING_HEADER = re.compile(r"^[A-Za-z\- ]{1,30}\s+\d{1,4}\s*$|^\d{1,4}\s+[A-Za-z\- ]{1,30}\s*$")

# Entry header: starts at line beginning with lowercase Latin word(s) + quote-like char
# Handles: acu-, ad, adeps, -ipls, ambo, etc.
ENTRY_PATTERN = re.compile(
    r"(?:^|\n)"
    r"([a-z][a-zāēīōūăĕĭŏŭáéíóúâêîôû\-,()1-9 ]{0,40}?)"  # headword (lowercase Latin)
    r"\s*['\u2018\u2019\u201a\u201b\*]"                       # opening quote or OCR *
    r"[^'\u2018\u2019\u201a\u201b\*\[]{3,120}"               # gloss (not too long)
    r"[\*'\u2018\u2019\u201a\u201b]?"                         # optional closing quote
    r"\s*\[",                                                  # opens grammar bracket
    re.MULTILINE,
)


def extract_pages(pdf_path: str) -> list[tuple[int, str]]:
    """Extract text page-by-page, stripping running headers."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        print(f"Total pages: {total}", file=sys.stderr)
        for i, page in enumerate(pdf.pages):
            pnum = i + 1
            if pnum < ENTRY_PAGE_START or pnum > ENTRY_PAGE_END:
                continue
            try:
                text = page.extract_text()
                if not text or len(text.strip()) < 10:
                    continue
                # Strip running headers (first 1-2 lines)
                lines = text.split("\n")
                cleaned = []
                for li, line in enumerate(lines):
                    if li < 2 and RUNNING_HEADER.match(line.strip()):
                        continue
                    cleaned.append(line)
                pages.append((pnum, "\n".join(cleaned)))
            except Exception as e:
                print(f"Page {pnum} error: {e}", file=sys.stderr)
    return pages


def split_entries(full_text: str) -> list[tuple[str, str]]:
    """Split full text into (headword, entry_text) pairs."""
    matches = list(ENTRY_PATTERN.finditer(full_text))
    print(f"Raw matches: {len(matches)}", file=sys.stderr)

    entries = []
    for i, match in enumerate(matches):
        headword = match.group(1).strip().rstrip(",- ")
        if not headword or len(headword) < 1:
            continue

        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        entry_text = full_text[start:end].strip()

        # Quality filters
        if len(entry_text) < 40:
            continue

        # Must have some etymological content
        has_pie = any(kw in entry_text for kw in ["PIE", "Pit.", "Proto-Italic", "IE cognates", "*h", "PGm"])
        has_cognates = any(
            lang in entry_text
            for lang in ["Greek", "Skt.", "Sanskrit", "Germanic", "Celtic",
                         "Gothic", "Lithuanian", "Slavic", "OIr", "OHG", "OE"]
        )
        if not has_pie and not has_cognates:
            continue

        entries.append((headword, entry_text))

    return entries


def make_chunks(entries: list[tuple[str, str]]) -> list[dict]:
    chunks = []
    seen: set[str] = set()

    for i, (headword, entry_text) in enumerate(entries):
        key = headword.lower()
        if key in seen:
            continue
        seen.add(key)

        slug = re.sub(r"[^a-z0-9]", "_", headword.lower()).strip("_")

        text = f"de Vaan Latin Etymology: {entry_text}"
        if len(text) > 2000:
            text = text[:1997] + "..."

        chunk = {
            "id": f"devaan::{i:04d}::{slug}",
            "content": text,
            "metadata": {
                "source": "de-vaan",
                "source_file": SOURCE_FILE,
                "collection": "etymology",
                "headword": headword,
                "language": "Latin",
                "dictionary": "de Vaan Etymological Dictionary of Latin 2008",
                "author": "de Vaan",
                "year": "2008",
            },
        }
        chunks.append(chunk)

    return chunks


def main():
    pages = extract_pages(PDF_PATH)
    print(f"Extracted {len(pages)} pages", file=sys.stderr)

    full_text = "\n".join(text for _, text in pages)
    print(f"Total text: {len(full_text):,} chars", file=sys.stderr)

    entries = split_entries(full_text)
    print(f"Parsed {len(entries)} entries", file=sys.stderr)

    chunks = make_chunks(entries)
    print(f"Generated {len(chunks)} chunks", file=sys.stderr)

    if chunks:
        print(f"First: {chunks[0]['id']} | {chunks[0]['content'][:100]}", file=sys.stderr)
        print(f"Last:  {chunks[-1]['id']} | {chunks[-1]['content'][:100]}", file=sys.stderr)

    json.dump(chunks, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
