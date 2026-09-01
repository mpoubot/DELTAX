# DELTAX research corpus

Candidate trading rules extracted from video sources, validated before any of it
trains the agent.

## Scope

The hackathon requires that all strategies **incorporate** options trading — not
that they consist solely of options (see `../HACKATHON-RULES.md`). Both buckets
contribute.

| Bucket | Status | Contributes | Synthesis |
|---|---|---|---|
| [Options](options/00-index.md) | ✅ 6 videos + AURA criteria | Instrument knowledge, structure selection, gates | [options/golden-rules.md](options/golden-rules.md) |
| [Stocks](stocks/00-index.md) | ✅ Alyrise (authoritative) + AURA Equity Lab + 4 videos | Engine spec, momentum research track, risk layer | [stocks/golden-rules.md](stocks/golden-rules.md) |
| [Crypto](crypto/golden-rules.md) | ⛔ post-hackathon (AURA) | MEXC candidate + risk frame, parked | [crypto/golden-rules.md](crypto/golden-rules.md) |
| [AURA platform](aura/00-platform.md) | ✅ methodology adopted corpus-wide | Validation stack, control plane, pre-committed bar · [independent review](aura/independent-review.md) | — |
| [Execution & Timing](execution/golden-rules.md) | ✅ E1–E9 | Liquidity windows, structure-aware gates, two-book nomination, pre-registered branches | [execution/golden-rules.md](execution/golden-rules.md) |

**Team sources:** videos A–I · **Elsa** (Alyrise stock engine) · **Matin / AURA**
(source M: platform, methodology, crypto candidate, options criteria).

**How they fit together.** The options bucket knows *what* to trade and had a
fatal gap: five sources selected on win rate and none measured the tail. The
process bucket supplies exactly what was missing — the expectancy gate, sizing
from defined risk, and the validation ladder — from three independent sources in
three different asset classes. Its instrument layer (pips, lots, CFD leverage,
crypto perpetuals) is excluded; its process layer is implemented in
`deltax/gates.py`.

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

**Target:** Alpaca paper account `PA397N6FXXIE`, options level 3.
Nothing is adopted. Everything is queued.
