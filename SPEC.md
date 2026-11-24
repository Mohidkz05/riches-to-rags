# riches-to-rags: spec

> The source of truth for **what** we're building and **why**. Keep it short. Update it when scope changes.

## Goal

A sync engine that keeps a vector index correct as its sources change. Most RAG pipelines "ingest once"
and then quietly rot: edited documents keep stale chunks, deleted pages stay retrievable, a crash halfway
through leaves a half-written index, and switching embedding models means a risky full rebuild with
downtime. riches-to-rags treats the vector index like a replica of the sources and keeps it in sync:
incremental, idempotent, crash-safe, with zero-downtime embedding-model migrations gated by a retrieval
eval.

Secondary goal (the honest one): a deep, well-architected portfolio project for learning distributed-
systems and data-pipeline design.

## Users

- **Primary:** developers who run their own RAG system and need its index to stay fresh and trustworthy
  without full re-ingests.
- **Maintainer:** one developer (the author), so few moving parts and boring infrastructure.

## v1 scope

- [ ] **Source interface** (pluggable) that lists documents with a stable ID and a content fingerprint
- [ ] Built-in sources: **local directory** and **git repository** (URL list is a stretch goal)
- [ ] **Change detection:** diff the source against the index state: added / modified / deleted / unchanged
- [ ] **Chunk-level incremental updates:** content-hash chunks so editing a document re-embeds only the
      chunks that actually changed; deletes remove every vector for that document
- [ ] **Idempotent, resumable sync:** re-running a sync after a crash at any point converges to the same
      correct state, with no duplicate or orphaned vectors (proven by fault-injection tests)
- [ ] **Embedding cache** keyed by (model, chunk hash) so identical text is never embedded twice
- [ ] **Versioned indexes + blue/green model migration:** build a new index for a new embedding model or
      chunking config alongside the live one, then switch atomically with no query downtime; roll back
- [ ] **Eval gate:** a small eval set (queries → expected documents) scored with recall@k and MRR; a
      migration's cutover is refused if retrieval quality regresses past a threshold
- [ ] **Query API:** `search(query, k)` against the live index version, used by the eval and the demo
- [ ] **CLI:** `init`, `sync`, `status`, `search`, `migrate build | eval | cutover | rollback`
- [ ] **Postgres + pgvector** as the storage backend (index state, chunks, vectors in one database)
- [ ] **Benchmark + demo:** reproducible numbers (e.g. embedding calls saved on a re-sync after 1% of a
      corpus changed) and a recorded terminal demo for the README

## Non-goals

- A web UI, chat interface, or answer generation (that's the commodity part; we serve retrieval)
- Advanced document parsing (PDF layout, tables, OCR). v1 handles text, Markdown and source code
- Other vector stores (Qdrant, Pinecone, ...). The storage layer is an interface, but only pgvector ships
- Permission/ACL-aware retrieval
- Multi-tenancy, auth, hosted service, billing
- Real-time streaming (webhooks / CDC from SaaS tools); sync is triggered by command or schedule
- Distributed workers across machines. One process, built so that could change later

## Constraints

- Python (best ecosystem for embeddings/ML, and the stronger signal for AI-engineering roles)
- Solo-maintained, low budget: one Postgres database, embeddings provider behind an interface with a
  deterministic fake for tests so CI costs nothing
- API keys live in `.env` only; `.env.example` documents the names
- Integration tests run against a real pgvector Postgres via Docker + testcontainers

## Open questions

- **Embedding provider:** Voyage AI (Anthropic's recommended partner) vs. OpenAI vs. a local
  sentence-transformers model (free, offline, slower). Interface first; pick when building it.
- **Chunking strategy** for v1: fixed token windows with overlap vs. structure-aware (Markdown headings,
  code symbols). Content-defined boundaries help incremental updates; worth an experiment.
- **Library vs. service:** v1 is a library + CLI. Whether to add a long-running worker/HTTP API is a v2 call.
