"""Kroonen (Etymological Dictionary of Proto-Germanic) ingestion script.

Parses the Kroonen PDF into per-lemma chunks and ingests into the
Portfolio RAG etymology collection via /ingest/custom (additive, no delete).

Usage:
    python scripts/ingest_kroonen.py --api-key <RAG_API_KEY> [--dry-run] [--batch-size 100]

Parsing strategy:
- Extract all PDF pages via PyPDF2
- Concatenate into one text block; fix common extraction artifacts
- Split on Proto-Germanic headword pattern: line starting with *lemma- + grammar tag
- For each entry: extract headword, grammar, meaning, PIE root, distribution tag, cognates
- POST batches of chunks to POST /ingest/custom with replace_collection=false
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
import warnings
warnings.filterwarnings("ignore")

PDF_PATH = "G:/My Drive/Code/Python/portfolio-rag/Etymological Dictionary of Proto-Germanic.pdf"
INGEST_URL = "https://portfolio-rag-57478301787.us-central1.run.app/ingest/custom"
COLLECTION = "etymology"

# Grammar abbreviations that follow headword in Kroonen entries
GRAMMAR_TAGS = (
    "m.", "n.", "f.", "adj.", "adv.", "pron.", "num.", "prep.",
    "v.", "wk.v.", "str.v.", "wv.", "sv.", "m/f.", "m/n.", "f/n.",
    "m.pl.", "n.pl.", "f.pl.", "m.a-stem", "n.a-stem",
)

# Distribution tags used in Kroonen
DIST_TAGS = {"IE", "GM", "NEUR", "WEUR", "EUR", "LW", "NIE", "DRV", "GRM", "WGM"}


def extract_pdf_text(pdf_path: str) -> list[str]:
    """Extract text from all pages of the PDF."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        print("ERROR: PyPDF2 not installed. Run: py -m pip install PyPDF2")
        sys.exit(1)

    print(f"Reading PDF: {pdf_path}")
    reader = PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append(text)
        if i % 100 == 0 and i > 0:
            print(f"  Extracted {i}/{len(reader.pages)} pages...")
    print(f"  Done: {len(pages)} pages extracted")
    return pages


def clean_text(text: str) -> str:
    """Clean PDF extraction artifacts."""
    # Fix soft hyphens / line-break hyphens in the middle of words
    text = re.sub(r"\xad\n", "", text)
    text = re.sub(r"-\n(?=[a-z])", "", text)
    # Normalize whitespace (preserve newlines for structure)
    text = re.sub(r"[ \t]+", " ", text)
    # Remove standalone page number lines (just a number)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    return text


def is_headword_line(line: str) -> bool:
    """Return True if this line looks like a Kroonen headword entry start.

    Pattern: *[lowercase_lemma]- GRAMMAR_TAG 'meaning'
    Requirements:
    - Line starts with * (not indented)
    - Second char is lowercase letter (PGm reconstructions are lowercase)
    - Contains a grammar tag abbreviation
    - Contains a quoted meaning with ASCII apostrophe
    """
    stripped = line.lstrip()
    # Must start with * followed immediately by a lowercase letter
    if not re.match(r"^\*[a-z]", stripped):
        return False
    # Must contain a grammar tag somewhere in first 100 chars
    snippet = stripped[:100]
    has_grammar = any(f" {g}" in snippet or f"\t{g}" in snippet for g in GRAMMAR_TAGS)
    # Must contain a quoted meaning (single quotes around meaning)
    has_meaning = "'" in snippet
    return has_grammar and has_meaning


def parse_entries(pages: list[str]) -> list[dict]:
    """Parse Kroonen pages into per-lemma entry chunks."""
    # Join all pages with a page separator
    full_text = clean_text("\n".join(pages))
    lines = full_text.splitlines()

    entries = []
    current_lines = []
    current_start = 0

    for i, line in enumerate(lines):
        if is_headword_line(line):
            if current_lines:
                entry_text = "\n".join(current_lines).strip()
                if len(entry_text) > 30:
                    entries.append(entry_text)
            current_lines = [line]
        else:
            current_lines.append(line)

    # Last entry
    if current_lines:
        entry_text = "\n".join(current_lines).strip()
        if len(entry_text) > 30:
            entries.append(entry_text)

    print(f"  Parsed {len(entries)} candidate entries")
    return entries


def parse_entry_metadata(entry_text: str) -> dict:
    """Extract structured metadata from a Kroonen entry text block."""
    lines = entry_text.splitlines()
    first_line = lines[0] if lines else entry_text

    # --- Headword ---
    hw_match = re.match(r"(\*[^\s']+)", first_line)
    headword = hw_match.group(1) if hw_match else ""

    # --- Grammar ---
    grammar = ""
    for tag in GRAMMAR_TAGS:
        if f" {tag}" in first_line or f"\t{tag}" in first_line:
            grammar = tag
            break

    # --- Meaning ---
    meaning = ""
    meaning_match = re.search(r"['\u2018]([^'\u2019]{1,100})['\u2019]", first_line)
    if meaning_match:
        meaning = meaning_match.group(1).strip()

    # --- Cognates: dash + language abbreviations after meaning on first line ---
    cognates = ""
    cog_match = re.search(r"-\s*([A-Z][A-Za-z.]+\s+.{5,}?)(?:\?|$)", first_line)
    if cog_match:
        cognates = cog_match.group(1).strip()[:300]
    else:
        # Look in entry body for language lines
        for ln in lines[1:4]:
            if re.match(r"\s*-\s*[A-Z]", ln):
                cognates = ln.strip().lstrip("-").strip()[:300]
                break

    # --- PIE root and distribution tag ---
    pie_root = ""
    distribution_tag = ""
    for ln in lines:
        # PIE root line: starts with arrow/bullet/? followed by *
        pie_match = re.search(r"[?\u2192\u2022\u00bb]\s*(\*\S+)", ln)
        if pie_match:
            pie_root = pie_match.group(1)
            # Distribution tag: (IE), (GM), etc.
            dist_match = re.search(r"\((" + "|".join(DIST_TAGS) + r")\)", ln)
            if dist_match:
                distribution_tag = dist_match.group(1)
            break

    return {
        "headword": headword,
        "grammar": grammar,
        "meaning": meaning,
        "pie_root": pie_root,
        "distribution_tag": distribution_tag,
        "cognates": cognates[:300],
        "source": "Kroonen",
        "source_file": "Etymological Dictionary of Proto-Germanic.pdf",
        "collection": COLLECTION,
        "doc_type": "dictionary",
    }


def build_chunk_text(entry_text: str, meta: dict) -> str:
    """Format chunk text for embedding — matches sprint spec format."""
    parts = []
    if meta["headword"] and meta["meaning"]:
        parts.append(f"{meta['headword']} — {meta['meaning']}")
    else:
        parts.append(entry_text.splitlines()[0][:100])

    if meta["pie_root"]:
        parts.append(f"PIE: {meta['pie_root']}")
    if meta["distribution_tag"]:
        parts.append(f"Distribution: {meta['distribution_tag']}")
    if meta["cognates"]:
        parts.append(f"Cognates: {meta['cognates']}")

    # Add body of entry (notes, cross-refs) for richer semantic embedding
    body_lines = [ln.strip() for ln in entry_text.splitlines()[1:] if ln.strip()]
    if body_lines:
        notes = " ".join(body_lines)[:500]
        parts.append(f"Notes: {notes}")

    return "\n".join(parts)


def post_batch(url: str, api_key: str, collection: str, chunks: list[dict], dry_run: bool) -> int:
    """POST a batch of chunks to /ingest/custom. Returns count ingested."""
    if dry_run:
        print(f"  [DRY RUN] Would POST {len(chunks)} chunks")
        return len(chunks)

    payload = json.dumps({
        "collection": collection,
        "chunks": chunks,
        "replace_collection": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result.get("chunks_ingested", len(chunks))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ERROR {e.code}: {body[:300]}")
        return 0
    except Exception as e:
        print(f"  ERROR: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Ingest Kroonen Proto-Germanic dictionary into Portfolio RAG")
    parser.add_argument("--api-key", required=True, help="RAG API key (x-api-key)")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, do not POST")
    parser.add_argument("--batch-size", type=int, default=100, help="Chunks per POST request")
    parser.add_argument("--pdf", default=PDF_PATH, help="Path to Kroonen PDF")
    parser.add_argument("--url", default=INGEST_URL, help="Ingest endpoint URL")
    args = parser.parse_args()

    # Step 1: Extract PDF text
    pages = extract_pdf_text(args.pdf)

    # Step 2: Parse entries — skip intro pages (first 38 are front matter/intro)
    # Page 38 (index 38) is where the "A" dictionary section begins with *aba-
    print("Parsing entries (skipping first 38 intro pages)...")
    entries = parse_entries(pages[38:])

    if not entries:
        print("ERROR: No entries parsed. PDF may not be text-extractable or parser needs adjustment.")
        sys.exit(1)

    # Step 3: Build chunks
    print(f"Building {len(entries)} chunks...")
    chunks = []
    skipped = 0
    for i, entry_text in enumerate(entries):
        meta = parse_entry_metadata(entry_text)
        text = build_chunk_text(entry_text, meta)

        if len(text) < 20:
            skipped += 1
            continue

        chunk_id = f"kroonen::{meta['headword'] or str(i)}::{i}"
        chunks.append({
            "id": chunk_id,
            "content": text,
            "metadata": meta,
        })

    print(f"  Built {len(chunks)} chunks ({skipped} skipped as too short)")

    if args.dry_run:
        print("\n--- DRY RUN: first 3 chunks ---")
        for c in chunks[:3]:
            safe_id = c['id'].encode('ascii', errors='replace').decode()
            safe_content = c['content'][:400].encode('ascii', errors='replace').decode()
            safe_meta = json.dumps(c['metadata'], ensure_ascii=True)[:300]
            print(f"\nID: {safe_id}")
            print(f"Content:\n{safe_content}")
            print(f"Metadata: {safe_meta}")
        print(f"\nTotal would ingest: {len(chunks)}")
        return

    # Step 4: POST in batches
    print(f"\nIngesting {len(chunks)} chunks to {args.url} (batch={args.batch_size})...")
    total_ingested = 0
    for start in range(0, len(chunks), args.batch_size):
        batch = chunks[start:start + args.batch_size]
        n = post_batch(args.url, args.api_key, COLLECTION, batch, args.dry_run)
        total_ingested += n
        print(f"  Batch {start // args.batch_size + 1}: {n}/{len(batch)} ingested (total: {total_ingested})")

    print(f"\nDone. Total Kroonen chunks ingested: {total_ingested}")
    return total_ingested


if __name__ == "__main__":
    main()
