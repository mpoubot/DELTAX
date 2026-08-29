# DELTAX — design response to the short-window problem

**The constraint:** P&L is a judging criterion, measured over ~4.5 trading
sessions (Mon 31 Aug → Fri 4 Sep, 11:00 AM EDT).

**The finding from our own research:** results over a window that short are noise.
Six videos, five viewpoints, and the only disinterested source in the corpus all
point the same way — a strategy can win most of its trades and still be defined by
the ones it loses. Optimizing for a 4-day number means taking concentrated risk
and calling the outcome skill.

**The resolution:** stop trying to control the number. Control the *distribution*
it comes from, and bring evidence that stands independently of it.

---

## 1. Make catastrophic loss structurally impossible, not merely unlikely

**Defined-risk structures only.** Vertical spreads and iron condors — every
position's maximum loss is known at entry, before the order is submitted. No naked
short options (undefined risk, and the corpus's Tier-4 contested question we
declined to answer).

**Two hard caps:**

| Cap | Value | Meaning |
|---|---|---|
| Per-position max loss | **1% of equity** ($1,000) | Sized from the defined max loss of the spread, not from conviction |
| Portfolio concurrent max loss | **5% of equity** ($5,000) | If *every* open position went to maximum loss simultaneously, the account ends at $95,000 |

That second cap is the point. The worst possible outcome of the entire competition
window is a 5% drawdown — and we can state that as a fact at submission time, not
as a hope. A blow-up isn't defended against; it's arithmetically unavailable.

## 2. Refuse loudly, and log the refusal

The agent emits a **decision record for every evaluation**, not just for trades.
Each record names the gates checked and, on a reject, the specific gate that
failed and its value.

This inverts the deliverable. "The agent evaluated 84 candidates, refused 78, and
explains every refusal" is a stronger demonstration of engineering than a P&L
figure, and it's the thing no amount of luck can fake. It directly serves
**Technology Implementation** and **Presentation**, and it's the honest expression
of what the corpus actually taught us.

## 3. Pre-register the strategy before the window opens

Commit the complete rule set — gates, thresholds, sizing, expected expectancy —
to git with a timestamp **before Monday's open**. Then report actual against
predicted.

This is the move that converts a noisy result into a legitimate finding *in either
direction*. Profitable: we can say whether it fell within the predicted range.
Unprofitable: same, and the prediction still holds. Without pre-registration,
any outcome can be narrated after the fact — which is precisely what every
commercial source in the corpus does.

## 4. Put the evidence in the backtest, not the window

4.5 sessions cannot establish an edge, so the edge claim has to rest on history.
Backtest the rule set over a long historical period using Alpaca's data, compute
`E = (1 + W/L) × P − 1`, and report the live window as **one sample drawn from
that distribution** rather than as proof of anything.

This is the strongest possible answer to the P&L criterion: we argue *expected*
P&L with real evidence, and present *realized* P&L with its uncertainty attached.

## 5. Report P&L with its error bars

Never report a bare dollar figure. Report:

- Number of trades (n will be small — say so)
- Win rate, average win, average loss, all in R-multiples
- Computed expectancy for the window
- The backtested expectancy for comparison
- An explicit statement that n is too small for the live figure to be significant

A team that reports its own confidence interval is doing something none of the
sources in our corpus did.

## 6. Two operational details that materially change the number

**Expiry selection: roughly 7–21 DTE.** Our rule R5 bans 0DTE outright — the WSJ
source reports a trader whose worst day was ~8.7× his best, and 0DTE is the decay
curve at its most violent. But 30–60 DTE (Sky View's preference) won't resolve
inside the window and would leave us reporting unrealized mark-to-market. The
7–21 band clears the gamma danger zone while letting theta actually accrue within
four sessions.

**Flatten everything before Friday 11:00 AM.** Close all positions before the
deadline so the judged P&L is *realized*, not a mark. This is a deliberate choice
worth stating in the write-up — it means the number we report is the number we
actually made.

---

## The honest bet

This approach probably does **not** produce the highest P&L in the field. If
someone takes concentrated 0DTE risk and gets lucky, they beat us on criterion one.

We are betting that four of five criteria — Technology, Creativity, Presentation,
Social — plus a defensible, pre-registered, honestly-reported result beats one
lucky number attached to a strategy that can't explain itself. Given that the
research corpus's central finding is *exactly* that people mistake luck for edge,
building an agent that refuses to make that mistake is also the most coherent
story we could tell.

That's a bet, not a certainty. It's the one worth taking with $100,000 of paper
money and five days.

---

## Build order

1. **Risk gate module** — the caps, defined-risk validation, expectancy check.
   Pure functions, unit-tested. This is the product.
2. **Decision logger** — structured JSON per evaluation, trade or refusal.
3. **Candidate screen** — option chain pull via `alpaca option contracts`,
   filtered to liquid underlyings and the 7–21 DTE band.
4. **Backtest harness** — historical expectancy for the pre-registration.
5. **Execution** — `alpaca order submit --order-class mleg --legs` for spreads.
6. **Pre-registration commit** — before Monday 09:30 ET.
7. **Flatten routine** — scheduled before Friday 11:00 ET.
