---
description: Systematic, grounded web research that triangulates real sources and never fabricates facts.
---

# Deep Research

Use this when a question needs current, factual, or external information you are
not certain about. The goal is a well-grounded answer backed by real sources —
never a confident guess.

## Method

1. **Decompose the question.** Break it into the specific sub-claims you must
   verify. Note what "done" looks like and what would make the answer wrong.
2. **Search broadly.** Use `search_web` with focused queries. Try several phrasings
   if the first returns weak results. Read titles and snippets to pick the most
   authoritative, primary, and recent sources.
3. **Read the actual pages.** Use `fetch_url` on the most relevant results before
   stating any specific fact — snippets are not enough. Use `read_pdf` for PDFs.
   Prefer primary sources (official docs, standards, papers, vendor pages) over
   aggregators and SEO content.
4. **Triangulate.** Confirm each non-trivial claim against at least two
   independent sources. If sources disagree, say so and explain which you trust
   and why.
5. **Track provenance.** Keep the URL for every fact you will report. If you
   could not verify something, do not assert it.

## Reporting

- Lead with a direct answer, then the supporting detail.
- Cite the URL inline for each specific claim, e.g. `(source: https://…)`.
- Separate **verified** facts from **uncertain / unverified** ones explicitly.
- State the date-sensitivity of the answer when it may change over time.
- End with remaining gaps or questions if the answer is incomplete.

## Rules

- Never invent URLs, quotes, statistics, or citations.
- If search and fetch cannot establish a fact, say "I couldn't verify this" and
  explain what you tried — do not fall back to a guess.
- When the user asks about durable facts about themselves or their project, also
  `recall` what you already know before researching.
