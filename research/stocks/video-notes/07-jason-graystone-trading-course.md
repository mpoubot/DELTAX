# Video 07 — Trading for Beginners Part 1: Full Trading Course Tutorial

**Source:** Jason Graystone — https://youtu.be/_YVQN6_nkfs
**Length:** 2:26:39 · **Uploaded:** 2023-01-15 · **Views:** ~9,569,371
**Viewpoint F** · Captions pulled 2026-08-29

---

## ⚠️ It's a forex/CFD course

Every worked example is a currency pair. Arithmetic is in pips and lots, sizing
assumes broker leverage and margin, the recommended broker is a CFD provider
(affiliate link). None of that instrument layer applies to a US options account.

**The process layer does, completely** — and it's the best in the whole corpus.

---

## The expectancy formula ★ the most valuable item in any bucket

> **E = ( 1 + W / L ) × P − 1**
> W = average win · L = average loss · P = win rate · **E > 0 to trade**

Worked: W=$200, L=$170, P=55% → (1 + 1.176) × 0.55 − 1 = **+0.20**.

**Verified correct.** Algebraically identical to `P × (W/L) − (1 − P)` —
expectancy in R-multiples, i.e. units of average loss.

Why it matters: it makes win rate and loss size inseparable. The options bucket's
fatal flaw was five sources selecting on probability of profit while ignoring the
tail. Sky View's own on-camera basket — four winners out of five, still net
negative — fails this in one line.

Now implemented as `gate_expectancy()` in `deltax/gates.py`.

## Risk and position sizing

1. **Risk a fixed 1% of account per trade.**
2. **Size from the stop:** risk budget ÷ stop distance. For options:
   risk budget ÷ max loss per contract.
3. **Target as a multiple of risk.** Stop placement first; size and target follow.

Implemented as `size_from_risk()` and `gate_position_size()`.

## Backtesting method

Log every hypothetical trade to a spreadsheet, one instrument at a time. Columns:
entry date/time, instrument, timeframe, system, trigger, market condition, phase,
**S/R touch count**, indicator readings, price deceleration, candle pattern,
entry, stop, target(s), close date/time, exit reason, P/L.

**The condition columns are the point** — post-hoc filtering. His example:
discovering every winner had ≥5 support/resistance touches, which then becomes an
entry filter. The log is raw material for finding which conditions carry the edge,
not a diary.

**Extract before going live:** longest losing streak, longest drawdown, largest
single loss, largest gain. For a human these prevent abandoning a system
mid-drawdown. **For DELTAX they are the kill-switch thresholds** — a live drawdown
exceeding the backtested worst case means the edge changed, not that we persevere.

## Setup selection — six components

Market condition (bullish / bearish / ranging / **choppy**) · market phase (run vs
pullback) · horizontal S/R · angular S/R · price action and candlesticks ·
indicators (Fibonacci retracements as confluence, not signals).

Rules that fall out:
- **Stand aside in choppy markets** — no edge in indecisive, structure-breaking
  conditions.
- **Enter on pullbacks, never mid-run.** Buying an extended move is the classic
  beginner error.
- **Score confluence cumulatively.** Count touches, note coincidences.
- **Don't chase exact tops and bottoms.** A good price, not the best price.

## Process discipline

- **Timeframe follows attention cadence.** Once daily → daily charts. Edges are
  small; missed trades erase weeks.
- **Demo before live**, to separate execution errors from strategy errors.
- **Don't trade a system you can't modify.** The same system handed to two people
  produces two outcomes.
- **Business framing:** wins are revenue; losses, spreads, commissions and
  platform fees are overheads. **Backtests must model fees and slippage.**
- Income is sporadic. Anyone promising a fixed weekly return is wrong.

## Flags

- Forex/CFD framing with an affiliate broker relationship.
- **No performance evidence** — and he says outright the demo strategy he builds on
  camera is *not* one he believes is profitable; it exists to teach the process.
  **Unusually honest**, which makes him more trustworthy than the options sources.
- **Backtesting is manual and discretionary.** Eyeballing charts in hindsight
  invites selection bias. Ours must be programmatic and out-of-sample.
- "Resistance becomes support" asserted with a hedge, entirely unquantified.
