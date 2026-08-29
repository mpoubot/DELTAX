# DELTAX — Golden Rules: STOCKS

## ⚠️ Authority

**This file is Alyrise, by Ilze Rosicka (Elsa).** It is the authoritative stock
strategy for DELTAX and supersedes the video-derived rules, which are retained
for reference only in [`video-derived-rules.md`](video-derived-rules.md).

**Scope: stocks only.** The spec states explicitly — *do not merge stock-specific
rules with crypto or options rules.* Nothing in this file applies to the options
engine.

Source: `Alyrise Stock Trading Engine – Integration Brief`, 14pp.
Author: Ilze Rosicka · https://www.linkedin.com/in/ilze-rosicka/

---

## 1. Architecture

Alyrise is the **stock engine** of a multi-asset robot. Separate engines for
stocks, crypto and options each emit **standardized trade intents**; a shared
layer handles risk checks, approval, execution, reconciliation, accounting,
notifications and reporting.

```
engines/stocks/   engines/crypto/   engines/options/
        └────────── shared: risk gate · approval · execution ·
                    reconciliation · ledger · alerts · dashboard · kill switch
```

Broker/exchange adapter is selected by `asset_class`. A US market closure stops
stock orders but must **not** halt a 24/7 crypto engine.

### The AI constraint

> Alyrise is primarily deterministic. An AI or LLM layer may analyse market
> information, generate research or propose opportunities, **but it must not
> change strategy thresholds, bypass risk controls or independently authorize
> orders.**

**This is the same architecture we arrived at independently** for the options
engine — `deltax/gates.py` contains no model-overridable path, and `DATA-FEEDS.md`
restricts news to a veto-only role. Two team members converging on this from
opposite ends is a strong signal it's correct, and it's worth saying so in the
hackathon write-up.

## 2. Execution cycle — every 5 minutes

1. Check Alpaca connection, account status, cash, market status
2. Reconcile broker orders, fills, positions
3. Update 5-minute prices, daily VWAP, intraday references
4. Determine broad market regime
5. Scan open positions for sell signals
6. Generate and execute eligible sell intents
7. Scan the universe for buy signals
8. Apply position, cooldown, universe and corporate-action filters
9. Select the deepest eligible drops
10. Allocate capital separately inside each strategy
11. Generate buy intents
12. Execute eligible orders
13. Reconcile fills again
14. Update valuation, logs, alerts, dashboard

> **The system must always create an auditable intent before submitting an order.**

Sells are processed **before** buys within each cycle.

## 3. The three strategies

| Parameter | CORE | ACTIVE | INTRADAY |
|---|---|---|---|
| Buy reference | 7-day rolling avg of daily VWAP | 20-day rolling avg of daily VWAP | Today's intraday VWAP |
| Normal buy threshold | −4.5% | −4.5% | −2.5% |
| Additional condition | none | none | `latest_price < previous_close` |
| Max buys per cycle | 3 | 3 | 10 |
| Take profit | **+12.0%** | **+6.5%** | **+2.0%** |
| Stop loss | **−30.5%** | **−30.0%** | **−3.5%** |
| Trailing activation | +8.0% | +5.0% | +1.2% |
| Trailing distance | 2.0% from peak | 2.0% from peak | 1.0% from peak |
| Max holding time | none | none | 24 hours |
| Stop-loss cooldown | 7 days | 7 days | 60 minutes |
| Post-sale cooldown | 3 hours | 3 hours | 3 hours |

All three are **dip-buying / mean-reversion**: buy a defined discount to a VWAP
reference, exit on a fixed target or a trailing stop.

## 4. Market-regime filter

Benchmarks: **SPY** (broad large-cap) · **QQQ** (Nasdaq/tech) · **IWM** (small-cap).

A benchmark is weak when `latest_price < intraday_vwap`. Count how many of the
three are weak; the required discount deepens accordingly.

| Weak benchmarks | CORE | ACTIVE | INTRADAY |
|---|---|---|---|
| 0 of 3 | −4.5% | −4.5% | −2.5% |
| 1 of 3 | −5.0% | −5.0% | −3.0% |
| 2 of 3 | −5.5% | −6.0% | −3.5% |
| 3 of 3 | −6.0% | −7.0% | −5.0% |

**Missing-data fallback** (conservative): CORE −6.0% · ACTIVE −7.0% · INTRADAY −3.5%

The filter never fully blocks CORE or ACTIVE — it **requires a progressively
deeper discount**. It distinguishes a company-specific decline from a broad-market
one. SPY, QQQ and IWM are filter instruments and must not become buy candidates
unless separately listed in the tradable universe.

*Future extension (not implemented): per-sector benchmarks XLK, XLF, XLE, XLV,
XLI, XLY, XLP, each stock assigned a sector, adjusting its threshold without
replacing the broad filter.*

## 5. Buy logic

```
CORE:      latest_price <= rolling_vwap_7d  * 0.955     (0.945 at 2/3 weak)
ACTIVE:    latest_price <= rolling_vwap_20d * 0.955     (0.94  at 2/3 weak)
INTRADAY:  latest_price <= intraday_vwap    * 0.975
           AND latest_price < previous_close
```

Substitute the regime-table multiplier when benchmarks are weak.

**Candidate selection:** CORE keeps up to 3, ACTIVE up to 3, INTRADAY up to 10.
Sorted by `drop_pct`, **deepest negative drop first.**

Universe files: `stocks.txt` (CORE, ACTIVE) · `stocks_intraday.txt` (INTRADAY).
INTRADAY reference data: `intraday_reference.csv` with fields `symbol`,
`intraday_vwap`, `previous_close`, `latest_price`, `market_date`, `updated_at`.

## 6. Position and eligibility filters

Reject a buy when any of these hold:

- symbol already has an open position **in the same strategy**
- symbol is still in cooldown
- symbol is not in that strategy's permitted universe
- symbol has no corresponding position-state record
- symbol is blocked for a split, corporate action or delisting risk
- the signal has expired
- the market is closed
- insufficient strategy capital
- the order would violate broker, PDT or other risk rules

**Position identity is `asset_class + strategy + symbol`.** The same symbol may be
held simultaneously by CORE, ACTIVE and INTRADAY as **separate virtual positions**,
even though Alpaca reports one combined broker quantity.

## 7. Capital pools

Each strategy has an **isolated virtual pool**: `entry_unit`, `entry_pool_balance`,
`entry_debt_balance`, `free_cash_balance`, `ever_bought_symbols`.

> Cash must not move between stock, crypto and options engines unless an explicit
> portfolio-level allocation process authorizes the transfer.

Split of stock capital: **CORE 70% / ACTIVE 30%.** INTRADAY has its own pool.

Default entry units: **CORE $70 · ACTIVE $30 · INTRADAY $30.**
INTRADAY starting `entry_pool_balance` = **$2,850**.

**First purchase:** `order notional = entry_unit`; `entry_pool_balance -= entry_unit`;
symbol added permanently to `ever_bought_symbols`.

**Repeat purchase** (previously owned by this strategy, position since closed):
uses `free_cash_balance` first. When several repeat-buy candidates compete, free
cash is allocated **in proportion to the depth of their declines** — a larger drop
gets a larger allocation. Never add to an already-open position in the same
strategy.

**Entry-pool borrowing:** if a repeat-buy exists but free cash is below minimum
order size, borrow one entry unit — `entry_pool_balance -= entry_unit`,
`entry_debt_balance += entry_unit`. Future sell proceeds repay debt before
becoming usable free cash.

**INTRADAY growth rule** — when `free_cash_balance >= 100`:
```
entry_unit          += 1
entry_pool_balance  += 95
free_cash_balance   -= 95
```
Growth stays inside INTRADAY. **INTRADAY profit must not fund CORE, ACTIVE,
crypto or options.**

## 8. Sell logic

Every open position is checked every 5-minute cycle. Priority order:

1. **Stop loss**
2. **Trailing stop**
3. **Take profit**
4. **Maximum holding time**

The highest observed price is stored **per position**. Once a trailing stop is
activated it **stays armed**, even if profit later falls below the activation
percentage.

**INTRADAY 24-hour max-hold rule:**
```
if pnl_pct >= 0.07:  create_max_hold_sell_intent()
else:                do_not_sell_because_of_time()
```
Below 0.07% profit the position stays open; take profit, trailing stop and stop
loss continue working normally.

## 9. Trade intents and execution safety

Buy and sell scans **only generate intents**. A shared execution layer decides
whether an order may be submitted. Every intent carries at least:

`asset_class · strategy · symbol · side · order_type · notional_usd · quantity ·
reference_price · signal_reason · signal_timestamp_utc · expires_at_utc ·
risk_status · intent_id · market_weak_count · market_weak_symbols ·
market_filter_note · applied_threshold_pct`

Market-regime fields must survive the whole chain: `signals_snapshot` →
`buy_candidates` → `order_intents` → execution ledger → dashboard and Telegram
notifications — so the system can always explain **why a deeper discount was
required**.

**Verify before submitting:** trading explicitly enabled · correct Alpaca paper
account connected · US market open · sufficient strategy cash · intent not expired
· intent not already executed · position reconciled with Alpaca · risk and PDT
checks pass · no conflict with another pending order.

Orders use **deterministic client order IDs** containing asset class, strategy,
symbol, reason and unique intent identifier.

## 10. Reconciliation

Alpaca combines positions by symbol; the internal ledger must preserve strategy
ownership.

```
CORE AAPL      0.40        Broker AAPL   0.70
ACTIVE AAPL    0.20   →    (must equal the sum)
INTRADAY AAPL  0.10
```

Every fill updates: immutable trades ledger · virtual position · strategy cash ·
entry pool, debt and free cash · cooldown state · realized P&L · portfolio
snapshots · activity logs.

---

# Open items from the spec (§19–20)

Elsa flags these as known gaps between spec and current code. **The brief is the
source of truth.**

| # | Item | Action |
|---|---|---|
| 1 | `INTRADAY_MAX_CANDIDATES = 4` in the older budget allocator | Change to **10**, matching `INTRADAY_MAX_BUYS = 10` |
| 2 | `INTRADAY_MAX_BUY_PER_SYMBOL_USD = 50.0` legacy cap | Not in the current spec — **do not carry forward without an explicit decision** |
| 3 | INTRADAY growth rule not implemented | Implement at reconciliation, or immediately after INTRADAY sell proceeds hit free cash |
| 4 | Market-regime comment conflict | Comments claim INTRADAY buys are disabled at 3/3 weak. Config has `DISABLE_BUYS_AT_WEAK_COUNT = None` and threshold −5.0. **Intended behaviour: INTRADAY stays enabled at 3/3 but requires −5.0%.** Update the stale comments |
| 5 | Market-regime fields lost downstream | Add `threshold_pct`, `market_weak_count`, `market_weak_symbols`, `market_filter_note` to `04_apply_position_filters.py`, `05_budget_allocator.py`, order intents, shared intent schema, ledger, dashboard, Telegram |
| 6 | Verify SPY/QQQ/IWM always land in `intraday_reference.csv` | Review `symbols.py`, `stocks_intraday.txt`, `01_market_data_pull.py`. If missing, the scanner silently runs on the conservative fallback forever |

Item 6 is the quiet one — a missing-data path that degrades to permanently
stricter thresholds without erroring.

---

# Observations for Elsa — questions, not changes

Recorded so the team can decide. **Nothing above has been altered.**

### A. The payoff ratios are inverted relative to the video-derived rules

Running her parameters through the expectancy gate already implemented in
`deltax/gates.py`:

| Strategy | TP | SL | W/L | **Breakeven win rate** |
|---|---|---|---|---|
| CORE | +12.0% | −30.5% | 0.39 | **≈ 72%** |
| ACTIVE | +6.5% | −30.0% | 0.22 | **≈ 82%** |
| INTRADAY | +2.0% | −3.5% | 0.57 | **≈ 64%** |

For reference: `E = (1 + W/L) × P − 1 > 0`.

This is the opposite shape from S1 in the video corpus (minimum 2:1 reward-to-risk).
**That is not automatically wrong** — dip-buying mean-reversion genuinely produces
high win rates, and the trailing stops mean real exits cluster well above the raw
stop, so these breakevens are an upper bound rather than the true requirement.

But ACTIVE needing roughly **82% of trades to win just to break even** is a thin
margin, and it's the exact profile our research flagged: frequent small wins
against an infrequent large loss. **The ask is simply that the backtest reports
realized expectancy per strategy**, not win rate — then the numbers settle it.

### B. Position sizing appears calibrated for a small live account

Entry units of $70 / $30 / $30 and an INTRADAY pool of $2,850 suggest tuning for a
real account of a few thousand dollars. The hackathon account holds **$100,000**.

At $70 per CORE position that's 0.07% of equity per position — the account would
barely deploy, and **P&L is a judged criterion**. Someone should decide whether to
scale entry units proportionally or keep them absolute. This is a parameter
decision, not a flaw.

### C. The −30% stop is survivable *because* sizing is small

Worth stating explicitly since it justifies A: a −30.5% loss on a $70 position is
about $21. The wide stop is coherent with tiny position sizes. **If entry units
are scaled up for the $100k account, the stop distance must be revisited at the
same time** — the two parameters are coupled, and changing one alone breaks the
risk profile.

### D. PDT

INTRADAY runs up to 10 buys per 5-minute cycle with a 24-hour max hold, which can
generate substantial day-trade counts. At $100,000 equity we're clear of the
$25,000 pattern-day-trader minimum, so this is fine on the competition account —
but it would bite on a smaller live account.

### E. Hackathon fit

The hackathon requires that **every strategy incorporate options trading**.
Alyrise is stocks-only by design and says so. It therefore **cannot be the
submission on its own** — but its architecture is exactly right: separate engines,
one shared risk/execution/ledger layer. **Our options engine plugs into it as
`engines/options/`**, and the shared intent schema, kill switch and reconciliation
are common. That combination satisfies the requirement and is a stronger story
than either engine alone.
