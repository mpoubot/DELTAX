# Options education corpus — video notes

Goal: extract candidate "golden rules" from top options-education videos, then
validate each before any of it trains the DELTAX agent.

**Synthesis lives in [`../golden-rules.md`](../golden-rules.md).**

## Options module — complete (6 videos, 5 viewpoints)

| # | Video | Source | Length | Viewpoint |
|---|---|---|---|---|
| 01 | [Options Trading For Beginners (4 Hour Course)](01-skyview-options-4hr-course.md) | Sky View Trading | 3:56 | **A** — sell defined-risk premium |
| 02 | [Options Trading for Beginners: Super Simple](02-chartfanatics-usman-ashraf-2hr.md) | Chart Fanatics / Usman Ashraf | 1:59 | **B** — buy premium, directional, 0DTE |
| 03 | [Understanding Option Prices](03-skyview-understanding-option-prices.md) | Sky View Trading | 0:07 | **A** ⚠️ duplicate of 01 |
| 04 | [Complete Guide with Examples](04-clearvalue-complete-guide.md) | ClearValue Tax | 0:50 | **C** — covered calls + CSPs |
| 05 | [Options Trading For Beginners \| Step By Step](05-andrei-jikh-step-by-step.md) | Andrei Jikh / Alex Pandrea | 0:22 | **D** — retail: CC, CSP, LEAPS |
| 06 | [0DTE: Inside the Explosion of Ultra-Risky Options Trading](06-wsj-0dte-explosion.md) | The Wall Street Journal | 0:05 | **E** — journalism, no conflict |

## Next: stocks module

Slots 07+ to cover general stock trading, then possibly crypto.

**Carry these lessons into source selection:**
- **Rank by viewpoint, not views.** Video 03 was a duplicate of 01 from the same
  channel — high view counts cluster in a few large channels and manufacture
  false consensus.
- **Include at least one disinterested source per module.** Video 06 (WSJ) was
  the single most informative item in the options corpus precisely because it had
  nothing to sell.
- **Age-discount hard.** Video 03 is from 2015; Video 05 is from the 2021 retail
  peak and promotes a lender that went bankrupt in 2022. Crypto content from that
  era will need the heaviest discount of all.

## Method

1. Pull auto-captions with `yt-dlp`, read in full.
2. Write concept notes in our own words — no verbatim transcripts stored.
3. Tag every prescriptive claim as a **candidate rule**, never an adopted one.
4. Promote to the rules repository only on independent multi-source agreement.
5. Only backtested, positive-expectancy rules enter the agent.

## Standing caution

High probability of profit ≠ positive expectancy. Video 01's own live demo won 4
of 5 trades and lost money on the basket; Video 06's profiled trader had a worst
day ~8.7× his best day. Every candidate rule is judged on expectancy, never on
hit rate.
