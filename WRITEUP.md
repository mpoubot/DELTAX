# DELTAX — an options agent that refuses

**Alpaca AI Trading Agents Hackathon · Paper account `PA397N6FXXIE`**
Live board: https://pautax007.github.io/DELTAX/ · MIT · 28 modules · 789 tests

---

## The claim

An autonomous agent is only as good as the trades it *declines*. DELTAX screened
**1,000 option structures**, approved **9**, and wrote all **2,851** decisions to a
hash-chained ledger. A 99% refusal rate is not timidity — every refusal names the
gate that produced it and the number that failed, so the agent can be audited
rather than believed.

We are **−0.87%** at the time of writing. The more interesting number is that we
can tell you precisely why, in one line: we were selling volatility below what the
underlying was delivering, and nothing in the system was checking.

---

## 1. AI logic

Three strategies; only one places orders.

**Options income (live).** Sell defined-risk vertical credit spreads on liquid
ETFs. Short strike inside a 0.15–0.35 delta band, long leg one width out, so
maximum loss is bounded before the order is built. Entry is not a point guess:
`search_vertical` enumerates every eligible (short, long) pair in the chain and
maximises `(credit − round-trip cost) / width` — the net edge after crossing both
books. Replacing a single delta-anchored guess with this search took the approval
rate from 0.3% to 100% on the same chains, without relaxing a single gate.

**Sector rotation (advisory).** Eleven GICS sectors ranked by relative strength
against SPY, with a regime layer (SPY vs GLD/TLT/BIL). It ranks and logs; it never
orders. The source framework says rotation unfolds over weeks, so wiring it to a
five-minute loop would trade against the signal's own design.

**Catalyst (retired 2 Sep).** A supply-shock debit spread. We backtested it on 46
expiries of real OPRA prices: −9% of debit per trade, P(mean<0) = 74.5%, max
drawdown −89.9%. Its one positive regime bucket did not survive permutation
testing (p = 0.185; 0.738 after Bonferroni across four buckets). We turned it off
and left the research next to the flag that disables it.

**The edge we were missing.** Selling a credit spread *is* selling volatility, so
the seller's only edge is implied vol above realised. Measured across the universe
on 2 September:

| DIA | SPY | FXI | IWM | QQQ | HYG | EEM | **SMH** |
|---|---|---|---|---|---|---|---|
| 1.64 | 1.40 | 1.24 | 1.18 | 1.17 | 1.16 | 1.12 | **0.91** |

SMH was our largest concentration — six spreads, $5,507, 42% of committed risk —
and it was the one name where we were selling movement for *less than it cost*.
That is a mathematically losing trade no strike selection repairs. It is now a
gate, and SMH is out of the universe.

---

## 2. Risk gates

**Fifteen deterministic gates run on every candidate.** All of them evaluate — the
record shows the full picture, not the first failure. Every gate **fails closed**:
unreadable data is a refusal, never a skip.

Defined risk · position size (2% of equity) · portfolio risk (30% cap) · liquidity
(500 OI floor, ≤5% of a strike's open interest) · spread quality and round-trip
friction (≤35% of credit) · minimum credit · credit fraction against a measured
market surface · **variance premium (IV/RV ≥ 1.10)** · DTE band · time-stop
coherence · contest window · earnings blackout · quote sanity · listing freshness
· halt and corporate action.

Above them sit an entry freeze driven by eight live signals, a per-cycle single-
instance lock, and a deadline flatten. **Closing orders bypass every stand-down** —
a freeze that could block an exit would trap the book, which is the opposite of
safety.

**Exits are the strategy, not an afterthought.** A GTC buy-to-close at 50% of
credit rests from the moment of entry, so it fills whether or not the agent is
alive. A trailing take-profit arms at 25% captured and exits on a 15-point
give-back — loose on purpose, because our measured round-trip is 9–15% of credit
and a tight trail would fire on quote noise. Everything flattens at 10:00 ET on
judging day.

---

## 3. Alpaca infrastructure

Alpaca CLI throughout — `order submit --order-class mleg` for multi-leg spreads
with explicit `position_intent`, `position list`, `order list`, `data
multi-snapshots`, `data bars`, `option contracts`, `option chain`, `clock`,
`account portfolio`. One module can reach the broker; every other module is pure.

Order safety is layered: dry-run by default, a second environment switch, a
pre-flight account-number and paper-endpoint check, and a rule-3 guard at
`build_mleg_args` — the one function every order-building path passes through — so
no non-option leg can ever be submitted. A healthy cycle is 20 seconds; the lock
exists because a degraded endpoint can stretch one past 40 minutes while cron
keeps firing, and two cycles reconciling before either submits would both size
against the same free budget.

Everything is scheduled: a five-minute trading cycle, a fifteen-minute freeze
signal check, pre-market intelligence, a three-minute dashboard publish, and the
judging flatten.

---

## What we would tell another team

**Four bugs found in the last 48 hours, each of which looked green:**

- A variable named `now` was reassigned to a spread's mark price. Every later
  `now − bar_time` raised `TypeError`, was swallowed by a handler meant for bad
  data, and silently disabled the delisting gate for an entire session — while the
  ledger reported healthy ETFs as "likely delisted."
- A risk formula multiplied its second term by zero, so the portfolio cap measured
  premium received instead of maximum loss. **The existing test asserted the bug.**
- A friction gate was fully implemented, fully unit-tested, and dead: nothing ever
  computed its input.
- The contest deadline close — the control the entire result depends on — had no
  test at all. Deleting it broke nothing.

The last two were found by **mutation testing**: corrupt a rule on purpose and see
whether the suite notices. We ran 25 mutations across the risk and exit paths. The
survivors were the rules nothing was really checking.

Reading code did not find these. Comparing the system's beliefs against the
broker's ground truth did.

---

*Paper trading only. No real capital. The ledger is append-only and hash-chained;
every number here is reproducible from `logs/decisions-*.jsonl`.*
