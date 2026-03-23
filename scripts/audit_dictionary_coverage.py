#!/usr/bin/env python3
"""Dictionary Coverage Audit — DICT-001

Fetches words from Super Flashcards, Etymython, and Etymology Graph APIs,
queries Portfolio RAG semantic search for each word against each dictionary,
and records matches in the word_dictionary_links table.

Usage:
    # From portfolio-rag root, with DB env vars set:
    python -m scripts.audit_dictionary_coverage

    # Or via Cloud Run job / one-off container
    python scripts/audit_dictionary_coverage.py
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from typing import Optional

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────

SF_API = "https://learn.rentyourcio.com"
ETYMYTHON_API = "https://etymython.rentyourcio.com"
EFG_API = "https://efg.rentyourcio.com"
RAG_API = os.getenv("RAG_API", "https://portfolio-rag-57478301787.us-central1.run.app")

DICTIONARIES = ["beekes", "kroonen", "de_vaan", "wiktionary", "dcc", "watkins"]

# Map dictionary name → RAG collection + source_file filter
DICT_CONFIG = {
    "beekes": {
        "collection": "etymology",
        "sources": "698401131-Beekes-Etymological-Dictionary-Greek-1.pdf",
    },
    "kroonen": {
        "collection": "etymology",
        "sources": "Etymological Dictionary of Proto-Germanic.pdf",
    },
    "de_vaan": {
        "collection": "etymology",
        "sources": "de Vaan - Etymological Dictionary of Latin (2008).pdf",
    },
    "watkins": {
        "collection": "etymology",
        "sources": "Watkins - American Heritage Dictionary of Indo-European Roots (1985).epub",
    },
    "wiktionary": {"collection": "wiktionary", "sources": None},
    "dcc": {"collection": "dcc", "sources": None},
}

# Minimum semantic similarity score to count as a match
MIN_SCORE = 0.25

# ── DB helpers ───────────────────────────────────────────────────────

DB_SERVER = os.getenv("DB_SERVER", "35.224.242.223")
DB_NAME = os.getenv("DB_NAME", "MetaPM")
DB_USER = os.getenv("DB_USER", "sqlserver")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")


def get_connection():
    import pyodbc

    server = DB_SERVER
    if "," not in server and ":" not in server and "/" not in server:
        server = f"{server},1433"

    conn_str = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={server};"
        f"DATABASE={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        "TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str, timeout=30)
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-16-le")
    conn.setencoding(encoding="utf-16-le")
    return conn


def ensure_table(conn):
    """Create word_dictionary_links if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (
            SELECT * FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'word_dictionary_links'
        )
        BEGIN
            CREATE TABLE word_dictionary_links (
                id            INT IDENTITY PRIMARY KEY,
                word          NVARCHAR(200) NOT NULL,
                language      NVARCHAR(10) NOT NULL,
                app_source    NVARCHAR(50) NOT NULL,
                entry_point   NVARCHAR(100) NOT NULL,
                dictionary    NVARCHAR(50) NOT NULL,
                rag_chunk_id  NVARCHAR(200) NULL,
                match_score   FLOAT NULL,
                matched_at    DATETIME2 DEFAULT GETUTCDATE(),
                UNIQUE (word, language, app_source, entry_point, dictionary)
            );
            PRINT 'Created word_dictionary_links table';
        END
    """)
    conn.commit()
    logger.info("word_dictionary_links table ensured")


def upsert_link(
    conn,
    word: str,
    language: str,
    app_source: str,
    entry_point: str,
    dictionary: str,
    rag_chunk_id: Optional[str],
    match_score: Optional[float],
):
    """Insert or update a word-dictionary link."""
    cursor = conn.cursor()
    cursor.execute(
        """
        MERGE word_dictionary_links AS target
        USING (SELECT ? AS word, ? AS language, ? AS app_source,
                      ? AS entry_point, ? AS dictionary) AS source
        ON target.word = source.word
           AND target.language = source.language
           AND target.app_source = source.app_source
           AND target.entry_point = source.entry_point
           AND target.dictionary = source.dictionary
        WHEN MATCHED THEN
            UPDATE SET rag_chunk_id = ?, match_score = ?, matched_at = GETUTCDATE()
        WHEN NOT MATCHED THEN
            INSERT (word, language, app_source, entry_point, dictionary, rag_chunk_id, match_score)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        word, language, app_source, entry_point, dictionary,
        rag_chunk_id, match_score,
        word, language, app_source, entry_point, dictionary, rag_chunk_id, match_score,
    )


# ── RAG query ────────────────────────────────────────────────────────

def query_rag(client: httpx.Client, word: str, dictionary: str) -> Optional[dict]:
    """Query RAG semantic search for a word in a specific dictionary.

    Returns the best match (highest score) or None if below threshold.
    """
    config = DICT_CONFIG[dictionary]
    params = {"q": word, "collection": config["collection"], "n": "1"}
    if config["sources"]:
        params["sources"] = config["sources"]

    try:
        resp = client.get(f"{RAG_API}/semantic", params=params, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        best = results[0]
        score = best.get("score", 0)
        if score < MIN_SCORE:
            return None
        # Extract a chunk ID from the result
        chunk_id = best.get("id") or best.get("source", "")[:200]
        return {"chunk_id": chunk_id, "score": score}
    except Exception as e:
        logger.warning(f"RAG query failed for '{word}' in {dictionary}: {e}")
        return None


# ── App data fetchers ────────────────────────────────────────────────

def fetch_super_flashcards(client: httpx.Client) -> list[dict]:
    """Fetch all cards from Super Flashcards API."""
    words = []
    try:
        resp = client.get(f"{SF_API}/api/flashcards", params={"limit": "2000"}, timeout=30)
        if resp.status_code != 200:
            logger.error(f"SF API returned {resp.status_code}")
            return words
        cards = resp.json()
        if isinstance(cards, dict):
            cards = cards.get("cards", cards.get("data", []))
        for card in cards:
            word = card.get("word") or card.get("front") or card.get("term")
            if not word:
                continue
            lang = card.get("language_code") or card.get("language") or "unknown"
            if isinstance(lang, dict):
                lang = lang.get("code", "unknown")
            # Normalize language codes
            lang = lang.lower()[:5]
            words.append({
                "word": word.strip(),
                "language": lang,
                "entry_points": ["definition"],
            })
            # Check for etymology/cognate fields
            if card.get("etymology"):
                words[-1]["entry_points"].append("etymology")
            if card.get("cognates") or card.get("related_words"):
                words[-1]["entry_points"].append("cognate")
        logger.info(f"SF: fetched {len(words)} cards")
    except Exception as e:
        logger.error(f"SF fetch failed: {e}")
    return words


def fetch_etymython(client: httpx.Client) -> list[dict]:
    """Fetch all figures from Etymython API."""
    words = []
    try:
        resp = client.get(f"{ETYMYTHON_API}/api/v1/figures", timeout=30)
        if resp.status_code != 200:
            logger.error(f"Etymython API returned {resp.status_code}")
            return words
        figures = resp.json()
        if isinstance(figures, dict):
            figures = figures.get("figures", figures.get("data", []))
        for fig in figures:
            name = fig.get("name") or fig.get("greek_name")
            if not name:
                continue
            # Greek name → definition entry point
            words.append({
                "word": name.strip(),
                "language": "el",
                "entry_points": ["definition"],
            })
            # PIE root if available
            pie_root = fig.get("pie_root") or fig.get("pie")
            if pie_root:
                words.append({
                    "word": pie_root.strip().strip("*"),
                    "language": "pie",
                    "entry_points": ["pie_root"],
                })
            # Cognates
            cognates = fig.get("cognates") or fig.get("english_cognates") or []
            if isinstance(cognates, str):
                cognates = [c.strip() for c in cognates.split(",") if c.strip()]
            for cog in cognates[:5]:  # Limit to avoid explosion
                cog_word = cog.get("word", cog) if isinstance(cog, dict) else cog
                if cog_word:
                    words.append({
                        "word": str(cog_word).strip(),
                        "language": "en",
                        "entry_points": ["cognate"],
                    })
        logger.info(f"Etymython: fetched {len(words)} word entries from {len(figures)} figures")
    except Exception as e:
        logger.error(f"Etymython fetch failed: {e}")
    return words


def fetch_efg(client: httpx.Client) -> list[dict]:
    """Fetch all nodes from Etymology Graph (EFG) API."""
    words = []
    try:
        resp = client.get(f"{EFG_API}/api/nodes", timeout=30)
        if resp.status_code != 200:
            # Try alternative endpoint
            resp = client.get(f"{EFG_API}/api/words", timeout=30)
            if resp.status_code != 200:
                logger.error(f"EFG API returned {resp.status_code}")
                return words
        nodes = resp.json()
        if isinstance(nodes, dict):
            nodes = nodes.get("nodes", nodes.get("words", nodes.get("data", [])))
        for node in nodes:
            word = node.get("word") or node.get("label") or node.get("name")
            if not word:
                continue
            lang = node.get("language") or node.get("lang") or "unknown"
            lang = lang.lower()[:5]
            words.append({
                "word": word.strip(),
                "language": lang,
                "entry_points": ["graph_node"],
            })
        logger.info(f"EFG: fetched {len(words)} nodes")
    except Exception as e:
        logger.error(f"EFG fetch failed: {e}")
    return words


# ── Main audit loop ──────────────────────────────────────────────────

def run_audit(dry_run: bool = False):
    """Execute the full dictionary coverage audit."""
    logger.info("=" * 60)
    logger.info("DICT-001: Dictionary Coverage Audit starting")
    logger.info("=" * 60)

    if not dry_run:
        conn = get_connection()
        ensure_table(conn)
    else:
        conn = None
        logger.info("DRY RUN — no DB writes")

    client = httpx.Client()
    stats = {"total_queries": 0, "total_matches": 0, "by_app": {}}

    # Fetch words from all apps
    app_data = {
        "super-flashcards": fetch_super_flashcards(client),
        "etymython": fetch_etymython(client),
        "efg": fetch_efg(client),
    }

    for app_source, words in app_data.items():
        app_stats = {"words": len(words), "queries": 0, "matches": 0}
        logger.info(f"\n--- Auditing {app_source}: {len(words)} word entries ---")

        for i, entry in enumerate(words):
            word = entry["word"]
            language = entry["language"]

            for entry_point in entry["entry_points"]:
                for dictionary in DICTIONARIES:
                    app_stats["queries"] += 1
                    stats["total_queries"] += 1

                    result = query_rag(client, word, dictionary)

                    if result:
                        app_stats["matches"] += 1
                        stats["total_matches"] += 1

                        if not dry_run:
                            upsert_link(
                                conn,
                                word=word,
                                language=language,
                                app_source=app_source,
                                entry_point=entry_point,
                                dictionary=dictionary,
                                rag_chunk_id=result["chunk_id"],
                                match_score=result["score"],
                            )

            # Commit every 50 words and log progress
            if not dry_run and (i + 1) % 50 == 0:
                conn.commit()
                logger.info(f"  [{app_source}] {i + 1}/{len(words)} words processed")

            # Rate limit: avoid hammering RAG
            if (i + 1) % 20 == 0:
                time.sleep(0.5)

        if not dry_run and conn:
            conn.commit()

        stats["by_app"][app_source] = app_stats
        logger.info(
            f"  {app_source} complete: {app_stats['matches']}/{app_stats['queries']} "
            f"matches from {app_stats['words']} words"
        )

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("AUDIT COMPLETE")
    logger.info(f"  Total queries: {stats['total_queries']}")
    logger.info(f"  Total matches: {stats['total_matches']}")
    for app, s in stats["by_app"].items():
        logger.info(f"  {app}: {s['matches']} matches from {s['words']} words")
    logger.info("=" * 60)

    if not dry_run and conn:
        conn.close()

    client.close()
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dictionary Coverage Audit")
    parser.add_argument("--dry-run", action="store_true", help="Query RAG but don't write to DB")
    args = parser.parse_args()

    if not DB_PASSWORD and not args.dry_run:
        logger.error("DB_PASSWORD not set. Use --dry-run or set DB_PASSWORD env var.")
        sys.exit(1)

    run_audit(dry_run=args.dry_run)
