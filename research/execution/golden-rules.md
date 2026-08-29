# DELTAX — Golden Rules: Execution & Timing

New category, established 2026-08-29. These rules are asset-agnostic — they
govern *how* and *when* the agent acts, not *what* it trades. Provenance: this
week's session-timing work, the structure-aware gate fix, the two-book entry
spec, and the competition playbook. Several were discovered by building, not by
watching videos — which is worth noting: **the build process is now generating
rules the corpus never contained.**

---

## E1 — Enter where the book is deep

> Confine entries to the venue's deep-liquidity windows. For US options:
> 9:45–10:30 and 14:30–15:15 ET. Never the first 15 minutes, never the lunch
> lull, never after 15:15.

The *principle* transfers across venues; the *specifics* never do. Equity
liquidity is U-shaped around auctions; crypto liquidity follows the sun, thins
on weekends, and pulses around 8-hour funding timestamps. Encoding one venue's
clock into another venue's engine is a category error (see
`../crypto/golden-rules.md`).

Echoes source B's open-interest rule from the options corpus — same insight,
time dimension instead of contract dimension.

## E2 — Most active ≠ best to enter

> The heaviest hour (15:00–16:00 ET) is the *worst* for opening: closing and
> hedging flows, 0DTE churn, and uncompensated overnight gap risk on anything
> fresh. Peak activity is for exits, not entries.

Raw volume only helps when it arrives with tight spreads and time for the
position to breathe. "When is the market most active?" and "when should the
agent enter?" have different answers, and conflating them is how the
trade-the-open folklore gets people filled badly at 9:31.

## E3 — Payoff gates must be structure-aware

> Credit structures: **credit/width ≥ 0.9 × short delta**. Debit structures:
> **reward:risk ≥ 2:1**. One floor applied to both silently refuses an entire
> structure class — and a *flat* floor on credit structures refuses most of the
> delta band.

Discovered as a live bug: our original 2:1 gate would have refused *every* OTM
credit spread — a credit spread's payoff IS its probability, so it can never
show 2:1. The replacement flat 30%-of-width floor then failed the same way for
a subtler reason: measured on live chains, credit/width runs ≈ 0.75–0.8 × short
delta, so any fixed floor selective at 35Δ silently bans every trade at 20Δ —
exactly where the regime logic pushes when markets weaken. The floor had to
become **delta-relative** to ask the economically meaningful question: is this
premium fair for the probability of loss being taken?

Generalization: **before going live, run every structure the agent will trade
through the gates and confirm at least one realistic candidate of each class
can pass.** A gate that can never pass is a ban you didn't mean to write —
and it can hide behind a number that looks reasonable.

## E4 — Triggers nominate; gates decide

> Analyst logic (human or model) may only *nominate* candidates. Entry
> authority lives exclusively in the deterministic gates; capital arbitration
> between books is arithmetic, not opinion.

This is what lets two teammates with *different* market views (Elsa's regime
mean-reversion, Matin's momentum signals) coexist in one account without
negotiation: each owns a nomination stream, neither owns the trigger. The
three-way AI-proposes/code-disposes convergence, extended to humans.

## E5 — Exits are placed at entry

> The exit order (GTC: buy back at 50% of credit; sell at 100% gain on debit)
> goes in the moment the entry fills. Freed risk budget recycles into the next
> gated candidate.

No intraday exit improvisation, no watching positions. For a short window this
is also the compounding engine: budget that exits early re-enters the queue.
Echoes Sky View's "take profits early" and B's scale-out — but as standing
orders, not discretion.

## E6 — Branches are decided before they arrive

> Any foreseeable decision point (a macro release, a deadline, a drawdown
> level) gets its branch pre-registered: *if green → X, if red → Y*, with caps
> attached. The branch executes mechanically when the condition lands.

Instance: the Friday jobs-report branch (green Thursday → flatten Thursday;
red → carry ≤4% capped recovery, flat by 10:15). The same trade improvised at
8:25 Friday is panic; pre-committed on Saturday it's strategy. Extends
pre-registration from parameters to *decisions*.

## E7 — Raise risk only where the floor stays arithmetic

> Tournament posture = a structural floor plus bought skew. Caps may rise
> (1%/5% → 2%/10% for the competition), but only on defined-risk structures
> where the worst week is a *known number chosen in advance*. Undefined risk
> and 0DTE stay banned at any risk appetite.

A busted account finishes last on P&L too. The floor (−10% → $90k) is not a
prediction; it's arithmetic. That's the difference between aggressive and
reckless, and it's the sentence for the judges.

## E8 — Sell premium when it's rich: mornings

> The income book favors the morning window: IV still carries overnight
> uncertainty (richer credit for the same strike), and theta accrues from
> entry — an earlier fill of equal quality strictly dominates a later one.

Afternoon window is for topping up, not for initiating the day's core.

## E9 — Time-of-day is hygiene, never signal

> Session windows exist for fill quality only. No "reversal time," no
> open-drive lore, no timing-based directional rules — those are corpus-grade
> folklore and stay out of the agent unless they someday pass the validation
> bar like any other hypothesis.

Guards E1/E2 from scope creep: the moment a timing rule starts *predicting*
instead of *protecting fills*, it must requalify as a signal through
backtest + pre-registration.

## E10 — Classify before encoding

> Every candidate rule declares itself **structural**, **empirical**, or
> **operational** before it can enter the agent. Structural needs one
> verification. Empirical needs the full validation bar. Operational needs
> neither. An unclassified rule cannot ship.

| Class | Meaning | Standard of proof |
|---|---|---|
| **Structural** | True by construction — a property of how the market is built | Verify once |
| **Empirical** | A pattern that may be signal or noise | OOS PF > 1.10, >50% folds positive, E > 0, no post-holdout tuning |
| **Operational** | Execution hygiene | Neither — but it must never be cited as edge (E9) |

**Why this rule exists.** A single live session inspecting one option chain
produced, in the same hour: two structural facts worth encoding permanently, one
genuine bug in our own gates, and two empirical claims that would have been
data-mined nonsense if promoted. All five *felt* equally like findings. Without
an explicit class, the empirical ones get encoded on the strength of having been
observed — which is precisely the failure that the entire video corpus
demonstrates and that killed the TSLA playbook.

**Worked example (AVGO, 2026-08-29):**

| Observation | Class | Action |
|---|---|---|
| Open interest clusters at round strikes (9,180 at $330 vs **14** at $332) | Structural | Encode |
| Bid/ask width tracks OI (0.7% at the liquid strike vs 16.9% at the thin one) | Structural | Encode |
| Earnings gate reported "safe" when it meant "unknown" | Bug | Fix |
| IV at 52–54% implies an approaching earnings event | Empirical | Queue for testing |
| A 30.7% credit at 0.307 delta is fair value | Empirical | Queue for testing |

Note that "bug" is a fourth outcome and the most valuable one that session
produced. Inspecting live data is excellent for finding what is *broken* and
what is *structurally true*; it cannot establish what is *profitable*.

## E11 — Direction-neutral until a directional edge is proven

> Absent a directional signal that has cleared the validation bar, a premium
> seller takes **both sides** (iron condor) rather than picking one. Choosing a
> side on an unvalidated signal is an unpriced directional bet wearing the
> costume of a strategy.

**Evidence.** Our port of the SPY/QQQ/IWM VWAP regime filter was driving the
income book's choice between put and call spreads. Tested over 2,679 sessions
(2016–2026) against SPY forward returns:

| Weak count | n | +5d mean | up % |
|---|---|---|---|
| 0 | 1,114 | +0.184% | 59.7% |
| 1 | 412 | +0.341% | 62.4% |
| 2 | 324 | +0.414% | 63.6% |
| 3 | 824 | +0.329% | 61.5% |
| *base rate* | *2,674* | *+0.281%* | *61.1%* |

No separation (0-weak minus 3-weak: t = −1.29, not significant), the ordering
is non-monotonic, and the sign runs **opposite** to the hypothesis — the
supposedly bullish 0-weak bucket has the *lowest* forward return.

Worse for the posture we had planned: after 3/3 weak — which our rules mapped
to **call** credit spreads, a bearish position — SPY still rose 61.5% of the
time over 5 days and 67.2% over 14, essentially matching the unconditional base
rate. We would have been selling calls into a market that drifts up.

**Scope.** This tests *our repurposing*, not Elsa's engine. Alyrise uses the
filter to deepen a dip-buying entry threshold on stocks, which is a different
claim we have not tested and are not disputing.

**Consequence.** The filter is demoted from direction selection to context. The
income book defaults to **iron condors** — both sides gated and sized
independently — until a directional signal clears the bar.

## E12 — Idle capital goes to the strategy that needs no edge

> When a directional signal fails to clear the validation bar, the capital
> earmarked for it does **not** get deployed on the unproven signal anyway,
> and does **not** sit idle by default. It moves to the strategy that does not
> require a directional edge.

**Evidence.** Matin's Equity Lab signal family was tested over 32,148 daily
bars across 12 names, entry at next open, measured against the unconditional
base rate for the same universe:

| RelVol | Horizon | n | Edge vs base | t |
|---|---|---|---|---|
| **1.0** (his original) | 5 / 10 / 15 | 326 | −0.271 / 0.000 / −0.875 | −0.79 / 0.00 / −1.39 |
| 1.5 (our tightened) | 10 | 111 | +1.409 | +2.14 |
| 2.0 | 10 | 58 | +2.213 | +2.41 |

Walk-forward TRAIN 2016–22 / TEST 2023–26 at 10 days: the sign **held out of
sample** (t = +1.42 and +1.95 in TEST) but nothing reached |t| > 1.96 in either
period alone, against a Bonferroni floor of 2.77 for the nine combinations
examined. Out-of-sample n was 27 and 18.

**Not proven, not refuted.** Two things follow, and the second is the rule:

1. His original RelVol ≥ 1 threshold shows no edge at all. Our tightening to
   1.5 is what produced the positive result — which is specification search,
   and choosing 2.0 now *because it looked best in TEST* would be post-holdout
   tuning.
2. Building a debit-spread book on an unvalidated directional signal means
   paying bid/ask for an edge we have not demonstrated. Defined risk caps the
   loss; it does not make the expectancy positive.

**Consequence.** The 40% satellite allocation is redeployed to additional
income-core positions — credit structures need no directional edge, we have 19
qualified underlyings for what was 3 slots, and E11 already defaults them to
direction-neutral condors. The signal returns to the backtest queue for a
proper walk-forward with adequate sample, post-hackathon.
