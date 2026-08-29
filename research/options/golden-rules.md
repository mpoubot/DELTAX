# DELTAX — Golden Rules Repository

Cross-video synthesis. Rules are promoted by **independent multi-source
agreement**, not by how confidently any one presenter states them.

**Corpus status:** 6 videos processed · **5 independent viewpoints** · options
module complete · **this is the whole corpus** — the agent trades options only
**Last updated:** 2026-08-29

---

## Source ledger

Weighting is by *viewpoint*, not by video count.

| ID | Source | Videos | Stance | Conflict of interest |
|---|---|---|---|---|
| **A** | Sky View Trading | 01, 03 | Sell defined-risk premium, harvest theta | Paid program ("part two") |
| **B** | Chart Fanatics / Usman Ashraf | 02 | Buy premium, directional, 0DTE–weekly | Prop-firm sponsors + own Options Hub |
| **C** | ClearValue Tax / Brian Kim | 04 | Covered calls + CSPs as yield overlay | Own website |
| **D** | Andrei Jikh / Alex Pandrea | 05 | Covered calls, CSPs, LEAPS for retail | Affiliate links |
| **E** | The Wall Street Journal | 06 | Journalism on 0DTE risk | **None — only disinterested source** |

⚠️ **Videos 01 and 03 are the same channel** — 03 is a condensed, older cut of
01's pricing chapter. They count once. Ranking these videos by view count will
keep surfacing duplicates from a few large channels; check the channel before
adding slot 6+.

---

## Tier 1 — Structural facts (unanimous)

Not rules, but the foundation the agent must model correctly. No dissent across
any source.

| # | Fact | Sources |
|---|---|---|
| 1 | 1 contract = 100 shares; quoted premium ×100 | A B C D |
| 2 | OTM at expiration is worthless; ITM is worth intrinsic only | A B C D |
| 3 | Contract value = intrinsic + extrinsic | A B C |
| 4 | Three price drivers: time, underlying, volatility | A B C |
| 5 | More time → more premium | A B C D |
| 6 | Closer to the money → more premium | A B C D |
| 7 | Higher IV → more premium (all strikes, both sides) | A B C |
| 8 | No obligation to hold to expiration; close any time | A B C D |
| 9 | **Time decay is non-linear and accelerates into expiry** | A B C |
| 10 | Long-option break-even = strike ± premium paid | A C D |

**Fact 9 is the most load-bearing.** Two sources with *opposite* strategies build
their timing around it independently — A avoids the steep part of the curve by
entering at 30–60 DTE, B compensates for it by cutting size Thursday/Friday. When
opponents agree on a mechanism, the mechanism is probably real.

---

## Tier 2 — Candidate rules with multi-source support

**Nothing here is adopted. Everything here is queued for backtest.**

### R1 — Assignment-willingness gate ★ strongest in corpus
> Never sell a put unless you would be content to own the stock at that strike.
> Never write a covered call unless you'd be content to sell at that strike.

**Sources: C, D** — two fully independent presenters, different audiences, no
shared lineage. The only rule so far with real convergence.

**Why it holds up:** it converts assignment from a failure into a planned branch.
Both outcomes are pre-accepted, so it removes the discretionary panic decision.
It is also the one rule in the corpus that *reduces* the tail rather than hiding
it.

**Agent form:** hard precondition on every short-put and covered-call entry —
underlying must already pass an independent "would hold" test at the strike.

### R2 — Own the collateral before selling against it
> Covered calls only against 100-share lots actually held. Never write more
> contracts than shares held ÷ 100. Cash-secured puts require cash for assignment.

**Sources: C, D.** Mechanically enforced by brokers, but explicit as discipline —
D declines a third contract he can't cover.

### R3 — Strike selection by probability band
> Sell in roughly the 65–85% probability-OTM range (~15–35 delta).

**Sources: A (65–85% explicit), D (~83% via broker UI).** Independent derivation
— A uses delta, D uses a "chance of profit" display.

⚠️ **Both sources select on win probability and neither ever mentions the size of
the loss.** Treat R3 as an observed convention, not a validated edge. See the
Standing Correction below.

### R4 — Size and timing must respect the decay curve
> Exposure should shrink as expiry approaches, because identical underlying moves
> produce progressively larger premium swings.

**Sources: A, B** — arrived at from opposite directions. A's answer is to enter at
30–60 DTE and avoid the steep zone; B's is to trade the steep zone but cut size
(a $1,000 Monday position → $500–750 by Friday; stop cost rises from 10–15% of
premium early week to 20–30% late).

**The mechanism is agreed. The prescription is not.** Encode the mechanism.

### R5 — Treat 0DTE as out of scope ⛔ hard constraint
> The agent does not trade 0DTE or same-week expiries until it has a validated
> edge and a proven loss distribution at longer horizons.

**Sources: E (evidence), B (advocacy, rejected).** Not a majority rule — a risk
limit, imposed because the only disinterested source in the corpus reports the
loss side and it is severe.

**Basis:** the trader profiled by WSJ ran a largest-day loss of ~$122k against a
largest-day gain of ~$14k — the bad day is ~8.7× the good day — and lost ~$65k
(20–30% of capital) in his first year. 0DTE is Tier-1 Fact 9 at its limit: decay
and gamma are at their most violent, so position outcomes are decided by minutes.
B treats this as the edge; E reports what it does to the people trading it.

**Agent form:** minimum-DTE floor as a hard precondition, not a tunable parameter.

---

## Tier 3 — Single-source, operationally valuable

Unconfirmed, but concrete and testable. Most come from B, which is the only source
that discusses execution at all.

| Rule | Source | Note |
|---|---|---|
| **Check open interest before choosing a strike.** If your intended size is a large fraction of OI, expect poor fills — worst exactly when the trade is working. | B | Best original content in the corpus. Directly actionable for an automated agent. |
| **Whitelist tickers with known liquidity** and trade them repeatedly. | B | SPY/SPX/QQQ named as unconstrained. |
| **Limit orders only, never market.** | C | Compounds with the OI rule. |
| **Stops on the underlying's price level, not on premium.** A premium stop can fire from decay alone while the underlying hasn't moved against you. | B | Real insight. Cost: manual management. |
| **Scale out in tranches (~30/20/30), hold a runner; no fixed price targets.** | B | Discretionary; hard to encode as stated. |
| **Chart confirmation required** — never act on options flow or IV signals alone. | B | Flow is ambiguous: hedges look like bets. |
| **Short-dated premium streams carry reinvestment risk** — a 6-month call locks a known credit; three 2-month rolls don't. | C | Only source to raise it. |
| **"No trade" is a valid outcome.** Some periods offer no acceptable premium. | C | Important for an always-on agent. |
| **Rich premium is a priced warning, not free money.** | — | *Our* inference from C's SIRI example, not stated by any source. See below. |

---

## Tier 4 — Contested (do not encode either side)

| Question | Position |
|---|---|
| **Buy or sell premium?** | A, C, D lean sell; B buys for leverage. But A, C and D are *not* the same trade — A sells defined-risk spreads for theta, C and D sell collateralized premium against assets they hold. Do not treat that as a 3-to-1 vote. |
| **Is theta an enemy or a cost?** | A: fighting decay is structurally losing. B: "theta is not the problem, it's you" — manageable with skill. Flatly opposed. |
| **What DTE?** | A: 30–60. B: 0DTE to weekly. C, D: 1–6 months. No overlap at all. |
| **Stop losses?** | B: mandatory, rejects "size for zero." A, C, D: never mention stops. A silence this loud across three sources is itself a finding. |

---

## Rejected claims — do not propagate

| Claim | Source | Why rejected |
|---|---|---|
| "Sellers have two-out-of-three odds (up/flat/down)" | B | Logical error. The three outcomes aren't equiprobable and the payoffs are wildly asymmetric. |
| "You cannot lose money selling the call option" / premium is guaranteed | C | A covered call is one position, not two. The position can lose badly. |
| Annualized single-outcome returns (28%, 46.8%, 66%, 85%) | C | Annualizes a best case as if it repeated 12×, ignoring assignment, the left tail, and C's own admission that some periods offer no trade. |
| "IV is more predictable than stock prices" | A (both videos) | The load-bearing claim of the entire premium-selling thesis — asserted twice, evidenced never, and deferred to paid material. |
| "Further-dated contracts are less risky" | D | Too loose. Directionally defensible for buyers only; false for sellers. |
| Credential-by-outlier ($2.5k→$106k; $16k→$1.2M) | B, D | Single unaudited trades / peak-bull-market results. D's is worse: the strategies taught are capped-return and *cannot* produce 75× in two years. |

---

## ⚠️ Standing correction — the corpus-wide blind spot

**Across the four commercial sources and five instructional videos, not one
discusses expectancy, sample size, or loss magnitude alongside win rate.** Every strike-selection method
presented — A's 65–85% probability OTM, D's 83% "chance of profit", B's directional
conviction, C's annualized yields — optimizes the frequency of winning and is
silent on the size of losing.

The corpus refutes itself on this point:

- **Video 01** shows five live short-option trades. Four won. The basket **lost
  money**. The presenter states this and moves on without drawing the conclusion.
- **Video 04's** SIRI cash-secured put pays 7.1% in 22 days — an ~85% annualized
  headline. That premium is large *because* implied volatility was large, i.e.
  the market was pricing serious downside in that specific name. The video sells
  the yield and never reads the warning inside it.
- **Video 06** is the only source that reports a loss distribution, and it is
  lopsided: worst day ~8.7× best day, first-year drawdown 20–30% of capital. It
  states outright that the odds generally run against these traders. The one
  source with nothing to sell is the one that shows the tail.

**Consequence for DELTAX:** high probability of profit is not an edge. Every rule
promoted out of Tier 2 or 3 must be validated on **expectancy**, never on hit
rate. This is precisely how the TSLA playbook failed validation, and the entire
corpus is built on the assumption that killed it.

### The gate, in computable form

> **E = ( 1 + W / L ) × P − 1**
> W = average win · L = average loss · P = win rate · **Trade only if E > 0.**

Algebraically identical to `P × (W/L) − (1 − P)` — expectancy expressed in
R-multiples, i.e. units of average loss. Verified correct.

Worked: average win $200, average loss $170, win rate 55% →
(1 + 1.176) × 0.55 − 1 = **+0.20**. Positive, so the system pays.

Sky View's on-camera basket — four winners out of five, still net negative —
fails this in one line. That is the whole point of the gate.

**Related payoff-ratio arithmetic**, which follows from the same algebra:

| Reward : risk | Breakeven win rate |
|---|---|
| 1 : 2 | 66% |
| 1 : 1 | 50% |
| **2 : 1** | **33%** |

Raising the payoff ratio lowers the accuracy the system needs — and accuracy is
the hardest variable to control. Hence: define the target as a multiple of
defined risk before entry, and size every position from the stop
(`quantity = risk budget ÷ (entry − stop)`) so that every loss normalizes to −1R
and expectancy stays computable across trades of different sizes.

*(Provenance: this framework did not come from the options sources — none of them
measured expectancy. It is retained here as the promotion gate because it is
verifiable arithmetic rather than anyone's opinion.)*

---

## Backtest queue

Ordered by (multi-source support × testability):

1. **R1 assignment-willingness gate** — needs a defensible "would hold" signal;
   test whether gating short puts on it beats ungated short puts on expectancy.
2. **R3 probability band** — sweep 10–40 delta on short strikes, measure
   expectancy and max drawdown, not win rate. Expect the win rate to rise and
   expectancy to fall as you move further OTM. **This is the corpus's central
   claim and the one most likely to break.**
3. **R4 decay-curve sizing** — test whether DTE-scaled position sizing improves
   risk-adjusted return versus flat sizing.
4. **A's 30–60 DTE window** vs alternatives, on expectancy.
5. **Open-interest liquidity floor** — model fill quality as a function of
   size÷OI; likely a meaningful cost drag the videos entirely ignore.
6. **Premium-yield vs IV sanity check** — does an unusually rich premium predict
   worse forward outcomes? Tests our SIRI inference directly.

**Data available:** Alpaca paper account `PA3ID1B9L6BP`, options level 3.
Everything in tiers 2–4 is unvalidated until it clears this queue.

---

## Source-quality note

Video 06 closes with its profiled trader planning to launch an options course.
That is the pipeline that produced most of this corpus: volatile P&L → educator →
content selected for what recruits students, not what survives the market. Weight
sources by what they stand to gain, and let the backtest settle everything else.

---

## AURA convergence (source M — Matin, 2026-08-29)

AURA's planned options module (v0.6.0) is **not built** — but its ten selection
criteria, drafted independently, map almost one-to-one onto the gates we shipped:

| AURA criterion | DELTAX gate | Status |
|---|---|---|
| Defined risk — known max loss before authorization | `gate_defined_risk` | ✅ shipped |
| Liquidity — volume / OI / tradability | `gate_liquidity` | ✅ shipped |
| DTE window | `gate_dte` (7–21) | ✅ shipped |
| Premium / risk | `gate_credit` + `gate_reward_risk` | ✅ shipped |
| Event risk — stand down around catalysts | `gate_no_earnings_before_expiry` + `gate_tradeable` | ✅ shipped |
| Position limits — portfolio & underlying concentration | `gate_position_size` + `gate_portfolio_risk` | ✅ shipped (per-underlying cap still to add) |
| **Bid/ask quality — tight spreads, acceptable slippage** | — | ❌ **gap: add a max-spread gate** |
| **IV / IV rank — regime relative to history** | — | ❌ **gap: add IV-rank input** |
| Delta — target exposure range | — | partially via R3 band; not a gate yet |
| Exit feasibility — predefined exits | flatten routine planned | 🔶 build |

Independent triple convergence on "defined-risk only, AI proposes / deterministic
code disposes" — ours, Elsa's, Matin's — is now the headline of the write-up.

**Adopted from AURA's research protocol** for the options backtest queue:
survivorship/expired-contract handling, historical bid/ask realism, entry/exit
timestamps, assignment and corporate actions, event-aware holdouts,
**multiple-testing correction**, and the pre-committed acceptance bar
(OOS PF > 1.10 AND >50% folds positive) layered on top of S0's E > 0.

**Honesty note carried from his AVOID list:** our 7–21 DTE band is an
operational constraint of the competition window — never to be cited as
researched edge.
