# Deep Agents

This repo implements the `design/genai_pipeline_v5.md` thought engine as a
local-first pipeline for research-driven LinkedIn post generation.

## Implemented Pipeline

The current build follows the design doc structure:

1. Tiered paper sources
2. Paper pool assembly
3. Exact dedup plus high-similarity deprioritization
4. Theme memory check for the last 6 months
5. Theme-driven synthesis with debate filtering
6. Position builder
7. Position strength detector
8. Post generator
9. Evaluation gate
10. Research note storage
11. Per-run JSON logging plus reasoning memory
12. Local delivery artifacts for email and Discord

## Runtime Modes

The project now has two major runtime switches:

- source mode:
  - `static`
  - `hybrid`
  - `live`
- synthesis engine:
  - `deterministic`
  - `auto`
  - `openai`

Default behavior:

- `DEEP_AGENTS_SOURCE_MODE=hybrid`
- `DEEP_AGENTS_SYNTHESIS_ENGINE=auto`

This means the pipeline prefers live sources when possible, falls back to local
sample sources when live fetches fail, and uses OpenAI-backed synthesis only if
`OPENAI_API_KEY` is present.

## Source Strategy

The repo ships with local sample sources for the design tiers and also supports
live adapters behind the same `SourceCatalog` contract.

Static source coverage:

- Tier 1: `arXiv`, `Semantic Scholar`, `OpenAlex`
- Tier 2: `MIT Sloan Management Review`, `Harvard Business Review`, `DeepLearning.AI`
- Tier 3: `Hacker News`, `YouTube`

Live source coverage:

- `arXiv`: official API-backed adapter
- `Semantic Scholar`: official API-backed adapter
- `OpenAlex`: official API-backed adapter
- `Hacker News`: official API-backed adapter
- `MIT Sloan Management Review`: configurable RSS feed URL
- `Harvard Business Review`: configurable RSS feed URL
- `DeepLearning.AI`: configurable RSS feed URL
- `YouTube`: official API-backed adapter

This keeps the pipeline runnable offline while allowing progressive migration to
live inputs.

Google Scholar is no longer used as a live adapter because it does not expose a
public official search API suitable for this pipeline. The Tier 1 scholarly
search slot now uses OpenAlex instead.

## Project Layout

- `deep_agents/sources.py`: source interfaces and catalog
- `deep_agents/memory.py`: paper memory, theme memory, and reasoning memory
- `deep_agents/heuristics.py`: synthesis, debate filter, position builder, post generation
- `deep_agents/synthesis.py`: pluggable synthesis engines with OpenAI fallback handling
- `deep_agents/pipeline.py`: end-to-end orchestration
- `deep_agents/storage.py`: research note persistence and per-run JSON logs
- `deep_agents/delivery.py`: local email and Discord delivery artifacts
- `deep_agents/samples.py`: built-in sample source catalog
- `main.py`: runnable entrypoint

## Run

```bash
cd /Users/emilygao/LocalDocuments/Projects/langchain/deep-agents
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python main.py --ignore-memory
```

The default CLI run:

- uses the configured default source catalog
- uses the configured default synthesis engine
- writes research notes to your Obsidian vault
- writes delivery drafts locally
- can also send live delivery when enabled in `.env`

To send live delivery instead of draft files only:

```bash
cd /Users/emilygao/LocalDocuments/Projects/langchain/deep-agents
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python main.py --ignore-memory --live-discord
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python main.py --ignore-memory --live-email
```

Or enable live delivery by default in `.env`:

```env
DEEP_AGENTS_LIVE_EMAIL=true
DEEP_AGENTS_LIVE_DISCORD=true
```

When these are set, the default CLI run will send live delivery without
requiring `--live-email` or `--live-discord`.

Outputs are written to:

- `memory/paper_memory.json`
- `memory/theme_memory.json`
- `memory/reasoning_memory.json`
- `runs/run_YYYY-MM-DD.json`
- `/Users/emilygao/LocalDocuments/Obsidian/research/YYYY-MM-DD-theme.md`
- `delivery/email/YYYY-MM-DD-linkedin-draft.md`
- `delivery/discord/YYYY-MM-DD-linkedin-draft.md`

Use the default mode without `--ignore-memory` when you want paper and theme
memory to affect selection across runs. Theme reuse is blocked across a rolling
6-month window, and the reasoning memory stores candidate themes, rejected
themes, rejection reasons, and scorecards for each remembered run.

Live email requires SMTP credentials in the environment. Supported variables:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`

Gmail is also supported via:

- `GMAIL_SENDER_EMAIL`
- `GMAIL_APP_PASSWORD`

Live Discord uses the Weekflow webhook in
`/Users/emilygao/LocalDocuments/Projects/Weekflow/config.py`.

## Live Sources

The runtime source mode is controlled by:

- `DEEP_AGENTS_SOURCE_MODE=static`
- `DEEP_AGENTS_SOURCE_MODE=hybrid`
- `DEEP_AGENTS_SOURCE_MODE=live`

Default: `hybrid`

Current live adapters:

- `arXiv`: live API
- `Semantic Scholar`: live API
- `OpenAlex`: live API
- `Hacker News`: live official API
- `MIT Sloan Management Review`: RSS URL via `DEEP_AGENTS_MIT_SLOAN_RSS_URL`
- `Harvard Business Review`: RSS URL via `DEEP_AGENTS_HBR_RSS_URL`
- `DeepLearning.AI`: RSS URL via `DEEP_AGENTS_DEEPLEARNINGAI_RSS_URL`
- `YouTube`: live official API via `YOUTUBE_API_KEY`

`hybrid` mode tries live first and falls back to the static sample sources when
live fetches fail or are not configured.

Optional live-source environment variables:

- `DEEP_AGENTS_ARXIV_QUERY`
- `DEEP_AGENTS_ARXIV_LIMIT`
- `DEEP_AGENTS_SEMANTIC_SCHOLAR_QUERY`
- `DEEP_AGENTS_SEMANTIC_SCHOLAR_LIMIT`
- `SEMANTIC_SCHOLAR_API_KEY`
- `OPENALEX_API_KEY`
- `DEEP_AGENTS_OPENALEX_QUERY`
- `DEEP_AGENTS_OPENALEX_LIMIT`
- `DEEP_AGENTS_OPENALEX_FROM_PUBLICATION_DATE`
- `DEEP_AGENTS_MIT_SLOAN_RSS_URL`
- `DEEP_AGENTS_HBR_RSS_URL`
- `DEEP_AGENTS_DEEPLEARNINGAI_RSS_URL`
- `YOUTUBE_API_KEY`
- `DEEP_AGENTS_YOUTUBE_QUERY`
- `DEEP_AGENTS_YOUTUBE_PUBLISHED_AFTER`
- `DEEP_AGENTS_HN_LIMIT`

## Pluggable Synthesis

The synthesis engine is controlled by:

- `DEEP_AGENTS_SYNTHESIS_ENGINE=deterministic`
- `DEEP_AGENTS_SYNTHESIS_ENGINE=auto`
- `DEEP_AGENTS_SYNTHESIS_ENGINE=openai`

Default: `auto`

Behavior:

- `deterministic`: always uses the local heuristic engine
- `auto`: uses OpenAI only when `OPENAI_API_KEY` is present, otherwise deterministic
- `openai`: attempts the OpenAI engine and falls back to deterministic on failure

Optional model override:

- `DEEP_AGENTS_OPENAI_MODEL`

The OpenAI engine works as a bounded synthesis layer:

- it starts from the deterministic candidate-theme set
- it chooses a theme from that known set
- it rewrites the theme rationale, position, and 3-paragraph post
- it falls back to deterministic synthesis if the model call fails or returns
  invalid output

This keeps memory, deduplication, storage, and delivery deterministic even when
LLM reasoning is enabled.

## Environment Summary

Core:

- `OPENAI_API_KEY`
- `DEEP_AGENTS_SOURCE_MODE`
- `DEEP_AGENTS_SYNTHESIS_ENGINE`
- `DEEP_AGENTS_OPENAI_MODEL`

Email:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `GMAIL_SENDER_EMAIL`
- `GMAIL_APP_PASSWORD`

Discord:

- Weekflow webhook is read from:
  `/Users/emilygao/LocalDocuments/Projects/Weekflow/config.py`

## Launchd At Login

This repo includes a LaunchAgent that runs the live pipeline once at login.

Files:

- `launchd/com.emilyg888.deep-agents.login.plist`
- `scripts/run_login_job.sh`
- `scripts/install_launch_agent.sh`

Install:

```bash
cd /Users/emilygao/LocalDocuments/Projects/langchain/deep-agents
./scripts/install_launch_agent.sh
```

The login job runs:

```bash
.venv/bin/python main.py --live-email --live-discord
```

Logs are written to:

- `logs/launchd.stdout.log`
- `logs/launchd.stderr.log`

## Test

```bash
cd /Users/emilygao/LocalDocuments/Projects/langchain/deep-agents
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests
```

The tests cover:

- exact deduplication
- hybrid source fallback
- high-similarity deprioritization
- recent theme memory
- synthesis-engine fallback
- tiered source coverage
- end-to-end pipeline output
