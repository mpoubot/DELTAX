# DELTAX — Golden Rules: Crypto

**Source:** AURA (Matin) — the only crypto contribution in the corpus.
**Status: ⛔ POST-HACKATHON. Nothing here runs before 4 Sept.**

## Why crypto is out of competition scope

1. The hackathon requires every strategy to incorporate **options**. Alpaca has
   **no crypto options** (verified live: 0 contracts on BTC/USD). Spot crypto
   alone cannot qualify.
2. AURA's crypto path targets **MEXC USDT-M perpetuals** — a non-Alpaca venue,
   so it cannot count toward Alpaca-stack judging at all.
3. If crypto-adjacent exposure is ever wanted *inside* the rules, the compliant
   route is **options on spot-crypto ETFs (e.g. IBIT)** — verified to have
   listed contracts — flowing through the ordinary options engine and gates.

## What stands ready for after the deadline (from AURA)

- **Frozen candidate:** BEAR × LOW ATR × POSITIVE bar-2 (ATR 0.596% 1H ATR14,
  4H EMA50 trend, positive 2H bar-2). Status: candidate, not validated edge —
  the falsification battery in `../aura/independent-review.md` §2 runs first.
- **Baseline:** EMA20>50>200 + 20-candle breakout + volume + RSI 50–70,
  mirrored short.
- **Risk frame:** 2% per trade · ATR 1.0 stop · max 5 concurrent · partial TP
  at 3R (50%) · trailing 1.5 ATR · time stop 24 candles · daily loss limit 8% ·
  max-drawdown halt 20% · taker 0.05% + slippage 0.05% · funding modeled with
  real history.
- **Universe:** BTC, ETH, BNB, XRP, ADA, DOGE, AVAX, DOT, SUI, TIA, COTI;
  wider set (SOL, NEAR, LINK, INJ, APT, ARB, OP) excluded after losing in three
  momentum tests — ⚠️ partially outcome-tuned, so unseen-asset validation is
  mandatory.
- **Methodology:** the same AURA validation stack adopted corpus-wide
  (train/test, walk-forward 180/60/60, permutation controls, pre-committed
  OOS PF > 1.10 & >50% folds, no post-holdout tuning).
- **Open execution gaps (his list):** venue reconciliation, durable order
  identity/idempotency, uncertain-submit recovery, partial fills, order-state
  monitoring, native stop/TP lifecycle. None may be assumed solved.
- **Compliance check before any live MEXC work:** counterparty risk and US
  regulatory access to offshore perpetuals — a decision for the team, not a
  backtest.

## Session timing in crypto (note for post-hackathon)

The equity session clock (open auction → lunch lull → close volatility) is NYSE
microstructure and **does not transfer** — crypto trades 24/7 with no auction,
no lunch, no close. Crypto has its own clock, and Matin's MEXC engine should
encode *these* instead:

- **Liquidity still follows the sun.** Volume and depth concentrate in the
  EU/US overlap (~13:00–20:00 UTC); books are thinnest in early Asian hours.
- **Weekends are the danger zone.** Thin books, outsized slippage, and many of
  the violent gap-like moves. An always-on engine needs weekend-specific size
  limits or a stand-down — "24/7 market" does not mean "24/7 equal quality."
- **Perp funding timestamps** (typically every 8h — 00:00/08:00/16:00 UTC)
  create micro-patterns around the funding events. Directly relevant to the
  frozen candidate: his own dossier flags that funding may erase the thin edge,
  so entries relative to funding time belong in the falsification battery.
- **US macro releases move crypto in real time** (CPI, FOMC, jobs) — the macro
  calendar applies even though the equity session doesn't.

One inversion worth noting: if crypto exposure ever enters the *hackathon*
account, it's via **IBIT options** — which trade equity options hours, so the
equity session rules apply in full to that route.
