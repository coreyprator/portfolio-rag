SESSION COMPLETE
================
PTH: 9F1D | Sprint: EFG-DCC-002
Portfolio RAG version: 2.3.0 → 2.4.0
MetaPM code: PR-013 [cc_complete, checkpoint 81CD]
Revision: portfolio-rag-00050-tkd

DCC chunks ingested: 519/532
(519 DCC words have frequency_rank; 13 DCC-imported words lack rank and were filtered)
/health dcc collection count: 519

Semantic search samples:
  "warfare battle": πόλεμος (#187 war), μάχη (#323 battle), στρατιά (#497 army), πολεμέω (#459 make war), στρατός (#503 army) — all "War and Peace" semantic group ✓
  "gods religion divine": θεῖος (#434 divine), θεός (#49 god), δαίμων (#482 spirit/god), ἱερός (#222 holy/divine) — all "Religion" semantic group ✓
  "most frequent nouns": ὄνομα (#127 name), εἰκός (#488 likelihood), θυγάτηρ (#368 daughter) ✓

Changes:
- app/api/ingest.py: Added POST /ingest/custom endpoint, CustomChunk/CustomIngestRequest models, ALLOWED_CUSTOM_COLLECTIONS
- app/api/query.py: Added "dcc" to VALID_COLLECTIONS
- app/core/vectorstore.py: Added "dcc" to collection_counts() and default query loop
- app/core/config.py: VERSION 2.3.0 → 2.4.0
- scripts/export_dcc_chunks.py: New script — fetches DCC words from EFG API, formats markdown chunks, POSTs to /ingest/custom

Acceptance criteria:
- [x] POST /ingest/custom returns success (not 404)
- [x] /health shows dcc collection with 519 chunks after ingestion
- [x] POST /semantic with collection=dcc returns relevant Greek words for "warfare" query
- [x] POST /semantic with collection=dcc returns θεός for "gods religion" query
- [x] Chunk metadata includes frequency_rank, lemma, definition, part_of_speech
- [x] Existing collections (portfolio 572, etymology 1835, code 521, jazz_theory 17) unaffected
- [x] Portfolio RAG version 2.4.0 at /health
- [x] EFG-DCC-002 at cc_complete in MetaPM

Deviations:
- 519 chunks instead of 532: 13 DCC-imported words lack frequency_rank and were filtered out.
  The sprint prompt specified "filtered to DCC-imported words" with rank sort — 13 have no rank.
  All 519 ranked words successfully ingested.
