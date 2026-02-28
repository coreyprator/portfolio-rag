# INTENT.md -- Portfolio RAG core pipeline

## Primary Intent
An indexed, version-aware search service for all portfolio documentation. Bootstrap standards, PROJECT_KNOWLEDGE.md files, software repositories, CLAUDE.md files, and other facts about each project. Replaces the current manual sequential search with instant semantic retrieval.

## Success Is
- A CC session can query "what is the latest Bootstrap standard for deploy-first auth?" and get the current version instantly, not a stale or outdated version.
- Any fact about any project (database name, OAuth client, deploy procedure) is retrievable in seconds.
- The chronology enforcement ensures current documents always rank above superseded versions.
- The investment in indexing pays out in fewer than two queries versus the sequential search alternative.

## Success Is NOT
- A replacement for PK.md as the canonical document. PK.md is the source of truth. The RAG indexes it.
- A general-purpose search engine. This serves the portfolio's documentation, not the open web.
- The Greek Etymology RAG. That's a separate project with a different corpus and different purpose.

## Decision Boundaries
- Start with the minimum viable corpus: 8 PK.md files and Bootstrap. If that alone justifies the infrastructure, expand from there.
- Document metadata (version, timestamp, project, supersedes) is mandatory for every indexed chunk.
- Re-ingestion can be manual initially. Automate via git hooks or GCS watchers when the process is proven.

## Anti-Goals
- Over-engineering before proving value with a small corpus.
- Conflating this with the etymology RAG. Different data, different purpose, different users.

## This Project Serves Portfolio Intents
- Workflow automation: Eliminates the most frustrating knowledge-loss problem across CC sessions.
- Cognitive vitality: RAG technology is something Corey wants to understand better. It has a lot of potential.

## Communication Standards
8th grade reading level. Short sentences. No em dashes. No filler. Direct.
