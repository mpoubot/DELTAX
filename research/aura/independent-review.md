# Independent review of AURA — as requested in README_FOR_CLAUDE

Matin's brief asks for challenge, not agreement: distinguish fact / inference /
recommendation, attempt falsification, propose experiments with rejection
criteria, invent nothing. This is that response, kept deliberately short.

Labels: **[F]** = fact from the pack · **[I]** = my inference · **[R]** = recommendation.

---

## 1. Stocks — Equity Lab v0.4.8

**[F]** Signal Master: EMA3/EMA8 bullish crossover + MACD histogram > 0 +
relative volume ≥ 1, on the S&P 100, entry next-day OPEN, 12 bp round-trip
friction. Model A = 10-day close exit; Model B = ATR 2× stop / 4× target;
Model C = both. Pre-committed bar: OOS PF > 1.10 and >50% folds positive.

**Verdicts**

| Item | Verdict | Reason |
|---|---|---|
| Methodology (freeze → unseen → no retune) | **KEEP** | Best in the team corpus |
| Model B | **INVESTIGATE first** | 2R asymmetric target aligns with our S1/S0; defined risk per trade |
| Model A / C | INVESTIGATE after B | Time-exit-only (A) confounds signal quality with drift exposure |
| EMA3/8 signal family | **CHALLENGE** | [I] 3/8-day momentum on the most liquid, most-arbitraged large caps is the weakest place to hunt; the prior is that it's market beta in disguise — which the dossier itself suspects |
| Top-down stack (macro→futures→sector→ranking) | **DO NOT BUILD YET** | [I] Four layers multiply degrees of freedom faster than they add information; his own docs say the scripts don't exist. [R] Add at most one binary regime layer and demand OOS improvement |

**Three specific challenges**

1. **[I] Survivorship bias in the frozen universe.** "S&P 100 immutable once
   universe.csv exists" freezes *today's* membership — backtesting current
   members historically inflates results, because today's list is the winners.
   **[R]** Use point-in-time membership, or at minimum report the bias direction
   in every result.
2. **[I] RelVol ≥ 1 barely filters** — roughly half of days pass by
   construction. **[R]** Sweep 1.0 / 1.5 / 2.0 as a pre-registered comparison.
3. **[R] Beta-matched null:** for every signal entry, enter a random S&P 100
   name the same day with the same exit rules. If the signal doesn't beat the
   matched-random baseline on expectancy, the crossover is beta + noise.
   **Rejection:** signal-minus-null expectancy ≤ 0, or fails his own
   pre-committed bar.

## 2. Crypto — frozen candidate BEAR × LOW ATR × POSITIVE bar-2

**[F]** ATR threshold 0.596% (1H ATR14), trend 4H EMA50, positive 2H bar-2
return; MEXC USDT-M perps; 2% risk, 1–5× leverage, daily-loss 8%, DD halt 20%;
seven wider-universe assets removed after losing in three momentum tests; the
pack itself asks whether the candidate is "a genuine edge or a conditional
artifact" and notes the historical edge was thin before funding.

**Verdict: INVESTIGATE — the shape is exactly what data-mining produces.**
[I] A three-condition interaction with a continuous threshold quoted to three
decimals (0.596%) is the signature of a swept parameter, not a mechanism. That
doesn't make it false; it makes perturbation the decisive test.

**Falsification battery [R]**

| Test | Reject if |
|---|---|
| Perturb ATR threshold across 0.45–0.75% | Edge exists only in a narrow notch around 0.596% |
| Shuffle bar-2 sign (keep regime) | Real candidate doesn't beat shuffled |
| Random entries matched to regime frequency | Candidate ≤ random on expectancy |
| Funding-inclusive re-run with real funding history | Edge ≤ 0 after funding |
| Unseen assets (the excluded seven + new listings) | Sign flips on unseen set |

[I] The post-hoc removal of seven losing assets makes the retained universe
partially outcome-tuned — unseen-asset validation is mandatory, not optional.

**Hackathon scope [F/R]:** Alpaca lists no crypto options (verified: 0 contracts
on BTC/USD) and crypto alone cannot satisfy the mandatory options requirement;
MEXC is a non-Alpaca venue. **Crypto is post-hackathon, full stop.** Flag for
later: MEXC USDT-M perpetuals raise counterparty and, for a US person,
regulatory-access questions that belong to a compliance check, not a backtest.

## 3. Options — v0.6.0

**[F]** Not built, not validated; no chain dataset, no backtest, no adapter.
Ten selection criteria; a research protocol covering chain data quality,
survivorship, historical bid/ask realism, slippage, assignment, expiration,
corporate actions, event-aware holdouts, multiple-testing correction.

**His key question — which family first? [R]**

**Primary: defined-risk vertical credit spreads on high-liquidity index ETFs
(SPY/QQQ).** Best research-to-complexity ratio: two legs, max loss known at
entry, the densest and tightest chains in the market, and the structure our
gate module already sizes. **Alternatives:** (1) defined-risk debit verticals
when IV rank is low; (2) covered structures — but they add assignment lifecycle
and ~100× more capital per position, so later.

[I] His criteria map ~1:1 onto our shipped gates — see the merge table in
`../options/golden-rules.md`. The two real gaps he exposes in *our* engine:
no bid/ask-spread-quality gate (we gate OI only) and no IV-rank input. Both
queued.

[I] One tension worth keeping honest: his AVOID list warns against picking DTE
from "one historical sweet spot." Our 7–21 DTE band was chosen for the
competition window, not discovered in data — it must be documented as an
operational constraint, never cited as researched edge.

## 4. Blind spots across the whole pack [I]

1. **No expectancy arithmetic anywhere.** Profit factor and fold-positivity are
   good, but nothing ties win rate to payoff ratio. Our S0 gate is the
   complement AURA lacks — as AURA's pre-committed bar is the numeric floor our
   ladder lacked. Merge both.
2. **No position-sizing theory on the equity side.** Crypto has 2%/trade; the
   Equity Lab dossier never states risk per trade.
3. **Execution-quality gaps are honestly listed but unpriced** — reconciliation,
   idempotency, partial fills. The listed MEXC gaps are precisely where live
   money is lost; the barriers-FALSE discipline is the right response.
