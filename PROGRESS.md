# Progress

> Shared memory between work sessions, for humans and agents. Update it before you stop.
> The tack session-start hook shows the end of this file to the agent automatically.

## Decisions

<!-- YYYY-MM-DD: decision, and why. Newest last. -->
- 2026-11-21: Adopted tack for checks, guardrails, and agent workflow.
- 2026-11-21: **Project purpose:** a portfolio/learning project to build something complex and grow
  architecture skills. Real users would be a bonus, not the target. Optimise for depth and a strong demo.
- 2026-11-21: **Pivoted away from an end-to-end "set up your own RAG" website.** That's crowded
  (AnythingLLM, Open WebUI, Dify, Ragie, Vectara, Vercel templates) and reads as tutorial-level on a
  resume. We build infrastructure for a hard, under-served part instead.
- 2026-11-21: **Chose: vector-index sync engine** (incremental, idempotent, crash-safe sync +
  blue/green embedding-model migration) **with a built-in retrieval eval gate.** Alternatives considered:
  retrieval regression testing (crowded: Ragas, DeepEval, LangSmith, Phoenix), permission-aware
  retrieval (strong but needs real SaaS integrations to demo), document parsing/chunking (very crowded,
  ML swamp). Sync engine has low competition (CocoIndex, parts of LlamaIndex/Airbyte) and the deepest
  architecture content. Full scope in `SPEC.md`.
- 2026-11-21: **No web UI and no LLM answer generation in v1.** We serve retrieval only, so Claude isn't
  needed yet. The deliverable is a library + CLI; the demo is README + benchmarks + recorded terminal session.
- 2026-11-24: **Stack approved:** Python 3.12 + uv + hatchling; Typer CLI; psycopg 3 + pgvector with
  plain SQL (no ORM, for exact transaction control over idempotency and atomic cutover); Ruff, Pyright
  strict, pytest; testcontainers for integration tests. Chosen over Rust + clap for the embeddings
  ecosystem and build speed.
- 2026-11-24: CLI exposed as both `riches-to-rags` and the short alias `r2r` (nicer in demos).
  Version is single-sourced from package metadata.

## Done

- 2026-11-21: `SPEC.md` written (goal, v1 scope, non-goals, constraints, open questions).
- 2026-11-21: Project description added to `AGENTS.md`.
- 2026-11-24: Bootstrapped skeleton: `uv init --package`, deps added, Typer app (`src/riches_to_rags/cli.py`)
  with a `version` command, smoke tests (`tests/test_cli.py`), Ruff/Pyright/pytest config in
  `pyproject.toml`, `.gitignore`, `README.md`. `tack detect --write` → status active; `tack verify` green.

## Current work

Bootstrap complete. Ready for the first v1 slice.

**Open blocker for integration tests:** Docker Desktop is installed on Windows but WSL integration is
off, so `docker` fails inside WSL. Fix: Docker Desktop → Settings → Resources → WSL Integration →
enable the distro → Apply & Restart; check with `docker run --rm hello-world`.

## Next

1. Enable Docker WSL integration (above).
2. Build v1 in thin vertical slices:
   1. Source interface + local-directory source + change detection (added/modified/deleted)
   2. Chunking + chunk hashing + fake embedder + pgvector storage + `sync` / `status` / `search`
   3. Idempotent/resumable sync with fault-injection tests
   4. Embedding cache
   5. Versioned indexes + `migrate build | cutover | rollback`
   6. Eval set + recall@k / MRR + eval-gated cutover
   7. Git-repo source; real embedding provider
   8. Benchmarks + recorded demo + README polish
3. Open questions to settle along the way (see `SPEC.md`): embedding provider, chunking strategy,
   whether to add a worker/HTTP service in v2.
