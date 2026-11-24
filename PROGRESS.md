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
- 2026-11-24: **A listing is complete or it fails.** A document missing from `list_documents()` is
  diffed as deleted, so unreadable dirs/files raise `SourceReadError` instead of being skipped
  (otherwise a transient EACCES or flaky mount would wipe part of the index). `skipped` is only for
  files that can never be text (binary, non-UTF-8, too large, symlink, unsafe name), which *should* be
  removed from the index. Workaround for a permanently unreadable file: exclude it.
- 2026-11-24: **Local source reads go through directory file descriptors** (`os.fwalk`, `dir_fd`,
  `O_NOFOLLOW`, `O_NONBLOCK`, checks on `fstat` of the open fd, bounded read). Security review showed
  check-then-open-by-path let a writer inside root swap a file or directory for a symlink and get
  files outside root read, or hang the sync on a FIFO. Cost: POSIX only (fine: Linux/macOS/WSL).
- 2026-11-24: Fingerprint is SHA-256 of bytes (not mtime). Possible later optimisation: skip hashing
  when (size, mtime) is unchanged since last sync. CRLF vs LF changes the hash (bytes did change);
  revisit if Windows checkouts cause churn.

## Done

- 2026-11-21: `SPEC.md` written (goal, v1 scope, non-goals, constraints, open questions).
- 2026-11-21: Project description added to `AGENTS.md`.
- 2026-11-24: Bootstrapped skeleton: `uv init --package`, deps added, Typer app (`src/riches_to_rags/cli.py`)
  with a `version` command, smoke tests (`tests/test_cli.py`), Ruff/Pyright/pytest config in
  `pyproject.toml`, `.gitignore`, `README.md`. `tack detect --write` → status active; `tack verify` green.
- 2026-11-24: **Slice 1 done:** `Source` protocol + `SourceReadError`, `LocalDirectorySource`
  (fd-based, symlink/FIFO/race-safe), pure `diff()` → `ChangeSet`, `r2r scan`. 51 tests incl.
  hypothesis properties for diff and deterministic race tests. Passed reviewer + security-reviewer
  (two rounds; all findings fixed).

## Current work

Slice 1 complete (see Done). Next up: slice 2.

Docker works inside WSL (2026-11-24), so testcontainers integration tests are unblocked.
Repo is public: https://github.com/Mohidkz05/riches-to-rags

## Next

1. Build v1 in thin vertical slices:
   1. ~~Source interface + local-directory source + change detection~~ (done 2026-11-24)
   2. Chunking + chunk hashing + fake embedder + pgvector storage + `sync` / `status` / `search`
   3. Idempotent/resumable sync with fault-injection tests
   4. Embedding cache
   5. Versioned indexes + `migrate build | cutover | rollback`
   6. Eval set + recall@k / MRR + eval-gated cutover
   7. Git-repo source; real embedding provider
   8. Benchmarks + recorded demo + README polish
2. Open questions to settle along the way (see `SPEC.md`): embedding provider, chunking strategy,
   whether to add a worker/HTTP service in v2.
