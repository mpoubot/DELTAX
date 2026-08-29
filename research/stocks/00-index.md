# Stocks bucket

## Authoritative strategy

**[`golden-rules.md`](golden-rules.md) — Alyrise, by Ilze Rosicka (Elsa).**
The stock engine spec. Stocks only; it explicitly must not be merged with crypto
or options rules.

## Reference only

[`video-derived-rules.md`](video-derived-rules.md) — superseded for stocks. Its
risk/process layer (S0–S6) informed `deltax/gates.py`, which serves the **options**
engine. Notes on the four source videos below.

| # | Video | Source | Length | Trades | Quality |
|---|---|---|---|---|---|
| 07 | [Trading for Beginners Part 1](video-notes/07-jason-graystone-trading-course.md) | Jason Graystone | 2:26 | ⚠️ Forex/CFD | **High** — supplies the expectancy formula |
| 08 | [How To Start Day Trading in 2025](video-notes/08-craig-percoco-day-trading-2025.md) | Craig Percoco | 0:27 | ⚠️ Crypto | **Medium** — strong psychology; core signal paywalled |
| 09 | [The ONLY Technical Analysis Guide](video-notes/09-ross-cameron-technical-analysis.md) | Ross Cameron | 1:41 | ✅ **US equities** | **High** — the five-criteria screen |
| 10 | [The Only Trading Strategy](video-notes/10-tradinglab-only-strategy.md) | TradingLab | 0:08 | ⚠️ Forex | **Low** — 🚩 offshore broker ad, winners-only evidence |

## What this bucket contributes

Three of four sources don't trade equities. The **process layer converges across
all four** and is credible precisely because it holds across asset classes — it's
now implemented in `deltax/gates.py`. The **underlying-selection method** (video
09) is the only screenable rule set in the corpus.

Its instrument layer — pips, lots, CFD leverage, crypto perpetuals — does not
apply to a US options account and is excluded.

## Still missing

A systematic/quant viewpoint, and a disinterested source. The WSJ piece was the
most valuable item in the options bucket because it had nothing to sell; nothing
here plays that role.
