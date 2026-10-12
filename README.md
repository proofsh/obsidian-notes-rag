[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/pypi/v/obsidian-notes-rag)](https://pypi.org/project/obsidian-notes-rag/)

# obsidian-notes-rag

MCP server and CLI for semantic search over your Obsidian vault — or any folder of linked markdown: an OKF knowledge bundle, a repo's docs tree, a wiki export. The CLI installs as `obsidian-rag` and as **`okf-search`** — same tool, use whichever name fits the corpus. Generates embeddings with OpenAI, Ollama, LM Studio, or llama.cpp. Stores vectors locally in sqlite-vec (~200KB, no telemetry, no network calls). Nothing requires Obsidian itself: point `--root` at any markdown directory and both the semantic index and the link graph work the same.

## What it does

Search your notes by meaning, not just keywords:

```bash
obsidian-rag search "project architecture decisions" -n 5
obsidian-rag similar "Projects/Platform Hub.md"
obsidian-rag context "Daily Notes/2026-02-14.md"
```

As an MCP server, it gives any compatible AI assistant the same capabilities — searching your notes, finding related content, and pulling context during conversations.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (for running and installing)
- One of: `OPENAI_API_KEY`, [Ollama](https://ollama.ai/), [LM Studio](https://lmstudio.ai/), or [llama.cpp](https://github.com/ggml-org/llama.cpp) (`llama-server`) for embeddings

## Setup

### 1. Run the setup wizard

```bash
uvx obsidian-notes-rag setup
```

This creates a config at `~/.config/obsidian-notes-rag/config.toml` with your vault path, embedding provider, and API key.

### 2. Build the index

```bash
uvx obsidian-notes-rag index
```

Parses your markdown files, chunks them by heading structure (using [Chonkie](https://github.com/chonkie-ai/chonkie) RecursiveChunker), generates embeddings, and stores everything in a local SQLite database.

### 3. Connect to an MCP client

Works with any MCP-compatible client. Examples:

**Claude Code:**

```bash
claude mcp add -s user obsidian-notes-rag -- uvx obsidian-notes-rag serve
```

**Claude Desktop, Cursor, Windsurf, etc. (JSON config):**

Add to your client's MCP config file (e.g. `~/Library/Application Support/Claude/claude_desktop_config.json` for Claude Desktop on macOS):

```json
{
  "mcpServers": {
    "obsidian-notes-rag": {
      "command": "uvx",
      "args": ["obsidian-notes-rag", "serve"]
    }
  }
}
```

### 4. Install the CLI (optional)

If you want `obsidian-rag` available as a standalone command:

```bash
uv tool install obsidian-notes-rag
```

This installs both `obsidian-rag` and `obsidian-notes-rag` to `~/.local/bin/`.

### Using the CLI with AI coding assistants

Instead of running the MCP server, you can have your AI assistant call the CLI directly via shell commands. This avoids loading MCP tool definitions into the context window, freeing up tokens for your actual work.

To do this, create a rule or skill that tells your assistant when and how to use the CLI:

- **Claude Code**: Create a [skill](https://docs.anthropic.com/en/docs/claude-code/skills) with CLI usage instructions
- **Cursor**: Add a [rule](https://docs.cursor.com/context/rules) to `.cursor/rules/`
- **Windsurf**: Add a [rule](https://docs.windsurf.com/windsurf/memories#rules) to `.windsurfrules`

The rule should describe when to use each command (`search`, `similar`, `context`) and any project-specific conventions. This gives the assistant enough context to run the right CLI commands without the overhead of an MCP connection.

## CLI Reference

```bash
# Search
obsidian-rag search "query"                  # semantic search
obsidian-rag search "standup" --type daily   # filter by note type
obsidian-rag search "design" -n 10           # more results
obsidian-rag search "design" --expand 1      # + notes linked from the hits
obsidian-rag search "design" -e 2 --expand-limit 15  # deeper graph context

# Explore
obsidian-rag similar "Path/To/Note.md"       # find related notes (by meaning)
obsidian-rag context "Path/To/Note.md"       # note + links/backlinks + similar
obsidian-rag graph "Path/To/Note.md"         # link-graph neighborhood
obsidian-rag graph "Path/To/Note.md" -n 2    # traverse two hops

# Index
obsidian-rag index                            # re-index vault
obsidian-rag index --clear                    # rebuild from scratch
obsidian-rag index --path-filter "Daily Notes/"  # index subset

# Info
obsidian-rag stats                            # show index size

# Second collections (e.g. a project's docs bundle) — pass both flags on every command
obsidian-rag --vault ~/proj/internal --data ~/rag-data/proj index
obsidian-rag --vault ~/proj/internal --data ~/rag-data/proj search "query" -e 1

# Services
obsidian-rag serve                            # start MCP server
obsidian-rag watch                            # watch for changes, auto-reindex
obsidian-rag install-service                  # macOS launchd auto-start
obsidian-rag uninstall-service                # remove service
obsidian-rag service-status                   # check service status
```

## MCP Tools

Once connected, your AI assistant has access to:

| Tool | What it does |
|------|--------------|
| `search_notes` | Find notes matching a query; `expand` adds link-graph neighbors |
| `get_similar` | Find notes similar to a given note |
| `get_note_context` | Get a note with its links, backlinks, and similar notes |
| `get_note_graph` | Get a note's link-graph neighborhood |
| `get_stats` | Show index statistics |
| `reindex` | Rebuild the index (chunks and link graph) |

## Graph-Aware Retrieval

Your vault's links already form a knowledge graph. Indexing extracts every
wikilink and markdown link between notes into a local edge table (no LLM
involved), and `--expand` / `get_note_graph` traverse it at query time:
a vector search finds the notes that *sound like* your query, then expansion
follows real links outward for the connected context — the entity-anchored
retrieval that graph-RAG systems promise, at zero extra indexing cost.
Traversal is breadth-first (both links and backlinks), never revisits a
note, and reports which note bridged each hop.

## Keeping the Index Fresh

**Manual:** `obsidian-rag index`

**Auto-reindex on file changes:** `obsidian-rag watch` (run in a terminal or background)

**macOS background service:** `obsidian-rag install-service` (starts on login, appears in System Settings > Login Items)

## Using Ollama (local, no API key)

```bash
ollama pull nomic-embed-text
obsidian-rag --provider ollama index
```

## Using LM Studio (local, no API key)

Load an embedding model in LM Studio, then:

```bash
obsidian-rag --provider lmstudio index
```

## Using llama.cpp (local, no API key)

Start `llama serve` with embedding support (`--embedding` + `--pooling` are required), then:

```bash
llama serve -hf nomic-ai/nomic-embed-text-v1.5-GGUF:Q8_0 --embedding --pooling mean --port 9931 -c 2048 -ub 2048
obsidian-rag --provider llamacpp index
```

The `-ub 2048` flag is important: since chunks can be up to 1,500 tokens long,
the default physical batch size (512) would cause long chunks to be
rejected with an `input is too large to process` error.

> Default URL is `http://localhost:9931` (llama.cpp b11521+; older
> servers defaulted to `8080`). Override with `--llamacpp-url` or
> `OBSIDIAN_RAG_LLAMACPP_URL`.

### Router mode (multiple models, on-demand loading)

Launched **without** `-m`/`-hf`, `llama serve` becomes a router: each
request's `model` field selects which model handles it, loading it
automatically on first use.

```bash
# Router with embedding support (discovers the llama.cpp cache / --models-dir)
llama serve --embedding --pooling mean --port 9931 -c 2048 -ub 2048

# Route by model name — no per-model port needed.
# The model loads on demand at first use (preloaded explicitly via
# POST /models/load when possible; falls back to auto-load otherwise).
obsidian-rag --provider llamacpp --model "nomic-ai/nomic-embed-text-v1.5-GGUF:Q8_0" index
```

List routable names with `curl http://localhost:9931/v1/models`.
With `--no-models-autoload` the server requires an explicit
`POST /models/load {"model": "<name>"}` — the embedder attempts this
automatically before indexing/searching.

### Router mode with `--models-preset` (per-model settings)

Each `[section-name]` in the INI file becomes the model name used in
API calls (`"model"` field). Example preset file (`models.ini`):

```ini
[nomic-embed-text-v2-moe]
model = C:\ISO\models\nomic-ai--nomic-embed-text-v2-moe-GGUF\nomic-embed-text-v2-moe.Q4_K_M.gguf
embedding = true
pooling = mean
ctx-size = 2048
ubatch-size = 512
```

```bash
llama serve --models-preset models.ini --port 9931

# The section name is the model name — it loads on demand at first use.
obsidian-rag --provider llamacpp --model "nomic-embed-text-v2-moe" index
```

Notes:
- The preset key is `embedding` (boolean: `true`/`on`/`1`/`enabled`).
  `embeddings` is accepted as an alias by the CLI, but `enable`
  (without the trailing `d`) is not a recognized boolean — prefer `true`.
- `ubatch-size` must cover your chunk size: with the default chunk size
  (up to 1,500 tokens) use `-ub 2048` / `ubatch-size = 2048`, otherwise
  long chunks are rejected with `input is too large to process`.
  Conversely, with `ubatch-size = 512` every chunk must fit in 512 tokens,
  so pair it with `chunk_size = 400` below.
- `nomic-embed-text-v2-moe` combo (effective context 512): the model caps
  slots at 512, so `ctx-size = 2048` reserves memory with no benefit —
  `ctx-size = 512` is enough. Consistent setup:
  `ctx-size = 512`, `ubatch-size = 512`, and `chunk_size = 400` in
  `config.toml`, then `obsidian-rag index --clear`.
- Tip: keep the section name containing the model family (e.g. `nomic`,
  `qwen`) — task prefixes (`search_document: `, `Query: `) are derived
  from the configured model name.

> Note the model's context length: the training context for
> `nomic-embed-text-v2-moe` is 512 tokens, so the server caps slots
> at 512; chunks exceeding 512 tokens cannot be accommodated
> via server flags (`input is larger than the max context size`).
> In that case, either use `nomic-embed-text-v1.5` (2,048 tokens)
> or reduce the chunk size in the configuration file:
>
> ```toml
> [indexer]
> chunk_size = 400
> ```
>
> After changing the chunking settings, please rebuild the index
> using `obsidian-rag index --clear`.

If the server was started with `--api-key`, pass it via `--llamacpp-api-key`
or `OBSIDIAN_RAG_LLAMACPP_API_KEY`. When a single model is loaded,
llama-server accepts any model name, so the default `default` works;
in router mode set the model with `--model` or `OBSIDIAN_RAG_MODEL`
to the routable model name.

## Configuration

The setup wizard writes to `~/.config/obsidian-notes-rag/config.toml`. You can also override with environment variables:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `OBSIDIAN_RAG_PROVIDER` | `openai` (default), `ollama`, `lmstudio`, or `llamacpp` |
| `OBSIDIAN_RAG_VAULT` | Path to Obsidian vault |
| `OBSIDIAN_RAG_DATA` | Index storage path (default: platform-specific) |
| `OBSIDIAN_RAG_OLLAMA_URL` | Ollama URL (default: `http://localhost:11434`) |
| `OBSIDIAN_RAG_LMSTUDIO_URL` | LM Studio URL (default: `http://localhost:1234`) |
| `OBSIDIAN_RAG_LLAMACPP_URL` | llama.cpp URL (default: `http://localhost:9931`) |
| `OBSIDIAN_RAG_LLAMACPP_API_KEY` | llama.cpp API key (when started with `--api-key`) |
| `OBSIDIAN_RAG_MODEL` | Override embedding model |

## How it works

1. Parses markdown files, strips YAML frontmatter
2. Chunks content using Chonkie's RecursiveChunker (splits by headings > paragraphs > lines > sentences, max 1500 tokens per chunk)
3. Generates embeddings via your chosen provider
4. Stores metadata in SQLite, vectors in sqlite-vec (KNN search via vec0 virtual tables)
5. MCP server and CLI both query the same local database

## Upgrading

If you installed the CLI with `uv tool install`, upgrade with:

```bash
uv tool upgrade obsidian-notes-rag
```

If you use `uvx` to run commands or the MCP server, it automatically uses the latest version.

### Upgrading to v1.0.0

v1.0.0 replaces ChromaDB with sqlite-vec. After upgrading, rebuild your index:

```bash
obsidian-rag index --clear
```

The old ChromaDB data at `~/.local/share/obsidian-notes-rag/` (or your configured path) can be deleted.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

## Support

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/ernestkoe)

## License

MIT
