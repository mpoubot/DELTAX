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
TARGET_DELTA_BY_WEAK = {0: 0.22, 1: 0.21, 2: 0.20, 3: 0.20}
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
DEFAULT_WIDTH = {
    "SPY": 5.0, "QQQ": 5.0, "IWM": 2.0, "DIA": 5.0, "EEM": 1.0, "TLT": 1.0,
    # sector sleeves
    "XLE": 1.0, "XOP": 2.5,                        # energy
    "XLK": 2.5, "SMH": 5.0, "SOXX": 5.0,           # technology / semis
    "XLF": 1.0, "KRE": 1.0,                        # financials
    "XLI": 2.5,                                    # industrials
    "XLV": 2.5, "XLY": 2.0, "XLP": 1.0,            # health / discretionary / staples
    "XLU": 1.0, "XLB": 1.0,                        # utilities / materials
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
INCOME_UNIVERSE = [
    # index and sector ETFs with wide strikes
    "SPY", "QQQ", "IWM", "DIA", "XLK", "XLV", "XLI", "SMH", "SOXX", "XOP",
    # single names: earnings verified clear of the 11 Sep expiry
    "AAPL", "MSFT", "META", "AMZN", "GOOGL", "MA", "V", "JPM", "UNH", "HD", "CRM",
]


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
    """Regime -> which credit verticals to nominate.

    An iron condor is expressed as two independent verticals so each side is
    sized and gated on its own rather than as one opaque 4-leg block.
    """
    strong = [s for s in BENCHMARKS if s not in regime.weak_symbols]
    if regime.weak_count == 0:
        return [("SPY", "put"), ("QQQ", "put")]
    if regime.weak_count == 1:
        best = strong[0] if strong else "SPY"
        others = [s for s in BENCHMARKS if s != best]
        return [(best, "put")] + [(s, side) for s in others[:1] for side in ("put", "call")]
    if regime.weak_count == 2:
        weakest = regime.weak_symbols[0]
        return [(weakest, "call")] + [(s, side) for s in strong[:1] for side in ("put", "call")]
    return [(s, "call") for s in regime.weak_symbols[:2]]


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
