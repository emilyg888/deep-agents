# GenAI Research → LinkedIn Pipeline (MVP Design Doc v5 — Theme-Driven Thought Engine)

## Objective
Build a lightweight thought engine that:
- Uses papers as inputs (not drivers)
- Extracts high-value themes
- Avoids repetition (papers + ideas)
- Produces strong architectural positions
- Generates high-signal LinkedIn content

---

# 🧠 Core Design Shift

OLD:
Paper → Summary → Post

NEW:
Paper Pool → Theme-Driven Synthesis → Position → Post

Papers support ideas. They do NOT define them.

---

# ⚙️ Final Pipeline Architecture

Paper Sources (Tiered)
   ↓
Paper Pool
   ↓
Dedup + Paper Memory
   ↓
🔥 Theme-Driven Synthesis (with Debate Filter)
   ↓
Position Builder
   ↓
Position Strength Detector
   ↓
Post Generator
   ↓
Evaluation Gate
   ↓
Storage (Obsidian) + Delivery

---

# 🌐 Source Strategy

Tier 1 — Core Research:
- arXiv
- Semantic Scholar
- OpenAlex

Tier 2 — Enterprise Interpretation:
- MIT Sloan Management Review
- Harvard Business Review
- DeepLearning.AI

Tier 3 — Signal:
- Hacker News
- YouTube

---

# 🧩 Dedup + Paper Memory

hash = md5(title + authors)

Rules:
- Exact match → DROP
- High similarity → DEPRIORITISE

---

# 🧠 Theme Memory (Lightweight)

[
  {
    "theme": "linear vs loop architecture",
    "last_used": "2026-04-27"
  }
]

Rule:
IF theme used in last 6 months → REJECT

---

# 🔥 Theme-Driven Synthesis (CORE ENGINE)

## Responsibilities:
- Extract 3–5 candidate themes
- Compare against theme memory
- Apply debate filter (NEW)
- Select ONE strong theme
- Reject all others

---

## 🧠 NEW: Debate Filter (CRITICAL)

For each theme:

- If a typical architect would AGREE → REJECT
- If a strong architect would DEBATE → SELECT

👉 Only themes that create professional disagreement should pass.

---

## Prompt (Updated)

You are a senior enterprise AI architect.

Given these papers:

Step 1: Identify 3–5 themes

Step 2: Compare with theme memory:
{theme_memory}

Step 3: For each theme:
- Would a typical architect agree? → reject
- Would a strong architect debate? → keep

Step 4: Select ONE theme that is:
- new or underused
- enterprise-relevant
- debatable (creates tension)

Step 5: Reject all others

Output:
- Selected Theme
- Why selected
- Why others rejected
- Why this theme would trigger debate

---

# 🧠 Position Builder

- Common belief
- Contrarian view
- Why wrong
- Recommendation
- Enterprise implication

---

# 🚫 Position Strength Detector

Reject if:
- Contrarian < 3
- Tension < 3
- Specificity < 3

---

# ✍️ Post Generator

- Max 150–180 words
- One idea only
- Strong hook
- Clear position
- No summaries

---

# 🧪 Evaluation

Score:
- Novelty
- Relevance
- Insight
- Position strength
- Clarity

---

# 🗂 Storage

/research/YYYY-MM-DD-theme.md
/runs/run_YYYY-MM-DD.json

Reasoning memory should also retain:
- candidate themes
- rejected themes
- why they were rejected
- scoring rationale

---

# 📤 Delivery

- Email
- Discord

---

# 🚀 Success Criteria

- High rejection rate
- No repeated themes
- Strong, debatable positions only
- Content triggers professional discussion

---

# 🧠 Principle

You are not summarising research.

You are selecting ideas worth debating.
