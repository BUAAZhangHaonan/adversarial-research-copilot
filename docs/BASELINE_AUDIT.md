# Baseline audit — 2026-09-07

The g203 main checkout is clean at `3bc93dd0be54d3c2ffc4c2b4f9f2014c79064c85`.
No ARC or ancestor AGENTS.md was found. Its `.venv` uses Python 3.13.5;
uv is `/home/g203/.local/bin/uv`. Existing tests comprise 16 files and 87 test definitions.
The unchanged baseline suite completed with **87 passed in 76.89 seconds**.
The earlier dirty-tree review is historical and is not treated as the current baseline.

Preserve Typer, Pydantic, Jinja and pytest. Replace custom model/MCP protocols, YAML/keyword
judgments, multiple reviewer loops and independent JSON state files with the contract's shared
SDK adapter, SQLite state, typed envelope and issue loop. Preserve references and historical
research artifacts. Existing `.env` is read privately; no credentials enter version control.

The three MCP connections are configured by `ARC_MCP_WEBRESEARCH_CMD`,
`ARC_SCHOLARTRACE_URL/TOKEN`, and `ARC_SCHOLARANALYSIS_URL/TOKEN`.
Service capabilities and fee visibility are audited separately before any paid tool request.
