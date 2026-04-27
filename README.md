# Deep Agents

This repo implements the `design/genai_pipeline_v5.md` thought engine as a
local-first pipeline for research-driven LinkedIn post generation.

## Implemented Pipeline

The current build follows the design doc structure:

1. Tiered paper sources
2. Paper pool assembly
3. Exact dedup plus high-similarity deprioritization
4. Theme memory check for the last 3 posts
5. Theme-driven synthesis with debate filtering
6. Position builder
7. Position strength detector
8. Post generator
9. Evaluation gate
10. Research note storage
11. Local delivery artifacts for email and Discord

## Source Strategy

The repo ships with local sample sources for the design tiers:

- Tier 1: `arXiv`, `Semantic Scholar`, `Google Scholar`
- Tier 2: `MIT Sloan Management Review`, `Harvard Business Review`, `DeepLearning.AI`
- Tier 3: `Hacker News`, `YouTube`

These are implemented as static local sources so the pipeline works without
network access or paid APIs.

## Project Layout

- `deep_agents/sources.py`: source interfaces and catalog
- `deep_agents/memory.py`: paper memory and theme memory
- `deep_agents/heuristics.py`: synthesis, debate filter, position builder, post generation
- `deep_agents/pipeline.py`: end-to-end orchestration
- `deep_agents/storage.py`: research note persistence under `research/`
- `deep_agents/delivery.py`: local email and Discord delivery artifacts
- `deep_agents/samples.py`: built-in sample source catalog
- `main.py`: runnable entrypoint

## Run

```bash
cd /Users/emilygao/LocalDocuments/Projects/langchain/deep-agents
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python main.py --ignore-memory
```

To send live delivery instead of draft files only:

```bash
cd /Users/emilygao/LocalDocuments/Projects/langchain/deep-agents
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python main.py --ignore-memory --live-discord
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python main.py --ignore-memory --live-email
```

Outputs are written to:

- `memory/paper_memory.json`
- `memory/theme_memory.json`
- `research/YYYY-MM-DD-theme.md`
- `delivery/email/YYYY-MM-DD-linkedin-draft.md`
- `delivery/discord/YYYY-MM-DD-linkedin-draft.md`

Use the default mode without `--ignore-memory` when you want paper and theme
memory to affect selection across runs.

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

## Test

```bash
cd /Users/emilygao/LocalDocuments/Projects/langchain/deep-agents
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests
```

The tests cover:

- exact deduplication
- high-similarity deprioritization
- recent theme memory
- tiered source coverage
- end-to-end pipeline output
