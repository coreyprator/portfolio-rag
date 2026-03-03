"""CLI ingestion script for Portfolio RAG collections.

Usage:
    python ingest.py --collection portfolio
    python ingest.py --collection etymology
    python ingest.py --collection etymology --source /path/to/beekes.pdf
"""

import argparse
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

from app.core.vectorstore import vector_store
from app.services.ingestion import ingest_portfolio, ingest_etymology


async def main():
    parser = argparse.ArgumentParser(description="Ingest documents into ChromaDB")
    parser.add_argument("--collection", required=True, choices=["portfolio", "etymology"])
    parser.add_argument("--source", help="PDF path for etymology collection")
    args = parser.parse_args()

    vector_store.initialize()

    if args.collection == "portfolio":
        result = await ingest_portfolio()
    elif args.collection == "etymology":
        result = await ingest_etymology(pdf_path=args.source)

    print(f"Result: {result}")
    chunks = result.get("chunks", 0)
    if chunks > 0:
        print(f"Successfully ingested {chunks} chunks into {args.collection} collection")
    else:
        print(f"Ingestion returned 0 chunks. Check errors: {result.get('error', 'none')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
