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

> Credit structures: **credit ≥ 30% of width**. Debit structures: **reward:risk
> ≥ 2.5:1**. One floor applied to both silently refuses an entire structure
> class.

Discovered as a live bug: our original 2:1 gate would have refused *every* OTM
credit spread on Monday — a credit spread's payoff IS its probability, so it
can never show 2:1. Generalization: **before going live, run every structure
the agent will trade through the gates and confirm at least one realistic
candidate of each class can pass.** A gate that can never pass is a ban you
didn't mean to write.

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
