"""
Export DCC Greek Core List from PIE Network Graph API and ingest into Portfolio RAG.

Fetches 584 words from EFG /api/words?include_dcc=true,
filters to DCC-imported words, formats each as a markdown chunk,
and POSTs to Portfolio RAG /ingest/custom as the 'dcc' collection.

Usage:
  python scripts/export_dcc_chunks.py [--dry-run] [--rag-url URL] [--api-key KEY]
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse

DCC_API = "https://efg.rentyourcio.com/api/words?include_dcc=true"
RAG_INGEST = "https://portfolio-rag-57478301787.us-central1.run.app/ingest/custom"


def fetch_dcc_words(api_url: str) -> list[dict]:
    req = urllib.request.Request(api_url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    # Filter to DCC-imported words only, sorted by frequency rank
    dcc = [w for w in data if w.get("dcc_imported") and w.get("frequency_rank") is not None]
    dcc.sort(key=lambda w: w["frequency_rank"])
    return dcc


def format_chunk(word: dict) -> dict:
    label = word["label"]
    rank = word["frequency_rank"]
    gloss = word.get("gloss") or ""
    transliteration = word.get("transliteration") or ""
    pie_root_id = word.get("pie_root_id") or ""
    cognates = word.get("english_cognates") or ""
    pos = word.get("pos") or ""
    semantic_group = word.get("semantic_group") or ""
    sf_link = word.get("sf_link") or ""

    # Transliteration display
    translit_part = f" ({transliteration})" if transliteration else ""
    pos_line = f"**Part of speech:** {pos}\n" if pos else ""
    group_line = f"**Semantic group:** {semantic_group}\n" if semantic_group else ""
    pie_line = f"**PIE root:** {pie_root_id.replace('pie_', '*').replace('_', '-')}\n" if pie_root_id else ""
    cognates_line = f"**English cognates:** {cognates}\n" if cognates else ""
    sf_line = f"**Super Flashcards:** {sf_link}\n" if sf_link else ""

    content = f"""# {label}{translit_part} — DCC #{rank}

**Definition:** {gloss}
{pos_line}{group_line}**Frequency rank:** {rank} of 532 (DCC Greek Core List)
{pie_line}{cognates_line}{sf_line}
One of the 532 most frequent ancient Greek words. Source: dcc.dickinson.edu"""

    chunk_id = f"dcc-{rank:03d}"
    metadata = {
        "lemma": label,
        "transliteration": transliteration,
        "frequency_rank": rank,
        "part_of_speech": pos,
        "semantic_group": semantic_group,
        "definition": gloss,
        "pie_root_id": pie_root_id,
        "english_cognates": cognates,
        "sf_link": sf_link,
        "source": "dcc",
        "dcc_url": "https://dcc.dickinson.edu/greek-core-list",
    }
    return {"id": chunk_id, "content": content, "metadata": metadata}


def post_ingest(chunks: list[dict], rag_url: str, api_key: str) -> dict:
    payload = json.dumps({
        "collection": "dcc",
        "chunks": chunks,
        "replace_collection": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        rag_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Export DCC words to Portfolio RAG")
    parser.add_argument("--dry-run", action="store_true", help="Format chunks but don't POST")
    parser.add_argument("--rag-url", default=RAG_INGEST, help="Portfolio RAG ingest URL")
    parser.add_argument("--api-key", required=True, help="Portfolio RAG x-api-key")
    args = parser.parse_args()

    print(f"Fetching DCC words from {DCC_API}...")
    words = fetch_dcc_words(DCC_API)
    print(f"Fetched {len(words)} DCC words (ranked by frequency)")

    chunks = [format_chunk(w) for w in words]
    print(f"Formatted {len(chunks)} chunks")

    if args.dry_run:
        print("\n--- DRY RUN: sample chunk ---")
        print(json.dumps(chunks[0], indent=2, ensure_ascii=False))
        print(f"\nWould POST {len(chunks)} chunks to {args.rag_url}")
        return

    print(f"\nPOSTing {len(chunks)} chunks to {args.rag_url}...")
    try:
        result = post_ingest(chunks, args.rag_url, args.api_key)
        print(f"\nIngest result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
