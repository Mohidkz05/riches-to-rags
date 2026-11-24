# riches-to-rags

A sync engine that keeps a vector index (Postgres + pgvector) correct as its sources change.
Re-syncs are incremental, idempotent and crash-safe, and embedding-model migrations run
blue/green with zero downtime, gated by a retrieval eval.

> Status: early skeleton. See [`SPEC.md`](SPEC.md) for scope and [`PROGRESS.md`](PROGRESS.md) for status.

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Docker (for integration tests against a real pgvector database)

## Run

```bash
uv sync
uv run r2r --help        # `riches-to-rags` is the long-form alias
uv run r2r version
```

## Test and check

```bash
uv run pytest                      # tests
python3 .claude/hooks/tack verify  # format, lint, typecheck (pyright strict), tests
```

Tests marked `integration` need Docker; they start a throwaway pgvector container via testcontainers.
