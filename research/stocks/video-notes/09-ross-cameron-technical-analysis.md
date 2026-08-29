# Video 09 — The ONLY Technical Analysis Guide You'll Ever Need

**Source:** Ross Cameron / Warrior Trading — https://youtu.be/BUCPPCXOHbs
**Length:** 1:41:30 · **Uploaded:** 2025-01-09 · **Views:** ~1,009,479
**Viewpoint H** · Captions pulled 2026-08-29

---

## ✅ The only genuine US equities source in the corpus

Small-cap momentum day trading on US listings — real floats, real share counts,
US brokers. The first material whose instrument layer maps onto the Alpaca
account, and directly usable for **underlying selection** before an options
overlay.

---

## The five selection criteria ★ most encodable content anywhere in the corpus

His thesis: technical analysis only works on instruments with a genuine
supply/demand imbalance. **Screen first, chart second.**

| # | Filter | Threshold | Rationale |
|---|---|---|---|
| 1 | Float (fixed supply) | **< 10M shares**, lower better | Demand has nowhere to go but price |
| 2 | Intraday move | **≥ +30%** | Demand already active — observed, not predicted |
| 3 | Catalyst | **Breaking news** | The cause; no catalyst, no sustained move |
| 4 | Price band | **$3 – $20** | Below is delisting risk; above, float edge fades |
| 5 | Relative volume | **≥ 5× normal** | Unusual participation, not routine trade |

**Causal order matters:** news → price squeezes → relative volume expands → the
volume itself attracts more participants → large move. News without price response
isn't tradeable; price without news isn't either.

Every filter is a number available from market data — the only rule set in the
entire corpus implementable as a scanner without interpretation. He states it came
from mining his own trade history, which is the right method even though the data
isn't shown.

Background he supplies: repeated dilution and reverse splits shrink floats over
time, which manufactures the low-float candidates and makes them squeeze targets.

## Risk framework

**Minimum 2:1 reward-to-risk.** His breakeven arithmetic — verified correct:

| Reward : risk | Breakeven win rate |
|---|---|
| 1 : 2 | 66% |
| 1 : 1 | 50% |
| **2 : 1** | **33%** |

Raising the payoff ratio lowers the accuracy required, and accuracy is the hardest
variable to control. Names accuracy, payoff ratio and consistency as the three
components of profitability — the same expectancy structure as videos 07 and 08,
from a **third** independent source.

Implemented as `gate_reward_risk()` in `deltax/gates.py`.

## Phased scaling, gated on metrics

1. Simulator, experience only — expect to lose; the goal is screen time.
2. Simulator, rules enforced — promotion requires **10 days holding target
   metrics.**
3. Real money at minimum size — a $5/day goal, one share if necessary.
4. Scale the goal: $5 → 10 → 20 → 40 → 80 → 160…

**Scale the size, never loosen the rules.** Promotion is earned by demonstrated
metrics, not elapsed time. Directly implementable as a deployment policy.

## The two feedback loops

**Negative:** real money → loss → emotional pain → emotion-seeking → reckless
"make it back" trading → larger losses → spiral.

**Positive:** A+ setups only → in a simulator → losses carry no emotional charge →
track record → confidence → fund real money with evidence to point at during the
inevitable drawdown.

Names the two causes of failure: no strategy at all, or a strategy without the
discipline to follow it.

**For DELTAX this maps unusually well.** An automated agent is immune to the
emotional loop by construction. Our version of discipline is simply not building a
discretionary override — which is exactly why `deltax/gates.py` contains no
model-overridable path.

## Technical content

Roughly the first hour: candlestick anatomy, wicks, multi-candle patterns,
candle-over-candle continuation, pullback patterns, moving averages, S/R, daily vs
intraday. Competently taught, and he stresses that **candlestick patterns are only
meaningful on the right instrument** — which is what makes the five criteria the
load-bearing part, not the patterns.

## Flags

- **⚠️ Verify the regulatory history before weighting any earnings claim.** Warrior
  Trading and Ross Cameron reached an FTC settlement in 2022 over allegations about
  earnings representations (reported ~$3M). This is from memory — **confirm at
  ftc.gov before relying on it.** It bears on the "Verified Earnings" chapter and
  the profit figures shown on screen. Treat all outcome claims as marketing.
- **A funnel for a paid programme** — the scanners that find these setups are the
  product.
- **He disclaims repeatedly and unprompted:** trading is risky, results aren't
  typical, no guarantee. More disclosure than any other commercial source here.
- **Survivorship** in the cited student example; no denominator.
- **Capacity-constrained by design.** Sub-10M-float stocks up 30% intraday are
  thin. Slippage at size is a real cost the video never quantifies and our
  backtest must.
