"""Ingestion pipelines for portfolio, etymology, and jazz_theory collections."""

import logging
import os
import re
from datetime import datetime, timezone

from app.core.config import settings
from app.core.vectorstore import vector_store
from app.core.chunking import chunk_markdown, chunk_pdf_pages
from app.services.github import GitHubClient

logger = logging.getLogger(__name__)

# Portfolio source files — specific docs for semantic search
PORTFOLIO_FILES = [
    {"repo": "metapm", "path": "PROJECT_KNOWLEDGE.md", "project": "MetaPM"},
    {"repo": "project-methodology", "path": "PROJECT_KNOWLEDGE.md", "project": "project-methodology"},
    {"repo": "project-methodology", "path": "templates/CC_Bootstrap_v1.md", "project": "project-methodology"},
    {"repo": "project-methodology", "path": "docs/CAI_Outbound_CC_Prompt_Standard.md", "project": "project-methodology"},
    {"repo": "project-methodology", "path": "docs/CAI_Inbound_CC_Handoff_Standard.md", "project": "project-methodology"},
    {"repo": "ArtForge", "path": "PROJECT_KNOWLEDGE.md", "project": "ArtForge"},
    {"repo": "harmonylab", "path": "PROJECT_KNOWLEDGE.md", "project": "HarmonyLab"},
    {"repo": "Super-Flashcards", "path": "PROJECT_KNOWLEDGE.md", "project": "SuperFlashcards"},
    {"repo": "etymython", "path": "PROJECT_KNOWLEDGE.md", "project": "Etymython"},
    {"repo": "portfolio-rag", "path": "PROJECT_KNOWLEDGE.md", "project": "PortfolioRAG"},
]

# Non-GitHub repos: PK files stored in GCS (gs://corey-handoff-bridge/pk-docs/)
GCS_PORTFOLIO_FILES = [
    {"gcs_path": "pk-docs/personal-assistant/PROJECT_KNOWLEDGE.md", "source": "personal-assistant/PROJECT_KNOWLEDGE.md", "project": "PersonalAssistant"},
    {"gcs_path": "pk-docs/pie-network-graph/PROJECT_KNOWLEDGE.md", "source": "pie-network-graph/PROJECT_KNOWLEDGE.md", "project": "PIENetworkGraph"},
]

GCS_PK_BUCKET = "corey-handoff-bridge"

# Beekes PDF filename (bundled in Docker image)
BEEKES_PDF = "698401131-Beekes-Etymological-Dictionary-Greek-1.pdf"


async def ingest_portfolio() -> dict:
    """Ingest portfolio markdown files into ChromaDB portfolio collection.

    Fetches specific files from GitHub, chunks by H2/H3 headers,
    embeds with OpenAI, and upserts into ChromaDB.
    Returns ingestion stats.
    """
    if not settings.OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not set", "chunks": 0}

    # Try with token; if it fails (expired PAT), retry without auth (repos are public)
    clients = [
        GitHubClient(token=settings.GITHUB_TOKEN, owner=settings.REPO_OWNER),
        GitHubClient(token="", owner=settings.REPO_OWNER),
    ] if settings.GITHUB_TOKEN else [
        GitHubClient(token="", owner=settings.REPO_OWNER),
    ]

    # Delete collection for clean re-ingestion
    vector_store.delete_collection("portfolio")

    ingested_at = datetime.now(timezone.utc).isoformat()
    all_chunks = []
    file_stats = []
    working_client = None

    for file_info in PORTFOLIO_FILES:
        source_file = f"{file_info['repo']}/{file_info['path']}"
        content = None
        for client in ([working_client] if working_client else clients):
            try:
                content, _ = await client.fetch_file(file_info["repo"], file_info["path"])
                working_client = client
                break
            except Exception:
                continue
        if content is None:
            err = "All fetch attempts failed (token may be expired)"
            logger.error(f"Failed to fetch {source_file}: {err}")
            file_stats.append({"file": source_file, "chunks": 0, "error": err})
            continue
        chunks = chunk_markdown(content, source_file, file_info["project"])
        for chunk in chunks:
            chunk["metadata"]["ingested_at"] = ingested_at
        all_chunks.extend(chunks)
        file_stats.append({"file": source_file, "chunks": len(chunks)})
        logger.info(f"Chunked {source_file}: {len(chunks)} chunks")

    # Fetch non-GitHub PK files from GCS
    try:
        from google.cloud import storage as gcs_storage
        gcs_client = gcs_storage.Client()
        bucket = gcs_client.bucket(GCS_PK_BUCKET)
        for gcs_file in GCS_PORTFOLIO_FILES:
            try:
                blob = bucket.blob(gcs_file["gcs_path"])
                if not blob.exists():
                    logger.warning(f"GCS file not found: gs://{GCS_PK_BUCKET}/{gcs_file['gcs_path']}")
                    file_stats.append({"file": gcs_file["source"], "chunks": 0, "error": "not found in GCS"})
                    continue
                content = blob.download_as_text(encoding="utf-8")
                chunks = chunk_markdown(content, gcs_file["source"], gcs_file["project"])
                for chunk in chunks:
                    chunk["metadata"]["ingested_at"] = ingested_at
                all_chunks.extend(chunks)
                file_stats.append({"file": gcs_file["source"], "chunks": len(chunks)})
                logger.info(f"GCS chunked {gcs_file['source']}: {len(chunks)} chunks")
            except Exception as e:
                logger.error(f"Failed to fetch GCS file {gcs_file['source']}: {e}")
                file_stats.append({"file": gcs_file["source"], "chunks": 0, "error": str(e)})
    except ImportError:
        logger.warning("google-cloud-storage not available, skipping GCS PK files")

    if not all_chunks:
        return {"chunks": 0, "files": file_stats}

    # Generate unique IDs — append index to handle duplicate section headers
    ids = [f"{c['metadata']['source_file']}::{c['metadata']['section']}::{i}" for i, c in enumerate(all_chunks)]
    documents = [c["text"] for c in all_chunks]
    metadatas = [c["metadata"] for c in all_chunks]

    vector_store.upsert("portfolio", ids, documents, metadatas)
    logger.info(f"Portfolio ingestion complete: {len(all_chunks)} chunks from {len(PORTFOLIO_FILES)} files")

    return {"chunks": len(all_chunks), "files": file_stats}


async def ingest_etymology(pdf_path: str = None) -> dict:
    """Ingest Beekes PDF into ChromaDB etymology collection.

    Extracts text from PDF pages, chunks, embeds, and upserts.
    """
    if not settings.OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not set", "chunks": 0}

    if pdf_path is None:
        # Look for PDF in app directory (Docker image) or repo root
        candidates = [
            os.path.join("/app", BEEKES_PDF),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), BEEKES_PDF),
        ]
        for p in candidates:
            if os.path.exists(p):
                pdf_path = p
                break
        if pdf_path is None:
            return {"error": f"Beekes PDF not found. Searched: {candidates}", "chunks": 0}

    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return {"error": "PyPDF2 not installed", "chunks": 0}

    logger.info(f"Reading PDF: {pdf_path}")
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)

    logger.info(f"Extracted {len(pages)} pages from PDF")

    chunks = chunk_pdf_pages(pages, BEEKES_PDF)
    if not chunks:
        return {"chunks": 0, "pages": len(pages), "error": "No viable chunks extracted"}

    # Delete collection for clean re-ingestion
    vector_store.delete_collection("etymology")

    ingested_at = datetime.now(timezone.utc).isoformat()
    for chunk in chunks:
        chunk["metadata"]["ingested_at"] = ingested_at

    ids = [f"beekes::p{c['metadata']['page_number']}::{i}" for i, c in enumerate(chunks)]
    documents = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    vector_store.upsert("etymology", ids, documents, metadatas)

    logger.info(f"Etymology ingestion complete: {len(chunks)} chunks from {len(pages)} pages")
    return {"chunks": len(chunks), "pages": len(pages)}


# Jazz theory seed files — bundled in Docker image under data/jazz_theory/
JAZZ_THEORY_DIR = "data/jazz_theory"


async def ingest_jazz_theory() -> dict:
    """Ingest jazz theory markdown files into ChromaDB jazz_theory collection.

    Reads .md files from data/jazz_theory/, chunks by H2/H3 headers,
    embeds with OpenAI, and upserts into ChromaDB.
    """
    if not settings.OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not set", "chunks": 0}

    # Look for seed files in Docker image (/app/) or repo root
    candidates = [
        os.path.join("/app", JAZZ_THEORY_DIR),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), JAZZ_THEORY_DIR),
    ]
    data_dir = None
    for p in candidates:
        if os.path.isdir(p):
            data_dir = p
            break
    if data_dir is None:
        return {"error": f"Jazz theory data dir not found. Searched: {candidates}", "chunks": 0}

    md_files = sorted(f for f in os.listdir(data_dir) if f.endswith(".md"))
    if not md_files:
        return {"error": f"No .md files in {data_dir}", "chunks": 0}

    # Delete collection for clean re-ingestion
    vector_store.delete_collection("jazz_theory")

    ingested_at = datetime.now(timezone.utc).isoformat()
    all_chunks = []
    file_stats = []

    for filename in md_files:
        filepath = os.path.join(data_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Derive topic from H1 heading
        h1_match = re.match(r"^#\s+(.+)", content)
        topic = h1_match.group(1).strip() if h1_match else filename.replace(".md", "").replace("_", " ")

        chunks = chunk_markdown(content, filename, "jazz_theory")
        for chunk in chunks:
            chunk["metadata"]["ingested_at"] = ingested_at
            chunk["metadata"]["topic"] = topic
            chunk["metadata"]["collection"] = "jazz_theory"
        all_chunks.extend(chunks)
        file_stats.append({"file": filename, "chunks": len(chunks), "topic": topic})
        logger.info(f"Jazz theory: chunked {filename}: {len(chunks)} chunks (topic: {topic})")

    if not all_chunks:
        return {"chunks": 0, "files": file_stats}

    ids = [f"jazz::{c['metadata']['source_file']}::{c['metadata']['section']}::{i}" for i, c in enumerate(all_chunks)]
    documents = [c["text"] for c in all_chunks]
    metadatas = [c["metadata"] for c in all_chunks]

    vector_store.upsert("jazz_theory", ids, documents, metadatas)
    logger.info(f"Jazz theory ingestion complete: {len(all_chunks)} chunks from {len(md_files)} files")

    return {"chunks": len(all_chunks), "files": file_stats}
