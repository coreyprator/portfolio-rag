"""Ingest Watkins chunks into Portfolio RAG etymology collection.

Usage:
    python scripts/ingest_watkins.py <RAG_API_KEY>

Reads watkins_chunks.json and POSTs in batches to /ingest/custom.
replace_collection=False — NEVER replaces the etymology collection.
"""

import json
import sys
import time

import httpx

RAG_URL = "https://portfolio-rag-57478301787.us-central1.run.app/ingest/custom"


def ingest(chunks, api_key, batch_size=25):
    total, done, errs = len(chunks), 0, 0
    for i in range(0, total, batch_size):
        batch = chunks[i : i + batch_size]
        try:
            r = httpx.post(
                RAG_URL,
                json={"collection": "etymology", "chunks": batch, "replace_collection": False},
                headers={"x-api-key": api_key},
                timeout=120.0,
            )
            if r.status_code == 200:
                done += len(batch)
                print(f"Batch {i // batch_size + 1}: {done}/{total}")
            else:
                errs += len(batch)
                print(f"ERROR {r.status_code}: {r.text[:200]}")
        except httpx.ReadTimeout:
            errs += len(batch)
            print(f"TIMEOUT batch {i // batch_size + 1} ({len(batch)} chunks)")
        time.sleep(1.0)
    print(f"Done. Ingested={done} Errors={errs}")
    return errs == 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_watkins.py <RAG_API_KEY>")
        sys.exit(1)
    with open("watkins_chunks.json") as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks)} chunks")
    sys.exit(0 if ingest(chunks, sys.argv[1]) else 1)
