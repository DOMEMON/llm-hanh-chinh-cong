# Simplified RAG redesign

This directory defines the new target structure. Existing G1–G6 code remains on the
branch history and is not moved yet.

## Target responsibilities

- `backend/app/api`: HTTP/API boundary only.
- `backend/app/core`: configuration and cross-cutting infrastructure.
- `backend/app/domain`: procedures, sources, fragments, conversations, and domain rules.
- `backend/app/retrieval`: exact, lexical, dense, fusion, and ranking logic.
- `backend/app/generation`: LLM client, prompting, and grounded response handling.
- `backend/app/storage`: persistence adapters.
- `rag/corpus`: reviewed legal corpus inputs/releases.
- `rag/index`: generated retrieval artifacts; never hand-edited.
- `rag/evaluation`: retrieval and generation evaluation sets/reports.
- `models/generation`: local quantized generator artifacts (stored outside Git).
- `models/embedding`: local embedding artifacts (stored outside Git).
- `scripts`: small operational/build/evaluation scripts.
- `infra`: deployment notes/configuration.

The existing `web/` application remains where it is for now. Migration comes only
after we identify which existing files are worth reusing.
