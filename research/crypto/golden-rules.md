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

## News feed — registered, awaiting the crypto engine

`coindesk` is wired in `deltax/rss.py` under the `crypto` bucket with
`active=False`. Nothing to change but that flag when the crypto engine comes
online — the ingestion, parsing and metadata-only storage are already built and
tested.

Note what it does *not* solve: CoinDesk carries no ticker tagging and no
earnings or halt data, so it informs none of the gates the options agent runs
today. It becomes useful when there are crypto positions for it to be news
*about*.

## C-E26 — The whole venue was screened. Nothing has an edge.

> Adding coins was never going to fix the crypto sleeve. The problem is not
> which coin — it is that spot crypto without an options overlay has no
> measurable edge anywhere on this venue.

**Source.** Matin supplied Alpaca's full crypto asset list (73 pairs,
`data/alpaca_crypto_assets.csv`). That makes this an exhaustive test rather
than a sample: 33 tradeable USD pairs after removing stablecoins, 22 with
enough history for a 4-day hold.

| | |
|---|---|
| Pairs tested | 22 |
| Significant at 95% (t ≥ 1.96) | **0** |
| Surviving Bonferroni (t ≥ 3.81) | **0** |
| **Median win rate** | **43.8%** — below a coin flip |
| Pairs with negative mean return | 14 of 22 |

The best result, SKY at t = 1.92, has n = 45 and does not clear even the
uncorrected threshold, let alone the correction required for 22 simultaneous
tests. Ranking 22 pairs and taking the top one is exactly the selection the
Bonferroni correction exists to punish.

**The asset list also settles three earlier questions.** BNB, TRX and ZEC do
not appear anywhere in it, confirming from an authoritative source what the
per-pair queries found: BNB and Zcash are not listed, and TRON was delisted
(E25).

**The condor premise holds everywhere and cannot be used.** In-band rates run
**80–85% across every pair**, better than SPY's 75%. Crypto sits inside its own
volatility-scaled band more reliably than equities do. Alpaca lists **no crypto
options**, so there is no instrument to sell that band with. The edge is
visible and unreachable.

**Consequence.** The $10,000 sleeve is a spot allocation with no expected
return, and it should carry none in any forecast. It is defensible at 10% as
part of the project's scope; it is not defensible as a source of P&L, and it
must not be grown on the strength of a lucky week (E24 — one XRP week supplied
34% of a three-week profit and was not repeatable).

**What would change this.** A venue offering crypto options, at which point the
condor logic transfers directly and the 80–85% in-band rate becomes tradeable.
Until then, no amount of coin screening helps.
