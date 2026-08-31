# Decision Ledger

Every consequential decision, scored honestly. A decision is **BAD** if it cost
money, time, or credibility — regardless of whether the reasoning sounded good
at the time. Reasoning that sounds good and loses money is still a bad decision.

Scored: 🟢 good · 🟡 mixed · 🔴 bad

---

## 🔴 D-07 · Opened a Sep 18 expiry in a contest judged Sep 4
**31 Aug 14:34 ET · cost: ~$300 of unearnable profit · mine**

Sold a UNH 380/370 put spread expiring **18 Sep**. Judging is **4 Sep**.

**What I checked:** all 13 gates, IV/RV 1.29, a 2.93% buffer, a 9.4% breach
probability, earnings clear to 27 Oct. All good. I even flagged that the Sep 18
expiry sat across the 14 Sep ex-dividend and noted the buffer cost.

**What I did not check:** whether the expiry finished before the contest did.

A credit spread pays when it decays, and decay lands in its final days. At
judging only **22% of it has accrued** — the judges see roughly −$130 on a
position built to earn +$814. The trade is not wrong; it is being scored before
it can pay.

**Why it happened.** I wrote **E17 — "measure the hold period you can actually
execute" — at 03:40 that same morning**, after finding the identical flaw in our
backtest. Eleven hours later I violated it. The rule lived in a markdown file
and nothing in the code compared an expiry to the contest end.
`choose_expiry` takes the nearest expiry clearing liquidity; Sep 11 failed
liquidity and it fell through to Sep 18 unchallenged.

**How to avoid it.** A constraint that can end the run belongs in a gate with a
test, never in prose. Now enforced twice: `gate_contest_window` refuses any
expiry past 4 Sep, and `manage.past_contest_deadline` flattens the book at 10:00
ET that day. See **E37**.

---

## 🟡 D-08 · Let the agent complete the condor without telling you
**31 Aug 15:10 ET · the trade was right, the communication was not · mine**

At 15:10 the scheduled agent sold a UNH 400/410 call spread on its own, turning
the put spread into a full iron condor. You found out from a broker screen.

**The trade itself was an improvement.** Credit went $418 → $814 while max loss
stayed ~$1,604, because only one side of a condor can be breached at expiry.
Nearly double the premium for the same risk.

**The failure was mine and it was a communication failure.** When we agreed
"UNH only", I pictured one spread. `run.py` has nominated **both sides** of every
name since the first commit — that is what an iron condor is. The call side had
been blocked by `liquidity` all morning and cleared at 15:10.

I described the position to you as a put spread and never said a call spread
would follow the moment liquidity allowed. That is the difference between an
autonomous agent and a surprising one.

**How to avoid it.** Before any live session, state what the agent *may* do, not
only what it is about to do. "UNH, both sides, up to 2 spreads" is a sentence
that would have prevented this entirely.

---

## 🟢 D-01 · Build the decision logger first
**29 Aug · the best call of the project**

Recorder before decider. 478 logged decisions with reasons are what later caught
E29, E30, E34 and E36 — none of which any test found.

**Attribution:** the ledger is specified in Matin's AURA architecture (`.17
Ledger`, "auditable record before any order"), integrated at commit 9 and built
at commit 14. The sequencing argument and the implementation are mine; **the
concept is his** and I presented it as my recommendation without saying so.

---

## 🟢 D-04 · Refused to trade all Monday morning
**31 Aug 09:30–13:00 · zero trades, correct**

The gates declined every candidate for four hours and it looked like failure. It
was not: the market was paying **$0.54** for a spread our floor required **$1.11**
for. Lowering the floor to trade would have meant knowingly taking
negative-expectancy positions.

---

## 🔴 D-05 · Backtested against a credit the market never pays
**29–31 Aug · invalidated every performance number we had · mine**

`credit = 1.15 × delta × width` was assumed, never checked against a quote. Real
market credit is roughly **half** that. The +0.107 expectancy, the three-week
replay, the forecast distribution — all computed at a price that does not exist,
and negative at real prices.

**How to avoid it.** Any backtest input that is *assumed* rather than *observed*
must be checked against one live quote before a conclusion is drawn. See **E34**.

---

## 🟢 D-06 · Rebuilt on measured prices mid-session
**31 Aug 13:00–14:00**

Re-derived the credit floor from live chains, re-ran walk-forward with Bonferroni
correction, adopted only the 5 of 180 configurations that survived. First thing
in the project validated at prices we can actually be filled at.

---

## 🟡 D-02 · Wrote 39 rules; enforced roughly half in code
**29–31 Aug**

The corpus is the project's differentiator and it also created a false sense of
safety. E17, E30 and E5 were all written down and all violated, because writing
a rule felt like solving the problem. **Documentation records what you decided;
only code enforces it.**

---

## 🔴 D-03 · Shipped an ETF-only universe half of which could never trade
**29–31 Aug**

`min_credit` needs a $3.26 strike width; XLU at $42 trades $1-wide strikes
yielding $0.23. More than half the universe was **mathematically incapable** of
clearing our own gate, on any day, at any price. Nobody checked the interaction
between two constants until the agent had refused everything for a full session.
