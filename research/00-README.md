# DELTAX research corpus

Candidate trading rules extracted from video sources, validated before any of it
trains the agent.

## Scope

**Options only.** The hackathon requires that all strategies incorporate options
trading (see `../HACKATHON-RULES.md`), so the corpus is scoped to match.

| Bucket | Status | Synthesis |
|---|---|---|
| [Options](options/00-index.md) | ✅ 6 videos, 5 viewpoints — complete | [options/golden-rules.md](options/golden-rules.md) |

*A stocks bucket (4 videos) was built and then removed on 2026-08-29 — the
instrument didn't qualify under the hackathon rules. Its one durable contribution,
the expectancy gate, was folded into the options rules before removal.*

## Method

1. Pull auto-captions with `yt-dlp`, read in full.
2. Write concept notes in our own words — no verbatim transcripts stored.
3. Every prescriptive claim is a **candidate rule**, never an adopted one.
4. Promote on independent multi-source agreement; weight by viewpoint, not by
   video count or view count.
5. **Gate on expectancy** — `E = (1 + W/L) × P − 1`, trade only if E > 0.
   Never on win rate.
6. Backtest, then adopt.

## Standing lessons

- **Rank sources by viewpoint, not views.** Two of the six videos were the same
  channel; counting them separately would have manufactured false consensus.
- **Include at least one disinterested source.** The WSJ 0DTE piece was the most
  informative item in the corpus because it had nothing to sell.
- **Age-discount hard.** The corpus spans 2015–2025.
- **High win rate is not an edge.** Every commercial source optimized for it and
  none measured the tail. This is exactly how the TSLA playbook failed.

**Target:** Alpaca paper account `PA3ID1B9L6BP`, options level 3.
Nothing is adopted. Everything is queued.
