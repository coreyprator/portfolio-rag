"""Ingest de Vaan Latin etymology chunks into Portfolio RAG etymology collection.

Reads devaan_chunks_clean.json and POSTs to /ingest/custom in batches.
NEVER replaces the collection — APPEND only.

Usage:
    python scripts/ingest_devaan.py
"""

import json
import os
import time

import httpx

RAG_URL = os.getenv("RAG_URL", "https://portfolio-rag-57478301787.us-central1.run.app/ingest/custom")
API_KEY_FILE = None  # read from env or prompt

BATCH_SIZE = 20
SLEEP_BETWEEN = 1.0   # seconds
TIMEOUT = 120.0


def get_api_key() -> str:
    key = os.getenv("RAG_API_KEY", "")
    if not key:
        # Try reading from gcloud secrets output file
        key_file = os.path.expanduser("~/devaan_api_key.txt")
        if os.path.exists(key_file):
            with open(key_file) as f:
                key = f.read().strip()
    if not key:
        raise ValueError("RAG_API_KEY not set")
    return key


def main():
    chunk_file = os.path.join(os.path.dirname(__file__), "..", "devaan_chunks_clean.json")
    if not os.path.exists(chunk_file):
        chunk_file = "devaan_chunks_clean.json"

    with open(chunk_file) as f:
        chunks = json.load(f)

    print(f"Loaded {len(chunks)} chunks from {chunk_file}")

    api_key = get_api_key()
    total_ingested = 0
    total_errors = 0
    batches = [chunks[i : i + BATCH_SIZE] for i in range(0, len(chunks), BATCH_SIZE)]

    print(f"Ingesting in {len(batches)} batches of {BATCH_SIZE}...")

    for bi, batch in enumerate(batches):
        payload = {
            "collection": "etymology",
            "chunks": batch,
            "replace_collection": False,  # CRITICAL: never replace
        }
        try:
            r = httpx.post(
                RAG_URL,
                json=payload,
                headers={"x-api-key": api_key},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            ingested = data.get("chunks_ingested", len(batch))
            total_ingested += ingested
            print(f"Batch {bi+1}/{len(batches)}: ingested={ingested} total={total_ingested}")
        except Exception as e:
            total_errors += 1
            print(f"Batch {bi+1}/{len(batches)}: ERROR {e}")
            if total_errors > 5:
                print("Too many errors — aborting")
                break

        if bi < len(batches) - 1:
            time.sleep(SLEEP_BETWEEN)

    print(f"\nDone. Ingested={total_ingested} Errors={total_errors}")


if __name__ == "__main__":
    main()
