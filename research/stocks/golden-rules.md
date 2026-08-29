# DELTAX — Golden Rules: Process bucket (originally "stocks")

**Corpus status:** 4 videos · **4 independent viewpoints** · restored 2026-08-29
Rules promoted by independent multi-source agreement. Nothing adopted until it
clears a backtest.

---

## Why this bucket exists, given that options are mandatory

The hackathon requires that **all strategies incorporate options trading** — but
"incorporate," not "consist solely of." This bucket was briefly deleted on the
mistaken reading that it couldn't contribute. It contributes two things, both of
which apply to options directly:

1. **The risk and process layer**, which is instrument-agnostic. Expectancy,
   sizing from defined risk, payoff-ratio floors, the validation ladder, and
   kill-switch thresholds work identically on a vertical spread and a share of
   stock. **This layer is already implemented in `deltax/gates.py`.**
2. **Underlying selection** (S7). Before you write an option you must choose an
   underlying, and video 09 is the only source in the entire corpus that gives
   numeric, screenable criteria for that choice.

The bucket's *instrument* content — pips, lots, CFD leverage, crypto perpetuals —
remains inapplicable and is excluded.

---

## Source ledger

| ID | Source | Video | Actually trades | Conflict of interest |
|---|---|---|---|---|
| **F** | Jason Graystone | 07 | ⚠️ Forex / CFD | CFD broker affiliate |
| **G** | Craig Percoco | 08 | ⚠️ Crypto perpetuals | Paid indicators, private team |
| **H** | Ross Cameron / Warrior Trading | 09 | ✅ **US equities** | Paid programme; **see note** |
| **I** | TradingLab | 10 | ⚠️ Forex | 🚩 Offshore broker sponsorship |

Only one of four trades US equities. The process content converges strongly
across all four — and is credible *because* it holds across asset classes.

⚠️ **Source H:** Warrior Trading/Ross Cameron reached an FTC settlement in 2022 over
allegations about earnings representations (~$3M reported). From memory —
**verify at ftc.gov.** Treat displayed profit figures as marketing regardless.
🚩 **Source I:** contains an offshore copy-trading claim of ~$50k → ~$160k in one
month. Disregard.

---

## S0 — Expectancy gate ★★★ three-source · **IMPLEMENTED**

> **E = ( 1 + W / L ) × P − 1** · trade only if **E > 0**

**Sources: F, G, H** — three independent derivations:
- **F** states the formula and verifies it with worked numbers.
- **G** reaches it via R-multiples: 7 losses at −1R and 3 wins totalling +10.8R →
  **net +3.8R while wrong 70% of the time.**
- **H** frames it as breakeven win rate by payoff ratio: 2:1 needs only 33%.

All three presentations check out and are algebraically equivalent to
`P × (W/L) − (1 − P)` — expectancy in R-multiples.

**This closes the options bucket's fatal gap.** Five options sources selected on
probability of profit; none measured the tail. Also mirrored in
`../options/golden-rules.md` as the promotion gate for every rule in every bucket.

→ `gate_expectancy()` in `deltax/gates.py`. Tested against Sky View's
four-winners-still-negative basket, which it correctly rejects.

## S1 — Minimum reward-to-risk floor ★★★ four-source · **IMPLEMENTED**

> Target must be at least **2× the risk**, defined before entry.

**F (2:1) · G (3R targets) · H (2:1 hard minimum) · I (2.5:1).** Threshold varies;
principle unanimous. Follows from S0 — a higher payoff ratio lowers the accuracy
required. → `gate_reward_risk()`

## S2 — Size from defined risk ★★★ three-source · **IMPLEMENTED**

> `quantity = (risk fraction × equity) ÷ risk per unit`, at a constant ~1%.

**F, G explicit; H implicit.** For options, "risk per unit" is the spread's max
loss per contract. Normalizing every loss to −1R is what makes S0 computable.
→ `size_from_risk()`, `gate_position_size()`

## S3 — Validation ladder ★★★ three-source

> **Backtest → simulator → live at minimum size → scale.** Promotion earned by
> measured metrics, never elapsed time.

**F** (backtest → demo → live) · **G** (bar replay → simulated → real) ·
**H** (sim → sim under rules → **10 days holding target metrics** → real at $5/day
→ scale the goal, never the rules).

H's metric-gated promotion is directly implementable as a deployment policy.

## S4 — Log every evaluation with structured fields ★★★ three-source

> Record instrument, direction, setup type, entry/stop/target, timestamps, exit
> reason, P/L in R, **and the conditions present at entry.**

The condition fields are the point: F's example is discovering post-hoc that every
winner had ≥5 S/R touches, which then becomes a filter. **The log is raw material
for finding which conditions carry the edge.** Our `DecisionRecord` extends this
by logging refusals too.

## S5 — Derive risk limits from the backtest ★★ two-source

> Extract longest losing streak, longest drawdown, largest single loss **before**
> going live. These are the **kill-switch thresholds.**

**F explicit, H via metric-gated phases.** For DELTAX: a live drawdown exceeding
the backtested worst case means the edge changed, not that we persevere.

## S6 — Selectivity: not trading is a position ★★ two-source

> **F:** no edge in choppy, structure-breaking markets. **H:** A+ setups only.

Echoes ClearValue's "no trade is a valid outcome" from the options bucket.
Already expressed in our architecture: refusal is a first-class logged outcome.

## S7 — Selection before analysis ★ single-source, high implementation value

> Technical analysis only works on instruments with a real supply/demand
> imbalance. **Screen first, chart second.**

**Source H**, for US small-cap momentum:

| # | Filter | Threshold |
|---|---|---|
| 1 | Float | < 10M shares |
| 2 | Intraday move | ≥ +30% |
| 3 | Catalyst | breaking news present |
| 4 | Price band | $3 – $20 |
| 5 | Relative volume | ≥ 5× normal |

**Relevance to an options agent:** these choose the *underlying*, not the
contract. But note the tension — low-float small caps with 30% moves have thin,
wide options chains, and our `gate_liquidity()` (OI ≥ 500) will reject most of
them. The live SPCX chain (OI of 6) is exactly that case. **S7's screening logic
is sound; its specific thresholds were tuned for share trading and would need
re-derivation for optionable names.** Treat the *method* as the contribution.

---

## Tier 2 — Candidates awaiting validation

| Rule | Sources | Note |
|---|---|---|
| Trade with the established trend | F G H I | Unanimous but too generic to test as stated |
| Enter on pullbacks, not extensions | F, G, I | F: pullback phase. G: break-and-retest. I: zone re-entry |
| Validated-structure trend definition | I | A low flips the trend only if it previously broke the opposing extreme. Precise and codeable |
| Confluence scoring | F, G | Count independent confirmations; require a minimum. Thresholds must come from our data |
| Fair value gaps | G | 3-candle pattern, wicks 1 and 3 non-overlapping. Mechanically defined |
| Fibonacci 50 / 61.8 | F, G | ⚠️ G justifies it via seashells and facial symmetry — numerology. Test as a self-fulfilling reference, not a law |
| One instrument at a time | F | Guards against pooling regime-specific behaviour |

---

## Process notes that don't transfer literally

This bucket spends heavily on **trading psychology** — loss spirals, revenge
trading, discipline. G's third reframe is the keeper: **a profitable trade is not
automatically a good trade.**

**For an automated agent the apparatus is replaced by construction.** DELTAX
cannot tilt. Our discipline is the absence of a discretionary override — which is
why `deltax/gates.py` has no model-overridable path. G's reframe survives
translation intact as an evaluation principle: **judge the process, never the
individual outcome.**

---

## Backtest queue

1. **S0** — implemented; it's the scoring function everything else is judged by.
2. **S1/S2 thresholds** — sweep the R:R floor and risk fraction; find where
   expectancy peaks rather than assuming 2:1 and 1%.
3. **S7 re-derivation for optionable underlyings** — the method is sound, the
   thresholds aren't ours yet.
4. **Pullback vs extension entries** — clean A/B, identical exits.
5. **Validated-structure definition (I)** vs naive structure breaks.
6. **Fair value gaps (G)** — defined precisely enough to test directly.
