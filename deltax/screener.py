"""Candidate screener: turns market state into gated, logged decisions.

Two independent nomination paths, per ENTRY-TRIGGERS.md:

  Elsa's regime filter  -> income core   (credit verticals)
  Matin's signal family -> satellite     (debit verticals)

Nothing here places an order. The screener nominates; `gates.evaluate()`
decides; `ledger` records. Pure functions are separated from I/O so the whole
selection path is testable with the market closed.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
import re

from deltax import feeds
from deltax.gates import evaluate, MIN_DTE, MAX_DTE, MIN_OPEN_INTEREST

BENCHMARKS = ["SPY", "QQQ", "IWM"]

# Elsa's dynamic-threshold table, ported: more weak benchmarks -> further OTM.
# Backtested 2026-08-29: 0.20 delta with a day-7 / 50%-credit exit is the best
# tested configuration (E = +0.075 to +0.109 across SPY/QQQ/IWM). 0.15 is
# materially weaker, 0.30 was negative on the hold-to-expiry test. The regime
# filter no longer picks direction (E11) so this varies the strike distance
# only, within the band the backtest supports.
# Walk-forward validated at REAL market prices, 31 Aug (E34). Delta 0.30 with
# 20-wide strikes on an 18-DTE expiry, exited at 4 days, was the strongest
# configuration to survive both out-of-sample testing and a Bonferroni
# correction for the 180 configurations searched: IWM out-of-sample E +0.588,
# 92% win, t=11.5 on 127 independent weeks. The prior 0.20-0.22 band was fitted
# to an assumed credit the market never paid.
TARGET_DELTA_BY_WEAK = {0: 0.30, 1: 0.30, 2: 0.28, 3: 0.25}
DELTA_BAND = (0.15, 0.35)      # rule R3: short strike stays inside 15-35 delta

# How to price a spread when evaluating it. We EVALUATE at one price and
# EXECUTE at a limit, so the two must agree or we either refuse trades we would
# have got filled on, or book fills we never get.
#   worst  - sell the bid, buy the ask. Assumes we cross both spreads.
#   mid    - mid-to-mid. Assumes a perfect fill at the midpoint.
#   haircut- mid, giving back HAIRCUT of the combined spread. Realistic.
MIN_LIQUID_STRIKES = 5     # chain is tradeable at all; not a ranking key
PRICING_MODE = "haircut"
SPREAD_HAIRCUT = 0.25
# The chain endpoint pages from the lowest strike, so an unbounded request
# returns deep-ITM contracts with unpopulated greeks. Always bound around spot.
STRIKE_BAND = {"put": (0.80, 1.02), "call": (0.98, 1.20)}
# Width scaled to price, rounded to common strike increments.
# WIDER IS BETTER, and this was the single biggest error in the original build.
# A 5-wide spread breached by $5 is a TOTAL loss; a 20-wide breached by $5 loses
# a quarter. Same strikes, same probability of being touched, but the loss is
# graduated rather than binary - worth far more than the slightly lower
# credit-per-point that wider strikes pay. We had chosen the width that
# maximises how badly a small breach hurts (E34).
#
# Widths are scaled to price: ~2.5-4% of spot, which is what the walk-forward
# tested. Names too cheap to carry a wide spread are simply not traded.
DEFAULT_WIDTH = {
    # index ETFs
    "SPY": 20.0, "QQQ": 20.0, "IWM": 10.0, "DIA": 20.0,
    # sector / thematic ETFs
    "SMH": 20.0, "SOXX": 20.0, "XLK": 5.0, "XLV": 5.0, "XLI": 5.0, "XOP": 5.0,
    # single names
    "AAPL": 10.0, "MSFT": 20.0, "META": 20.0, "AMZN": 10.0, "GOOGL": 10.0,
    "MA": 20.0, "V": 10.0, "JPM": 10.0, "UNH": 10.0, "HD": 10.0, "CRM": 10.0,
}

# Income-book candidates beyond the three regime benchmarks. All ETFs, so no
# earnings risk, and all verified to carry strikes clearing the OI floor in the
# 7-21 DTE band. Nine names for three concurrent slots - deliberately
# oversubscribed so a thin day still has candidates, not so wide that we are
# ranking for the sake of it.
# Sector sleeves span the market rather than betting on one theme. Every name
# here was verified to carry >=5 strikes clearing the OI floor inside the
# 7-21 DTE band.
#
# E10 note: adding these is OPERATIONAL - it widens what we *can* trade. The
# claim that Energy or Tech will outperform is EMPIRICAL and unvalidated, so it
# does not select direction. Direction still comes from the regime filter.
SECTOR_SLEEVES = ["XLE", "XOP", "XLK", "SMH", "SOXX", "XLF", "KRE",
                  "XLI", "XLV", "XLY", "XLP", "XLU", "XLB"]
# Names that can BOTH clear the min_credit floor and are earnings-clear.
#
# The old list was 19 ETFs, and more than half of them were mathematically
# incapable of passing our own gate: min_credit needs a >= $3.26 strike width,
# which needs a high-priced underlying, and XLU at $42 or XLF at $58 trade
# $1-wide strikes yielding $0.23. They could never trade, on any day (E33).
#
# Single names are permitted only because the earnings blocklist is now wired
# and fail-closed - blocklist.check() refuses anything it cannot positively
# clear, so a name entering this list still has to survive the gate each cycle.
# Restored 1 Sep. The UNH-only restriction was scoped to Monday's 14:30 window;
# on a fresh account with three sessions left, a one-name universe whose Sep 4
# chain does not qualify means the agent cannot trade at all.
# E50: eight ETF CANDIDATES, at most MAX_CONCURRENT traded, ordered by live
# IV/RV. Widening the candidate list does not widen the tail: the concurrency
# cap fixes how many positions exist, and ranking decides which. All eight are
# ETFs, so the earnings gate is satisfied without the SEC lookup that has never
# worked (E49). Measured this morning: KRE 1.82, XLF 1.69, XLE 1.68, XOP 1.62
# against SPY 1.08, IWM 1.15, SMH 0.70, QQQ 0.66 - the old book averaged 0.94,
# i.e. selling premium BELOW realised risk.
#
# E44: four names, not fourteen. The payoff is CAPPED at the take-profit, so
# each extra name adds breach risk without adding upside - diversification is
# strictly negative for a capped-payoff short-premium book. Measured: 14 names
# -11.7%, 6 names -1.4%, this basket +3.1%. Chosen from six candidates and
# positive under BOTH the pessimistic (IV/RV 1.15) and observed (1.45) vol
# assumptions, which is the property that matters - the margin itself is noise.
INCOME_UNIVERSE = ["SPY", "QQQ", "IWM", "SMH", "XLF", "XLE", "XOP", "KRE"]


@dataclass
class RegimeState:
    weak_count: int
    weak_symbols: list = field(default_factory=list)
    detail: dict = field(default_factory=dict)
    complete: bool = True          # False when any benchmark's data was missing

    @property
    def note(self) -> str:
        if not self.complete:
            return "incomplete benchmark data - conservative fallback applied"
        return f"{self.weak_count}/3 weak: {', '.join(self.weak_symbols) or 'none'}"


# ── pure logic ───────────────────────────────────────────────────────────────

# A benchmark must sit MEANINGFULLY below its VWAP to count as weak. Without a
# deadband the test has no noise floor: on 31 Aug at 09:45 QQQ was 0.004% below
# its VWAP and classified WEAK, which with SPY and IWM produced 3/3 -> DEFENSIVE
# and blocked the entire put side of the book on a flat tape.
#
# This is a measurement fix, not a loosening. A 0.004% gap is not a regime, and
# classifying it as one is wrong in whichever direction it happens to point -
# the same change would BLOCK trades on a day the noise ran the other way (E31).
REGIME_DEADBAND = 0.0015   # 0.15% below VWAP


def assess_regime(snapshots: dict) -> RegimeState:
    """Alyrise §4: a benchmark is weak when latest price sits meaningfully
    below its intraday VWAP - meaningfully being REGIME_DEADBAND (E31)."""
    weak, detail, complete = [], {}, True
    for sym in BENCHMARKS:
        snap = snapshots.get(sym) or {}
        price, vwap = feeds.latest_price(snap), feeds.intraday_vwap(snap)
        if price is None or vwap is None:
            complete = False
            detail[sym] = {"price": price, "vwap": vwap, "weak": None}
            continue
        is_weak = vwap > 0 and (price / vwap - 1.0) <= -REGIME_DEADBAND
        if is_weak:
            weak.append(sym)
        detail[sym] = {"price": price, "vwap": vwap, "weak": is_weak}
    # Missing data fails conservative: treat as fully weak (Alyrise fallback).
    count = 3 if not complete else len(weak)
    return RegimeState(count, weak, detail, complete)


def posture(regime: RegimeState) -> list:
    """Regime -> which credit verticals to nominate, across the REAL universe.

    An iron condor is expressed as two independent verticals so each side is
    sized and gated on its own rather than as one opaque 4-leg block.

    E48: this used to hardcode [("SPY","put"), ("QQQ","put")] and read only
    BENCHMARKS, so the morning brief announced two names while run.py went on
    to evaluate every name in INCOME_UNIVERSE on both sides. The brief feeds
    the public dashboard, so it was telling the team and the judges something
    the agent did not do. It now enumerates the universe that actually trades.
    """
    names = list(INCOME_UNIVERSE)
    if not names:
        return []
    weak = [s for s in regime.weak_symbols if s in names]
    if regime.weak_count == 0:
        return [(s, "put") for s in names]
    if regime.weak_count >= 3:
        return [(s, "call") for s in names]
    # Mixed tape: sell calls on what is weak, puts on what is not, so each
    # vertical leans with the symbol rather than against it.
    out = [(s, "call") for s in weak]
    out += [(s, "put") for s in names if s not in weak]
    if not any(sd == "call" for _, sd in out):
        out.append((regime.weak_symbols[0], "call"))
    if not any(sd == "put" for _, sd in out):
        out.append((names[0], "put"))
    return out


def _dte(expiry: str, today: date) -> int:
    return (datetime.strptime(expiry, "%Y-%m-%d").date() - today).days


def parse_expiry(occ_symbol: str) -> Optional[str]:
    """OCC symbol -> 'YYYY-MM-DD'. e.g. PLTR260918P00175000 -> 2026-09-18."""
    m = re.search(r"[A-Z](\d{2})(\d{2})(\d{2})[CP]\d{8}$", occ_symbol)
    if not m:
        return None
    yy, mm, dd = m.groups()
    return f"20{yy}-{mm}-{dd}"


def spread_pct(bid, ask) -> Optional[float]:
    if bid is None or ask is None:
        return None
    mid = (bid + ask) / 2
    return None if mid <= 0 else (ask - bid) / mid


def _price_credit(short: dict, long_leg: dict, mode: str) -> float:
    """Net credit for selling `short` and buying `long_leg`, per pricing mode."""
    worst = short["bid"] - long_leg["ask"]
    s_mid = (short["bid"] + short["ask"]) / 2
    l_mid = (long_leg["bid"] + long_leg["ask"]) / 2
    mid = s_mid - l_mid
    if mode == "worst":
        return worst
    if mode == "mid":
        return mid
    # haircut: start at mid, concede a fraction of the total spread we would
    # have to cross. Sits between the two, and is what a resting limit that
    # re-pegs toward the market should realistically achieve.
    combined = (short["ask"] - short["bid"]) + (long_leg["ask"] - long_leg["bid"])
    return mid - SPREAD_HAIRCUT * combined


def select_vertical(chain: dict, *, side: str, target_delta: float, width: float,
                    oi_by_symbol: dict, pricing: str = None) -> Optional[dict]:
    """Pick the short strike nearest target delta, then the long leg one width away.

    Returns a candidate dict, or None when the chain can't support the structure.
    """
    pricing = pricing or PRICING_MODE
    rows = []
    for sym, c in chain.items():
        d, (bid, ask) = feeds.delta(c), feeds.quote(c)
        if d is None or bid is None or ask is None or bid <= 0:
            continue
        strike = _strike_from(sym)
        if strike is None:
            continue
        rows.append({"symbol": sym, "strike": strike, "delta": abs(d),
                     "bid": bid, "ask": ask})
    # R3: only strikes inside the delta band are eligible as the short leg.
    lo, hi = DELTA_BAND
    eligible = [r for r in rows if lo <= r["delta"] <= hi]
    if not eligible:
        return None

    short = min(eligible, key=lambda r: abs(r["delta"] - target_delta))
    # Long leg: prefer the exact width, but accept the nearest liquid strike
    # within a tolerance rather than abandoning an otherwise good candidate.
    want = short["strike"] - width if side == "put" else short["strike"] + width
    longs = [r for r in rows if abs(r["strike"] - want) < 0.01]
    if not longs:
        near = [r for r in rows
                if r is not short
                and abs(r["strike"] - want) <= max(1.0, width * 0.5)
                and ((r["strike"] < short["strike"]) if side == "put"
                     else (r["strike"] > short["strike"]))]
        if not near:
            return None
        longs = [min(near, key=lambda r: abs(r["strike"] - want))]
    long_leg = longs[0]
    width = abs(short["strike"] - long_leg["strike"])   # actual, not requested

    credit = _price_credit(short, long_leg, pricing)
    worst_spread = max(filter(None, [spread_pct(short["bid"], short["ask"]),
                                     spread_pct(long_leg["bid"], long_leg["ask"])]),
                       default=None)
    return {
        "structure": "credit",
        "side": side,
        "short": short, "long": long_leg,
        "width": width,
        "credit": credit,
        "max_loss_per_contract": (width - credit) * 100,
        "max_profit_per_contract": credit * 100,
        "worst_leg_spread_pct": worst_spread,
        "open_interest": min(oi_by_symbol.get(short["symbol"], 0),
                             oi_by_symbol.get(long_leg["symbol"], 0)),
        "expiry": parse_expiry(short["symbol"]),
    }


def directional_bias(side: str, structure: str = "credit") -> tuple:
    """Translate an options structure into the direction it actually expresses.

    Teams reason in LONG and SHORT; the agent nominates "put" and "call" sides.
    They are not the same vocabulary, and the mapping inverts with structure:

        SELL a put spread  -> profits if price holds up  -> LONG  bias
        SELL a call spread -> profits if price holds down -> SHORT bias
        BUY  a call spread -> LONG        BUY a put spread -> SHORT

    A condor holds both sides at once and is therefore NEUTRAL as a book, which
    is the honest label given E11 found no directional edge.

    Returns (bias, emoji, plain_english).
    """
    credit = structure == "credit"
    if side == "put":
        return ("LONG", "📈", "profits if price holds up") if credit \
          else ("SHORT", "📉", "profits if price falls")
    if side == "call":
        return ("SHORT", "📉", "profits if price holds down") if credit \
          else ("LONG", "📈", "profits if price rises")
    return ("NEUTRAL", "⚖️", "direction-neutral")


def choose_expiry(feed, symbol: str, side: str, gte: str, lte: str,
                  strike_lo: float, strike_hi: float) -> Optional[tuple]:
    """Pick the NEAREST expiry in the band that is liquid enough to trade.

    The chain endpoint pages by expiry-then-strike, so a multi-expiry request
    returns only the NEAREST expiries - typically thin weeklies - and never
    reaches the liquid monthly. Every chain query must therefore target one
    expiry at a time, and this picks which.

    Nearest, not most-liquid (E17/E18). Over a fixed hold, a nearer expiry
    decays a larger fraction of its premium: measured walk-forward on SPY at
    delta 0.20, an 11-day expiry returned +0.109 against +0.030 for the 18-day.
    Ranking by open interest instead would always select the monthly, because
    monthlies carry far more of it than weeklies - handing us the weakest cell
    in the table. Liquidity stays a THRESHOLD (>= 5 strikes at MIN_OPEN_INTEREST,
    which is what keeps us out of untradeable chains); it is no longer the
    ranking key.

    Returns (expiry, {symbol: open_interest}) or None.
    """
    best = None
    contracts = feed.option_contracts(symbol, option_type=side, expiry_gte=gte,
                                      expiry_lte=lte, strike_gte=strike_lo,
                                      strike_lte=strike_hi, limit=1000)
    by_exp: dict = {}
    for c in contracts:
        by_exp.setdefault(c["expiration_date"], {})[c["symbol"]] = _as_int(
            c.get("open_interest"))
    for exp in sorted(by_exp):                      # ascending date = nearest first
        oi = by_exp[exp]
        liquid = sum(1 for v in oi.values() if v >= MIN_OPEN_INTEREST)
        if liquid >= MIN_LIQUID_STRIKES:
            best = (exp, oi, liquid)
            break                                   # nearest qualifying wins
    return (best[0], best[1]) if best else None


def _as_int(v) -> int:
    """Alpaca returns open_interest as a string; normalise to int."""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _strike_from(occ_symbol: str) -> Optional[float]:
    m = re.search(r"[CP](\d{8})$", occ_symbol)
    return int(m.group(1)) / 1000 if m else None


# ── orchestration ────────────────────────────────────────────────────────────

def screen_income_book(feed, ledger, *, equity: float, today: date,
                       open_portfolio_max_loss: float = 0.0) -> dict:
    """Full income-core pass: regime -> posture -> candidates -> gates -> ledger."""
    snaps = feed.snapshots(BENCHMARKS)
    regime = assess_regime(snaps)
    target_delta = TARGET_DELTA_BY_WEAK[min(regime.weak_count, 3)]
    results, committed = [], open_portfolio_max_loss

    for symbol, side in posture(regime):
        spot = feeds.latest_price(snaps.get(symbol) or {})
        if spot is None:
            continue
        lo_mult, hi_mult = STRIKE_BAND[side]
        strike_lo, strike_hi = round(spot * lo_mult, 2), round(spot * hi_mult, 2)
        expiry_gte = str(today.fromordinal(today.toordinal() + MIN_DTE))
        expiry_lte = str(today.fromordinal(today.toordinal() + MAX_DTE))
        chain = feed.option_chain(
            symbol, option_type=side,
            expiry_gte=expiry_gte, expiry_lte=expiry_lte,
            strike_gte=strike_lo, strike_lte=strike_hi,
        )
        if not chain:
            continue
        oi = {c["symbol"]: _as_int(c.get("open_interest"))
              for c in feed.option_contracts(
                  symbol, option_type=side, expiry_gte=expiry_gte,
                  expiry_lte=expiry_lte, strike_gte=strike_lo,
                  strike_lte=strike_hi, limit=500)}
        cand = select_vertical(chain, side=side, target_delta=target_delta,
                               width=DEFAULT_WIDTH.get(symbol, 5.0), oi_by_symbol=oi)
        if cand is None:
            continue
        decision = evaluate(
            symbol=symbol, equity=equity,
            max_loss_per_contract=cand["max_loss_per_contract"],
            max_profit_per_contract=cand["max_profit_per_contract"],
            credit=cand["credit"], expiry=date.fromisoformat(cand["expiry"]),
            today=today, open_interest=cand["open_interest"],
            open_portfolio_max_loss=committed,
            structure="credit", width=cand["width"],
            short_delta=cand["short"]["delta"],
            worst_leg_spread_pct=cand["worst_leg_spread_pct"],
        )
        ledger.record(decision, context={
            "book": "income", "side": side, "regime": regime.note,
            "weak_count": regime.weak_count, "target_delta": target_delta,
            "short_strike": cand["short"]["strike"], "long_strike": cand["long"]["strike"],
            "short_delta": round(cand["short"]["delta"], 4), "credit": round(cand["credit"], 2),
        })
        if decision.decision == "TRADE":
            committed += decision.max_loss
        results.append((cand, decision))

    return {"regime": regime, "results": results, "committed_max_loss": committed}


def realized_vol_20(feed, symbol: str, today: Optional[date] = None) -> Optional[float]:
    """Annualised 20-session realized vol from daily closes. None if unusable."""
    from math import log, sqrt
    from statistics import stdev
    from datetime import timedelta
    today = today or date.today()
    try:
        bars = feed.daily_bars(symbol, str(today - timedelta(days=75)), str(today), 80)
    except Exception:
        return None
    closes = [b.get("c") for b in bars if b.get("c")]
    if len(closes) < 22:
        return None
    rets = [log(closes[i] / closes[i - 1]) for i in range(len(closes) - 20, len(closes))]
    try:
        return stdev(rets) * sqrt(252)
    except Exception:
        return None


def vol_premium(feed, symbol: str, expiry: str, spot: float) -> Optional[float]:
    """Live IV/RV for the d0.30 put. None when it cannot be measured.

    E50: this is the only input the rebuilt backtest showed actually moves the
    result (-4.0% at IV/RV 1.00 vs +2.1% at 1.45). Selling a name below 1.0
    means collecting less premium than the realised risk being taken on.
    """
    try:
        rv = realized_vol_20(feed, symbol)
        if not rv or rv <= 0:
            return None
        chain = feed.option_chain(symbol, option_type="put",
                                  expiry_gte=expiry, expiry_lte=expiry,
                                  strike_gte=round(spot * 0.85, 2),
                                  strike_lte=round(spot * 1.02, 2))
        cand = [v for v in chain.values() if (v.get("greeks") or {}).get("delta")]
        if not cand:
            return None
        node = min(cand, key=lambda v: abs(abs(v["greeks"]["delta"]) - 0.30))
        iv = node.get("impliedVolatility") or 0
        return (iv / rv) if iv > 0 else None
    except Exception:
        return None                      # never let a ranking failure stop a cycle


def rank_by_vol_premium(feed, symbols: list, expiry: str, spots: dict) -> list:
    """Richest premium first. Unmeasurable names keep their place at the back.

    E50: run.py used to walk INCOME_UNIVERSE in list order and stop at
    MAX_CONCURRENT, so capital went to whichever name was typed first rather
    than to whichever name paid most. Ordering is advisory - every gate still
    runs on every candidate; this only decides who gets looked at first.
    """
    scored, unscored = [], []
    for s in symbols:
        px = spots.get(s)
        r = vol_premium(feed, s, expiry, px) if px else None
        (scored if r is not None else unscored).append((s, r))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in scored] + [s for s, _ in unscored]
