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

## E13 — Validate the data before calibrating against it

> Before any threshold is tuned, the data behind it must pass an internal
> consistency check. A number fitted to broken quotes is worse than no number,
> because it looks calibrated.

**Evidence.** A full afternoon of threshold analysis — pricing model, minimum
credit, credit fraction — was run against Saturday quotes and produced
confident-looking conclusions. All of it was worthless. The quotes were frozen
at the Friday close and structurally impossible:

- bid/ask spreads of **122%, 180%, 99%** of mid
- **seven strike pairs where a lower put strike bid higher than a higher one**,
  which arbitrage forbids
- four spreads priced at **negative credit**, which cannot occur for a vertical
  credit structure

Every "the gates refuse everything" finding from that session was an artifact.
Worse, the natural response — loosening `min_credit` or `credit_fraction` until
trades appeared — would have permanently weakened live gates to fit dead data.

**The gate.** `gate_quote_sanity` runs **first**, before any economic gate:
non-positive credit on a credit structure, or quotes older than one hour, are
rejected as broken input rather than as unattractive trades. It is classified
**structural** under E10 — put prices rise with strike by arbitrage, always.

**Consequence.** Thresholds are calibrated only against live-session data.
`PRICING_MODE` is set to `haircut` (mid, conceding 25% of the crossed spread)
on reasoning rather than measurement, and is explicitly flagged for
recalibration once live quotes exist.

## E14 — Test the payoff, not the instrument

> When historical prices for an instrument are unavailable, test the **payoff
> structure** against real outcomes instead. A defined-risk position settles on
> two things: the premium taken and where the underlying finishes. Only the
> second needs history — the first can be bounded by the gate that governs it.

**The problem.** Options are OPRA-only, and Alpaca serves no historical option
quotes. Our gates price every spread from bid/ask, so a literal replay is
impossible. That blocked the entire strategy from validation.

**The way through.** A credit spread held to expiry pays exactly
`credit − breach loss`, and `gate_credit_fraction` already constrains the
credit to a floor. So assume the credit is *exactly that floor* — the worst
premium the agent would ever accept — and settle the payoff against ten years
of real underlying closes, which are freely available. Any real fill collects
at least the floor, so the result is a conservative lower bound.

**What it found.** At the floor then in force (0.90 × delta) the iron condor is
negative expectancy on every underlying and every delta tested:

| | δ 0.15 | δ 0.20 | δ 0.30 |
|---|---|---|---|
| SPY | −0.117 | −0.116 | −0.166 |
| QQQ | −0.125 | −0.141 | −0.184 |
| IWM | −0.133 | −0.138 | −0.098 |

Breakeven sits at roughly **1.03–1.20 × delta**, remarkably consistent across
nine independent cases — a spread of only ~4 percentage points of width. That
consistency argues for a structural relationship rather than noise.

**Consequence.** `CREDIT_DELTA_MULTIPLE` raised **0.90 → 1.15**. This makes the
gate *stricter* and will pass fewer trades, which is the correct direction when
the alternative is knowingly trading a negative-expectancy structure.

**Caveats, in both directions.** The model holds to expiry, so it omits the
50%-of-credit early exit that E5 mandates (would help). It places strikes by
realized volatility, so it omits the implied-minus-realized variance premium
that is the premium seller's theoretical edge (would help). It charges no
commissions or slippage (would hurt). Net effect unresolved — which is why the
floor was set at 1.15 rather than at the bare breakeven.

## E15 — Model the exit before condemning the strategy

> A strategy's expectancy is a property of entry **and exit** together. Testing
> entry logic against a hold-to-expiry exit measures a strategy nobody runs.

**Evidence.** The condor was measured as negative expectancy and the natural
conclusion was that the structure did not work. But that test held every
position to expiry, while E5 has always required exiting at 50% of credit. With
the exit modelled - close on day 7 of 14 if neither short strike was touched -
every configuration flips positive:

| | hold to expiry | exit day 7 @ 50% |
|---|---|---|
| SPY δ0.20 | +0.076 | **+0.109** |
| QQQ δ0.20 | +0.041 | **+0.107** |
| IWM δ0.20 | +0.030 | **+0.075** |
| SPY δ0.15 | +0.008 | +0.065 |
| QQQ δ0.15 | −0.002 | +0.048 |
| IWM δ0.15 | −0.021 | +0.025 |

Win rate rises from ~56% to ~67-77%. The improvement is consistent across six
independent configurations, which is what distinguishes it from noise.

**Why it works.** Exiting early halves the exposure window. Most of the tail
risk in a 14-day condor sits in the second week, when gamma rises and a move
that was comfortably outside the strikes can reach them. Taking half the credit
for a quarter of the risk-time is the trade.

**What this did NOT come from.** Four directional ideas were tested and all
failed: the VWAP regime filter, the EMA/MACD/RelVol signal family, the 20-day
high breakout, and the breakout filtered for a clear uptrend — the last of
which was *worse* than the unfiltered version, the classic signature of
over-filtering. The gain came from the exit, not from finding a better entry.

**Consequence.** Target delta narrowed to 0.20-0.22, the range the backtest
supports. The day-7 / 50% exit is promoted from a stated rule to a modelled and
measured one.

**Caveats.** The exit model approximates "reached 50% of credit" as "neither
short strike touched by day 7", since option prices are unavailable
historically. Weekly entries on 14-day holds overlap, so the samples are
serially correlated and the effective n is below 300. Strikes are placed on
realized rather than implied volatility, omitting the variance risk premium
(would help); no costs are charged (would hurt).

## E16 — A global permission state sits above strategy

> One state governs whether trading is allowed at all. Strategy cannot override
> it, evidence only *recommends* it, and when inputs conflict the agent adopts
> the **most restrictive** reading — never the average, never the optimistic one.

States, ordered by restriction: `NORMAL` → `CAUTION` → `DEFENSIVE` →
`NO_NEW_POSITIONS` → `HALT`.

**Source: Matin's live-architecture proposal.** His framing is right and
generalises a principle we already held in scattered form — E13's data
validation, S5's kill-switch thresholds, and the market-closed check were each
enforcing this idea locally. Now one component owns it.

**Translated for a condor book.** Put credit spreads carry the long-side
exposure, call credit spreads the short side. `DEFENSIVE` therefore blocks put
spreads while still permitting calls — bearish exposure without ever shorting
stock, which sidesteps borrow and locate entirely.

**What raises the state**

| Trigger | State |
|---|---|
| Stale or incomplete feed | HALT |
| Market status unknown | HALT |
| Live drawdown past the backtested worst case (S5) | HALT |
| VIX +30% or more | NO_NEW_POSITIONS |
| Market closed | NO_NEW_POSITIONS |
| VIX +15% | DEFENSIVE |
| All three benchmarks weak | DEFENSIVE |
| Any required reading unavailable | CAUTION |

**Fail-closed throughout.** A missing input never yields `NORMAL`. This is
Matin's "DATA UNCERTAIN → FAIL CLOSED → HALT", applied to every field.

**What we did NOT adopt.** His short-equity engine: a call credit spread is
already defined-risk bearish exposure, so shorting stock adds borrow, locate
and unbounded risk to reach a place we can already stand. His Market
Intelligence layer (Asian markets, futures, three daily news scans) is sound
architecture but is an empirical claim about global risk-off predicting local
outcomes — untested, and E10 requires that testing before it can gate anything.
Queued behind the catalyst engine.

## E17 — Measure the hold period you can actually execute

> An expectancy figure is only valid for the exit it was modelled on. If the
> contest window closes before that exit fires, **the number does not describe
> the trade you are placing.**

**How we found this.** E15 promoted the day-7 / 50%-credit exit after modelling
it flipped every configuration positive (held-to-expiry −0.021 to +0.076 →
+0.025 to +0.109). We then quoted **+0.107** as the strategy's expectancy for
weeks. Checking the calendar against the contest deadline:

| | |
|---|---|
| Entry | Mon 31 Aug 2026 |
| Modelled exit | day 7 = **Mon 7 Sep** |
| Submission deadline | **Fri 4 Sep, 11:00 ET** |
| Trading sessions available | **5** (Labor Day 2026 falls 7 Sep, outside the window) |
| Usable, allowing for a truncated Friday | **~4.5** |

The exit that produced our headline number fires **three days after the
contest ends.** Positions will instead be marked to market having captured
partial decay. The 4-day expectancy has never been measured.

**The rule.** Before trading a fixed-length event, re-measure expectancy at the
hold period the event permits. Never carry a number across a change in exit.

**Second-order consequence — the DTE band is also unvalidated for this window.**
`MIN_DTE=7 / MAX_DTE=21` was tuned for a system that holds to its modelled
exit. Theta accelerates into expiry, so across a fixed 4-day hold a nearer-dated
contract decays a larger fraction of its premium — at the cost of gamma. Which
expiry maximises a 4-day hold is an empirical question we have not asked.
**Do not change the band on reasoning alone; sweep it.**

**Why this is a rule and not a footnote.** We came within a day of trading a
five-session contest on a seven-day number, having done the validation work
correctly and then failed to check it against the calendar. The error was not
in the modelling. It was in never asking whether the modelled exit was reachable.

## E18 — Test the expiries that exist, not the ones on your grid

> A backtest grid is a set of hypotheses. The market lists a specific,
> **discrete** set of expiries. Optimising over a grid the market does not
> offer produces a recommendation that cannot be traded.

**Evidence.** The 4-day sweep (E17) was run across 4/5/7/10/14/21/30 DTE and
showed a clean monotonic result: shorter DTE captures more of a fixed 4-day
hold, exactly as theta acceleration predicts. The apparent winner was 5–7 DTE.

Querying the actual chain for a Mon 31 Aug entry:

| Expiry | DTE | Listed |
|---|---|---|
| Fri 4 Sep | 4 | ✅ |
| Fri 11 Sep | 11 | ✅ |
| Fri 18 Sep | 18 | ✅ |

**5, 7 and 10 DTE do not exist.** Equity options list Friday weeklies; only
SPY, QQQ and IWM carry dailies. Worse, **BDX and CB list no weeklies at all** —
their nearest expiry is the 18 Sep monthly. A universe rule that assumes a
weekly is available for every name is wrong.

**Consequence — the two findings collide.** Re-running walk-forward at the
expiries that exist, δ0.20, TRAIN ≤2023 / TEST ≥2024:

| | Sep 4 (4 DTE) | Sep 11 (11 DTE) | Sep 18 (18 DTE) |
|---|---|---|---|
| SPY | **+0.245, t=2.70** | +0.109, t=1.22 | +0.030, t=0.33 |
| QQQ | +0.136, t=1.63 | +0.023, t=0.32 | −0.020, t=−0.29 |
| IWM | **+0.251, t=2.84** | +0.147, t=1.73 | +0.076, t=0.92 |
| **Gate** | **BLOCKED** by MIN_DTE=7 | passes | passes |

**The only out-of-sample-significant configuration is the one our own gate
forbids.** Everything MIN_DTE permits is positive in point estimate but not
statistically distinguishable from zero.

**The rule.** Enumerate the tradeable instruments *before* sweeping parameters,
and constrain the grid to them. A parameter study on unavailable instruments is
not conservative or optimistic — it is unusable.

**Do not resolve this by relaxing MIN_DTE on the strength of this table.**
The 4-DTE cell is where the model's constant-implied-vol assumption is weakest,
where gamma is largest, and where R5 was aimed. See E19.

## E19 — Per-trade expectancy is not one-week expectancy

> Expectancy is measured across independent trades spread over years. A
> one-week contest gets **one** draw. When every position shares a market
> factor, spreading across 40 tickers does not give 40 independent bets.

**The error to avoid.** SPY δ0.20 Sep 4 shows a 63% win rate out of sample. It
is tempting to read that as "63% of our positions win." It is not. That figure
is 63% of *weeks* winning, sampled over 127 independent weeks.

Within a single week, direction-neutral condors on 40 correlated equities are
approximately **one bet on realised market volatility.** If the market makes a
sharp move Thursday, the put spreads breach together. Diversification across
tickers reduces idiosyncratic risk; it does almost nothing against the market
factor, which is what a condor book is actually short.

**Consequence for sizing.** The 10% portfolio cap is not a 10% worst case
across independent positions — in a correlated move it is closer to a genuine
10% single-event loss. That is survivable by design, and it is the reason the
cap exists. Do not raise it on the strength of a per-trade win rate.

**Consequence for expiry choice.** Shorter-dated condors have the largest
gamma, so a single adverse day translates into the largest mark-to-market
swing. Observed worst case, SPY δ0.20: **−$270 at Sep 4** (the full max loss)
versus −$251 at Sep 11 and −$207 at Sep 18. The shortest expiry both maximises
expected return and maximises the correlated tail — in a contest scored once,
on a fixed date, with no time to recover.

## E20 — A gate that passes its unit test may still never fire

> Unit-testing a gate proves the **function** works. It proves nothing about
> whether the pipeline ever reaches it. Test every gate through the real
> evaluation path, and assert it fires **by name**.

**Source: Matin's crypto engineering review.** His team found a daily-trend
risk filter that "had never actually blocked a single trade since it was built,
despite passing every isolated unit test" — a wiring gap, not a logic error.
We took that as a prompt to audit our own chain and found two instances.

**Finding 1 — a crash where a refusal belonged.** `evaluate()` called
`size_from_risk()` before running `gate_defined_risk`. A `None`
`max_loss_per_contract` therefore raised `TypeError` and aborted the run,
instead of producing the refusal that gate exists to produce. The gate passed
its own tests and was unreachable for its primary case.

This is worse than a missed refusal. **A crash is not a refusal:** it writes no
decision, leaves the ledger silent, and loses the audit record. Undefined risk
is now refused before any arithmetic depends on it.

**Finding 2 — a gate that is a tautology.** `gate_position_size` cannot fail
through `evaluate()`. `size_from_risk()` floor-divides by the same
`PER_POSITION_RISK_PCT` cap the gate checks, so `contracts x max_loss <= budget`
holds by construction.

It is **not** removed — it is a genuine regression guard against a future change
that sizes by some other rule, and it works when called directly. But it must
not be counted as active protection. A test now asserts the invariant that makes
it redundant, so if sizing ever stops deriving from the cap, that test fails
loudly rather than the gate silently starting to matter.

**The rule.** `tests/test_wiring.py` trips each gate through `evaluate()` and
asserts the refusal is attributed to that gate by name, on a baseline that is
first proven to APPROVE — otherwise every case passes vacuously. Any gate that
cannot be provoked there is either unreachable or a tautology, and the team is
entitled to know which.

## E21 — The same conclusion from an unrelated asset class

> Independent replication on different data, in a different market, by a
> different team, is stronger evidence than any single result.

**E15** found that the condor's edge lived in the **exit**, not the entry:
held to expiry the strategy was marginal, and modelling the day-7 exit flipped
every configuration positive.

Matin's crypto permutation study reached the same conclusion from the opposite
direction. Testing a momentum strategy on MEXC perpetuals against 200
randomised controls:

| Metric | Real | Random | p |
|---|---|---|---|
| Profit factor | 1.020 | 0.936 | 0.085 |
| Expectancy | 0.190 | −0.530 | 0.085 |
| **Avg MFE (R)** | **2.322** | 2.068 | **0.000** |

**The entries locate genuinely better maximum favourable excursions than random
(p = 0.000), while overall profitability is not significant (p = 0.085).** The
strategy finds good moves and the exit logic fails to convert them.

Equities and crypto, options and perpetuals, two codebases, two teams — both
land on the exit as the binding constraint. That is the strongest support E15
has, and it did not come from our own data.

**Consequence.** Exit modelling is promoted from an options-specific technique
to a house rule: no strategy in any asset class is evaluated, accepted or
rejected on entry logic alone.

## E22 — Raising size changes the account, not the edge

> Per-trade expectancy is a per-contract R-multiple. It does not improve or
> degrade when you trade more contracts. What scales with size is the **account
> outcome distribution — in both directions, symmetrically.**

**The decision.** The team allocated $30,000 to options (from $10,000), $60,000
to stocks and $10,000 to crypto. `PORTFOLIO_RISK_PCT` therefore moves
**0.10 → 0.30**. Nothing about the strategy's validation changes: E is still
+0.109 (SPY, Sep 11, out-of-sample). The number of contracts triples, the
expected return triples, and **so does the worst case: −10% becomes −30%.**

**Per-position stays at 2%.** With a $30,000 budget and a $2,000 per-position
cap, deploying the full budget requires **at least 15 distinct positions**. That
is deliberate: E19 established that a condor book is approximately one bet on
realised market volatility, so the defence available is many small positions
rather than few large ones. Raising the portfolio cap without holding the
position cap would have produced concentration, which is the opposite of what
the evidence asks for.

**The kill switch had to move with it.** `max_backtested_drawdown_pct` was
−10%, matching the old budget. Left there, it would have fired on a routine bad
day at the new size and frozen the agent mid-contest — a threshold calibrated
for one risk level silently becomes wrong at another. It is now **−20%**: two
thirds of the deployed budget, which stops us with a third still unspent and
80% of the account intact. Halting only after the entire budget is gone is not
a circuit breaker.

**Tests were hardcoding the old thresholds.** Five cases asserted against −11%,
−6.5% and $9,950 literals. They passed the moment the constants moved while
testing nothing — the same silent drift that left `condor_expectancy.py`
pinned at `CREDIT_MULT=0.9` after the gate moved to 1.15. Every risk test now
derives its inputs from the live constant.

**Rule.** A threshold expressed as a percentage of equity is coupled to every
other such threshold. Move one and re-derive the rest, or the safety chain
quietly develops a gap at the new size.

## E23 — Quote two bounds, not one number

> Our two estimates of the same week's return differ by a factor of nineteen.
> Reporting either one alone would misinform the team.

| Method | Basis | This week on $30,000 risk |
|---|---|---|
| BS model, walk-forward | credit at the **gate floor**, constant IV, no fills above minimum | **≈ +$723** |
| Last-week replay | **actual chain prices**, 5 names | **≈ +$13,800** (+46% on capital at risk) |

Both are honest; they answer different questions. The model asks *what if every
fill is the worst the gate would accept* — a deliberate lower bound. The replay
asks *what did real quotes actually pay* on one week that has already happened,
which is a single sample and cannot be a distribution.

**The truth is bracketed, not pinpointed.** Real fills land above the floor, so
the model understates; one week's replay cannot be extrapolated, so it
overstates as a forecast. Report the range and say which assumption produces
each end. A single confident number here would be the least defensible thing in
the whole write-up.

## E24 — Size the sleeve by what it contributes, not by what it costs

> Capital allocated and return contributed are different quantities. A sleeve
> can hold most of the money and produce almost none of the result.

**Combined-book backtest** (SPY history, 4-day Monday→Friday hold, team
allocation):

| Sleeve | Capital | Mean/week | Return | t | Win% | Worst |
|---|---|---|---|---|---|---|
| Options (condor) | $30k risk | **+$774** | 2.58% | **2.10** | 68.4% | −$27,914 |
| Stocks (covered call) | $60k | +$73 | 0.12% | 1.27 | 61.3% | −$5,338 |
| Crypto (spot ×4) | $10k | +$86 | 0.86% | 1.69 | **52.2%** | −$1,978 |
| **Combined** | $100k | **+$1,134** | 1.13% | 2.24 | 71.3% | −$21,168 |

**The options sleeve produces 83% of the return on 30% of the capital.** The
other $70,000 contributes $159 a week between them and carries most of the
directional risk.

**Why covered calls underperform here.** Over a 4-day hold on an 11-DTE call
there is very little premium to capture, so the sleeve is dominated by the
stock's own move — it is long beta with a small overlay, not a premium
strategy. Its t of 1.27 says so. Covered calls need a longer hold or a nearer
strike to earn their place; at this horizon they are a compliance structure
more than an edge.

**Crypto spot wins 52.2% of weeks.** That is a coin flip, and it independently
reproduces Matin's conclusion from a different venue and codebase: the crypto
directional premise has no measured edge.

**Median beats mean, everywhere.** Combined median is +$3,444 against a +$1,134
mean — the signature of premium selling. Most weeks are quietly good and the
occasional week is very bad. Never quote the mean alone for a book like this.

**Caveat on the combined row.** Crypto has 136 weekly samples against the
equity book's 282, and the sleeves are index-paired rather than date-aligned.
Per-sleeve figures are sound; the combined row is indicative, not exact.

**Kill switch:** a −5% daily limit fires in **14% of weeks** on this book.

## E25 — History is not evidence that something still exists

> A clean price series proves an instrument **traded**. It says nothing about
> whether it **trades**. Check listing at nomination, not at order time.

**Evidence.** `TRX/USD` returns 332 clean daily bars ending 2023-04-19 and
**zero** bars for August 2026 — Alpaca delisted it. Every backtest reads
perfectly; an order would meet no market. `BTC/USD` and `SOL/USD` return 28
bars over the same window, so this is a delisting, not a data outage.

`gate_listed` now refuses on three grounds, fail-closed on all of them:

| Condition | Result |
|---|---|
| Venue reports asset not tradable | REFUSE |
| Last bar older than the age limit | REFUSE |
| Either fact unavailable | **REFUSE — unknown is not safe** |

Age limits differ by asset class: **4 days for equities** (weekends and
holidays are legitimate silence) and **1.5 days for crypto**, which trades 24/7
and has no excuse for going quiet.

**A second, larger instance of the same error.** Five tickers — JBGS, ZETA,
ACHC, BV, FN — were carried in `STATUS.md` as universe candidates on the
strength of a 314-name expectancy screen. The screen results were never written
to disk, so the recommendation outlived its evidence. Checking the live chains:

| | Liquid strikes | |
|---|---|---|
| ZETA | 15 | ✅ tradeable |
| ACHC | 4 | ❌ |
| FN | 3 | ❌ |
| JBGS | **0** | ❌ |
| BV | **0** | ❌ |

**JBGS scored best of all 314 names and cannot be traded at all.** `BDX`, already
in the universe, also fails at 3 strikes. Ranking on price history alone
manufactures candidates that the gates would refuse anyway — the universe-level
form of E18.

**Breadth was checked rather than assumed.** Of 39 names swept, **34 are
tradeable and 29 carry a Sep 11 weekly** — up to 58 positions against the 15
needed to deploy $30,000 at 2% each. Sufficient, but that is now a measured
fact rather than a hope.

**Wiring note, and an irony.** The first attempt at this passed the listing
evidence to `execute.submit()` instead of `evaluate()` — the gate would never
have run, exactly the failure E20 was written about. `tests/test_wiring.py`
asserts it fires through the real path.

## E27 — A leak detector must not carry the secret it detects

> Hardcoding a credential in order to search for it puts that credential
> everywhere the search code goes. Read the value at runtime; never embed it.

**Evidence.** `bin/preflight.sh` checked for leaked keys with a literal grep:

```
git grep -qI "PK<the-literal-key-was-here>" ...
```

The check was correct and the intent was defensive. It still published the API
key to a public repository, and — because git history is permanent — the key
stayed **publicly fetchable** at commit `5335a27` after the working tree was
cleaned. Confirmed by fetching it over plain HTTPS with no credentials.

**Severity is decided by what is NOT exposed.** Alpaca requires key *and*
secret. The secret was verified absent from the working tree and from the
complete history across all refs, so the account was never accessible. This is
a leak, not a breach — but the distinction is luck about which of two values
got embedded, not a control that held.

**The permanent fix is rotation, not deletion.** Removing a secret from the
working tree does nothing; rewriting history is disruptive, breaks every clone,
and still cannot recall what was already fetched or cached. Rotating makes the
leaked value worthless, which is the only outcome that does not depend on
guessing who read it.

**Defence in depth now in place**

| Layer | Control |
|---|---|
| Pre-commit | `.githooks/pre-commit` refuses credential-shaped strings and any `.env` file |
| Push | GitHub push protection blocks secrets server-side |
| Repository | GitHub secret scanning, enabled |
| Storage | `.env.alpaca`, mode 600, gitignored, never tracked |

**This rule caught its own documentation.** The first attempt to commit E27
quoted the offending line verbatim, and the new pre-commit hook refused it. The
example above is redacted because the hook would not allow it through — which
is the control working, demonstrated on the person who wrote it.

**Rule.** Any check for a secret reads it from the environment at runtime.
Any automated job that commits stages named files only — never `git add -A`,
which is one stray write away from publishing everything.

## E28 — "Nothing found" and "could not look" are different answers

> A gate that returns the same value for *checked, clean* and *check failed*
> is at its most permissive exactly when it is least informed.

**Evidence.** `gate_no_earnings_before_expiry` took `earnings_date=None` and
passed. But `None` meant two unrelated things: an ETF that files no 8-K and
genuinely has no earnings, or a SEC lookup that raised. The morning brief made
the collapse visible and it went unread:

```
EARNINGS BLACKOUT  (0 blocked)
   UNCHECKED: DIA (RuntimeError); EEM (RuntimeError); TLT (RuntimeError); ...
```

Nine names could not be checked and none was blocked. A SEC outage — a rate
limit, a 403, a network blip — would have waved every candidate through the one
gate whose entire job is refusing to sell premium into an earnings event.

**Why the ETF case makes this subtle.** The obvious fix, refuse on `None`,
would block the whole income universe, since ETFs correctly have no earnings
date. The states had to be separated rather than merged: `checked=True` with no
date is a clean bill of health; `checked=False` is an admission of ignorance
and refuses.

**Rule.** Every gate reading an external source carries an explicit
*was-this-check-possible* flag, distinct from what the check returned. Absence
of evidence is not evidence of absence, and in a risk gate the difference is
the whole point.

**Pattern.** This is the third instance of the same failure shape in two days —
E20 (a gate that could never fire), E25 (history mistaken for existence), and
now E28. All three passed their unit tests. All three were found by asking what
the code does when the world does not answer.

## E30 — Ask the broker what you hold before opening anything

> `run()` started `committed = 0.0` on every cycle and never queried open
> positions. Scheduled every five minutes from 09:30, that is **96 runs a day,
> each believing the book was empty.**

**What would have happened today.** The simulation opens 12 positions per run
at roughly $23,100 of risk. The $30,000 portfolio cap would have been breached
on the **second** run, and the account would have carried on the order of 1,150
positions by the close. The cap was not weak — it was measuring the wrong thing.
`open_portfolio_max_loss` was seeded from the current cycle's fills, so it
described one run, never the book.

**Reconciliation is not bookkeeping.** It is the thing that makes a risk limit
mean anything across more than one cycle. A cap that resets every five minutes
is not a cap.

`deltax/reconcile.py` now runs before any candidate is considered:

| | |
|---|---|
| Seeds `committed` | from the live book's short legs, not from zero |
| Records `held` | `(underlying, side)` pairs — an existing leg is never re-opened |
| Fails closed | an unparseable position refuses **all** new risk |
| Logged | every cycle, to the ledger |

**Two further faults found in the same pass.**

*An order failure aborted the whole run.* `execute.submit()` raises on a
rejected order, a preflight mismatch, or a CLI error, and nothing caught it.
The fifth of twelve orders failing would have left four positions open, eight
never attempted, and no summary written — then the next cycle would have opened
the first four again. Each candidate is now wrapped: the failure is recorded,
that candidate is skipped, the rest of the book proceeds.

*A guard tested a string that is never returned.* `rec["result"] not in
(None, "REFUSED")` gated exit placement, but `submit()` raises rather than
returning `"REFUSED"`, and the live value is `"SUBMITTED"`. It now matches on
the prefixes actually produced.

**How these were found.** The user asked for a bug check five hours before live
trading. All 343 tests passed the whole time. Tests verify the code does what
it says; none of them asked what happens on the *second* run.

**Rule.** Any agent that runs on a schedule must reconcile against external
state at the start of every cycle. State held only in a local variable is state
that resets, and a limit computed from it silently stops being a limit.

## E29 — A documented rule that nothing calls is not a rule

> E5 required a GTC exit at every fill from day one. `build_close_args()` was
> written to place it. **Nothing ever called it.** For two days the agent could
> open positions and had no way to close one.

E15 measured the exit as the *source* of the edge — the 50% close flips every
configuration positive. An agent that opens and never closes is not a weaker
version of the backtested strategy; it is the version we measured as marginal.

`deltax/manage.py` now owns both halves: `place_exit()` rests a GTC
buy-to-close at 50% of credit at fill time, and a 2-DTE time stop closes
regardless of profit. Found by the user asking why the bot was not "following
sales" — all tests were green while the strategy was missing half of itself.

**Rule.** Every corpus rule that mandates an action needs a test asserting the
action actually happens. Otherwise the corpus documents intentions, and reads
exactly like a system that works.

*(Note: this entry was itself lost once — its original commit was blocked and
the corpus text silently dropped while the code landed. Restored 31 Aug.)*

## E31 — A threshold without a deadband classifies noise as signal

> `price < vwap` has no noise floor. Any gap counts, however small. On the
> agent's first live session that blocked the entire put side of the book on a
> flat tape.

**Evidence, 31 Aug 09:45 ET — the first entry window the agent ever reached:**

| | Gap vs VWAP | Classified |
|---|---|---|
| SPY | −0.05% | WEAK |
| QQQ | **−0.004%** | WEAK |
| IWM | −0.26% | WEAK |

3/3 weak → `DEFENSIVE` → put spreads blocked → **38 candidates refused, zero
trades.** QQQ was four thousandths of one percent below its average price. That
is not a regime; it is a tick.

A **0.15% deadband** re-reads the same tape as 1/3 weak → `NORMAL`, put side
open at full size.

**Why this is a fix and not a loosening.** The test applied before changing it:
*would I make this change if it BLOCKED trades instead of unblocking them?*
Yes — a 0.004% gap is not a market regime in whichever direction it points, and
a rule that reads it as one is wrong on the days it costs nothing as well as the
days it costs a session. The tests assert the symmetry: noise **above** VWAP is
ignored on the same terms.

**What was deliberately NOT changed.** Risk caps, kill switches, credit floor,
liquidity gates — all firing correctly, all untouched. The change is confined to
how one measurement is classified.

**The larger admission this exposed.** The `3/3 weak → DEFENSIVE` rule was never
backtested; it was written from reasoning. Meanwhile **E11**, which *was*
backtested, found the regime filter has no directional edge at all (t = −1.29,
sign inverted). So an unproven rule was blocking half the book — precisely what
**E10** exists to prevent, sitting in our own corpus unnoticed until it cost a
session.

**Outstanding work, tonight.** Backtest whether 3/3-weak genuinely predicts
worse put-spread outcomes. If it does not, `DEFENSIVE` should reduce **size**,
not block a **side** — caution without a directional bet the evidence does not
support.
