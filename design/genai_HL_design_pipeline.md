# GenAI Research → LinkedIn Pipeline (MVP Design Doc)

## Objective
Build a lightweight pipeline that:
1. Ingests research papers (LangChain output)
2. Extracts structured insights
3. Forces a strong architectural position
4. Generates a LinkedIn post
5. Evaluates quality before publishing
6. Stores outputs in Obsidian
7. Sends final post via Email/Discord

---

## High-Level Architecture

Search → Summarise → Position Builder → Post Generator → Evaluation Gate → Store → Deliver

---

## Data Contracts

### 1. Paper Summary (JSON)
```json
{
  "title": "",
  "source": "",
  "summary": "",
  "key_claims": [],
  "tags": []
}
```

---

### 2. Position Object
```json
{
  "theme": "",
  "common_belief": "",
  "contrarian_view": "",
  "why_others_are_wrong": "",
  "recommendation": "",
  "enterprise_implication": ""
}
```

---

### 3. LinkedIn Post
```json
{
  "hook": "",
  "body": "",
  "implication": "",
  "full_post": ""
}
```

---

### 4. Evaluation Result
```json
{
  "scores": {
    "novelty": 0,
    "enterprise_relevance": 0,
    "non_obvious": 0,
    "position_strength": 0,
    "clarity": 0
  },
  "total": 0,
  "verdict": "publish | revise | reject",
  "reason_publish": "",
  "reason_reject": ""
}
```

---

## Core Components

### 1. Summariser
Input: raw paper text
Output: Paper Summary JSON

---

### 2. Position Builder (CRITICAL)
Prompt:
- Extract dominant belief
- Challenge it
- Form contrarian position
- Tie to enterprise architecture

---

### 3. Post Generator
Rules:
- Max 180 words
- One idea only
- Strong hook
- Clear position

---

### 4. Evaluation Engine
Score across:
- Signal (novelty, relevance, non-obvious)
- Thinking (position strength)
- Communication (clarity)

Threshold:
- Publish if score ≥ 30/45
- Reject if position < 3

---

### 5. Storage (Obsidian)

Folder structure:
```
/research/
  YYYY-MM-DD-topic.md
```

Template:
```
# {{title}}

## Summary
...

## Position
...

## Post
...

## Score
...
```

---

### 6. Delivery

Option A: Email (SMTP)
Option B: Discord (Webhook)

---

## Execution Flow (Pseudo)

1. Fetch papers
2. Generate summaries
3. Build position
4. Generate post
5. Evaluate
6. If pass → save + send
7. Else → revise or discard

---

## Non-Functional Requirements

- Deterministic prompts (no randomness)
- Logging at each stage
- Re-runnable pipeline
- Local-first (no heavy infra)

---

## Future Extensions

- Agent orchestration (LangGraph)
- Feedback loop (track engagement)
- Topic memory (avoid repetition)
- Diagram auto-generation

---

## Success Criteria

- 5 posts generated
- ≥60% pass evaluation
- Clear, opinionated content
- No generic summaries

