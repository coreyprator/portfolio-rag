"""Chunking strategies for markdown files and PDFs."""

import re


def chunk_markdown(content: str, source_file: str, project: str) -> list[dict]:
    """Split markdown by H2/H3 headers into chunks with metadata.

    Rules:
    - Split on ## and ### headers
    - Min chunk: 100 characters (skip shorter)
    - Max chunk: 1500 characters (split at sentence boundary)
    - Include header text as first line of chunk
    """
    sections = re.split(r"(?=^#{2,3}\s)", content, flags=re.MULTILINE)
    chunks = []

    for section in sections:
        section = section.strip()
        if len(section) < 100:
            continue

        header_match = re.match(r"^#{2,3}\s+(.+)", section)
        header = header_match.group(1).strip() if header_match else "Introduction"

        if len(section) > 1500:
            sub_chunks = _split_at_sentence(section, 1500)
            for i, sub in enumerate(sub_chunks):
                label = f"{header} (part {i + 1})" if len(sub_chunks) > 1 else header
                chunks.append({
                    "text": sub,
                    "metadata": {
                        "source_file": source_file,
                        "section": label,
                        "project": project,
                    },
                })
        else:
            chunks.append({
                "text": section,
                "metadata": {
                    "source_file": source_file,
                    "section": header,
                    "project": project,
                },
            })
    return chunks


def chunk_pdf_pages(pages: list[str], source_file: str) -> list[dict]:
    """Chunk extracted PDF pages into searchable chunks.

    Rules:
    - Skip near-empty pages (< 50 chars)
    - Max chunk: 1500 chars (split at paragraph boundary)
    - Store page_number and entry_headword in metadata
    """
    chunks = []
    for i, page_text in enumerate(pages):
        page_text = page_text.strip()
        if len(page_text) < 50:
            continue

        page_num = i + 1
        headword_match = re.search(r"[A-Za-z\u0370-\u03FF\u1F00-\u1FFF]+", page_text)
        headword = headword_match.group(0) if headword_match else ""

        if len(page_text) > 1500:
            sub_chunks = _split_at_paragraph(page_text, 1500)
            for j, sub in enumerate(sub_chunks):
                chunks.append({
                    "text": sub,
                    "metadata": {
                        "source_file": source_file,
                        "page_number": page_num,
                        "entry_headword": headword,
                    },
                })
        else:
            chunks.append({
                "text": page_text,
                "metadata": {
                    "source_file": source_file,
                    "page_number": page_num,
                    "entry_headword": headword,
                },
            })
    return chunks


def _split_at_sentence(text: str, max_len: int) -> list[str]:
    """Split text at sentence boundaries to stay under max_len."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) > max_len and current:
            chunks.append(current.strip())
            current = s
        else:
            current = (current + " " + s) if current else s
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text]


def _split_at_paragraph(text: str, max_len: int) -> list[str]:
    """Split text at paragraph boundaries to stay under max_len."""
    paragraphs = re.split(r"\n\n+", text)
    chunks = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) > max_len and current:
            chunks.append(current.strip())
            current = p
        else:
            current = (current + "\n\n" + p) if current else p
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text]
