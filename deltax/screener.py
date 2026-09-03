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
# E69: the shortest DTE at which CREDIT_SURFACE is a valid benchmark. The
# surface was measured on 11- and 18-DTE chains and has no DTE term, so it
# systematically over-demands credit from anything much shorter.
MIN_BENCHMARK_DTE = 5
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
# E51: XLF/XLE/KRE were added to the universe in E50 without widths and fell
# through to the 10.0 default. On a $57 ETF a 10-wide spans a 17% move: it
# quoted $0.17 against a $1.27 requirement and could never pass. Width must
# scale with price, not be a constant - these sit at ~2.5-3% of spot, matching
# what SPY/QQQ/IWM already use.
                 "XLF": 2.0, "XLE": 2.0, "KRE": 2.0,
                 # E101: ~1.5-3% of spot, so max loss per contract stays in
                 # the same band as the index names rather than scaling with
                 # share price - a 5-wide spread on a $35 ETF is not a spread.
                 "EEM": 2.0, "HYG": 2.0, "FXI": 1.0, "XLU": 2.0, "SLV": 2.0,
                 "AAPL": 5.0, "ORCL": 2.5, "JPM": 5.0,
                 "RSP": 5.0, "XLI": 5.0, "XLU": 1.0, "TQQQ": 2.0, "VXX": 1.0,}

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
# E101 (2 Sep, evening). Re-pointed at names with a MEASURED variance premium.
#
# Dropped XLF, XLE, XOP, KRE: across 972 logged candidates they produced zero
# trades. Measured live they quote 16-24% median spreads against a 15% cap, so
# they consumed 58% of every scan while being structurally untradeable.
#
# Dropped SMH: IV/RV 0.91 - the one name where we were selling movement for
# LESS than the stock delivers, and it had grown to 42% of committed risk.
#
# Added DIA (IV/RV 1.64), FXI (1.24), HYG (1.16), EEM (1.12) - all measured on
# 2 Sep with >=14 strikes above the 500 open-interest floor and median spreads
# inside the 15% cap. Kept SPY (1.40), IWM (1.18), QQQ (1.17).
#
# The premium is re-measured per candidate by gate_variance_premium, so this
# list says where to LOOK. It is never a standing claim that these stay cheap.
# E103 (2 Sep, late): AAPL added - 86% tradeability on the screener, IV/RV
# above the floor, no earnings until late October. AVGO scored 90% and is
# deliberately NOT added: it reported after today's close, so tomorrow it is a
# repricing event with the same 10-17% excursion band that ruled out SNOW.
# E110 (3 Sep 10:50). Broad scan of 30 names, live: ORCL carried the richest
# variance premium on the board (IV/RV 1.83, 89% tradeability, 46 highs / 14
# lows) and JPM the highest tradeability (92%, IV/RV 1.67). Both added.
#
# ORCL reports fiscal Q1 around 9-12 Sep. The earnings gate refuses any expiry
# that crosses it - 09-11 and 09-18 - and permits 09-08. That is the gate's
# job, not this list's: adding ORCL here lets the pipeline evaluate it; the
# gate decides. After SNOW, an expiry across an earnings print is not a trade.
#
# Every single name here (AAPL, ORCL, JPM) is REFUSED until DELTAX_SEC_UA is
# set: the earnings lookup fails without it, and the gate fails closed on an
# unknown date. That is correct behaviour and it is the operator's line to set.
# E112 (3 Sep 11:40). Forty-ETF scan, live. ETFs carry no earnings lookup, so
# anything clearing here is tradeable THIS cycle without DELTAX_SEC_UA. Five
# cleared every gate at tradeability >= 70 and IV/RV >= 1.10:
#   RSP  1.58   XLI 1.52 (31 liquid strikes)   VXX 1.53   TQQQ 1.31   XLU 1.22
# VXX and TQQQ pass the pricing gates and are added on that basis; both carry
# realised-vol behaviour the IV/RV ratio understates (VXX can gap 30% in an
# hour, TQQQ is 3x). The variance-premium and defined-risk gates price each
# candidate on its own merits every cycle, and the joint-CVaR brake bounds the
# concentration against the existing index-put book. That is the control; the
# list only says where to look.
INCOME_UNIVERSE = ["DIA", "SPY", "QQQ", "IWM", "FXI", "HYG", "EEM", "AAPL", "ORCL", "JPM",
                   "RSP", "XLI", "XLU", "TQQQ", "VXX"]


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


def search_vertical(chain: dict, *, side: str, target_delta: float, width: float,
                    oi_by_symbol: dict, pricing: str = None,
                    max_spread_pct: float = 0.15,
                    min_credit: float = 0.75) -> Optional[dict]:
    """Search the chain for the best TRADEABLE vertical, instead of guessing one.

    E95. select_vertical() makes a single point pick: the one strike nearest
    target delta, then the one strike a width away. It never looks at anything
    else, so if that particular pair happens to quote badly the whole symbol is
    refused for the cycle - even when the same expiry holds dozens of structures
    that would pass every gate. Across 972 logged candidates that produced 3
    trades: they were not 972 candidates, they were 972 single guesses.

    This enumerates every (short, long) pair that is actually eligible -
    R3 delta band, real two-sided quotes, both legs above the open-interest
    floor - and keeps the ones whose quotes can survive the hard microstructure
    gates. Among those it maximises credit per dollar of risk, NET of the
    round-trip cost of crossing both books, which is the quantity the strategy
    actually earns:

        score = (credit - roundtrip) / width

    Nothing here relaxes a gate. It changes only WHICH candidate is nominated;
    evaluate() still runs the full stack on whatever this returns. A symbol that
    genuinely has no tradeable structure still returns None.
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
                     "bid": bid, "ask": ask,
                     # E101: the chain already carries implied vol. Capturing it
                     # here costs nothing; solving it later would mean a second
                     # pass over data we have already fetched.
                     "iv": c.get("impliedVolatility")})
    if not rows:
        return None

    lo, hi = DELTA_BAND
    liquid = lambda r: oi_by_symbol.get(r["symbol"], 0) >= MIN_OPEN_INTEREST
    shorts = [r for r in rows if lo <= r["delta"] <= hi and liquid(r)]
    if not shorts:
        return None

    # A long leg must be further OTM than the short, and close enough to the
    # requested width that the structure is still the one we intended to trade.
    tol = max(1.0, width * 0.5)
    best = None
    for sh in shorts:
        want = sh["strike"] - width if side == "put" else sh["strike"] + width
        for lg in rows:
            if lg is sh or not liquid(lg):
                continue
            if side == "put" and lg["strike"] >= sh["strike"]:
                continue
            if side == "call" and lg["strike"] <= sh["strike"]:
                continue
            if abs(lg["strike"] - want) > tol:
                continue
            w = abs(sh["strike"] - lg["strike"])
            if w <= 0:
                continue
            credit = _price_credit(sh, lg, pricing)
            if credit <= 0 or credit >= w:        # not a credit spread
                continue
            if credit < min_credit:
                continue
            worst = max(filter(None, [spread_pct(sh["bid"], sh["ask"]),
                                      spread_pct(lg["bid"], lg["ask"])]),
                        default=None)
            if worst is None or worst > max_spread_pct:
                continue
            roundtrip = ((sh["ask"] - sh["bid"]) + (lg["ask"] - lg["bid"]))
            # net edge per dollar of risk - what the structure actually pays
            score = (credit - roundtrip) / w
            if score <= 0:
                continue
            cand = {
                "structure": "credit", "side": side,
                "short": sh, "long": lg, "width": w, "credit": credit,
                "max_loss_per_contract": (w - credit) * 100,
                "max_profit_per_contract": credit * 100,
                "worst_leg_spread_pct": worst,
                "roundtrip_cost": roundtrip,
                "open_interest": min(oi_by_symbol.get(sh["symbol"], 0),
                                     oi_by_symbol.get(lg["symbol"], 0)),
                "expiry": parse_expiry(sh["symbol"]),
                "score": score,
                "implied_vol": sh.get("iv"),
                "delta_distance": abs(sh["delta"] - target_delta),
            }
            # Best net edge; ties broken toward the requested delta.
            key = (-score, cand["delta_distance"])
            if best is None or key < (-best["score"], best["delta_distance"]):
                best = cand
    return best


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

    # E94: THE THROUGHPUT BOTTLENECK. oi_by_symbol was used only to REPORT open
    # interest at the bottom of this function - never to choose a strike. So the
    # short leg was picked purely on delta distance, which repeatedly landed on
    # an odd strike carrying almost no open interest, and gate_liquidity then
    # refused it. Across 972 logged candidates that produced 640 liquidity
    # refusals and 3 trades, while the SAME expiry held 95 SPY strikes above the
    # 500 floor (760 alone has 38,335) sitting a fraction of a delta away.
    #
    # The floor is not the problem and is not touched: this picks the nearest
    # target-delta strike FROM the liquid ones, and falls back to the old
    # behaviour when none qualify, so it can only ever nominate a better
    # candidate. Every gate still runs on whatever comes out.
    _liquid = [r for r in eligible
               if oi_by_symbol.get(r["symbol"], 0) >= MIN_OPEN_INTEREST]
    short = min(_liquid or eligible, key=lambda r: abs(r["delta"] - target_delta))
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
        # E94: the comment above has always said "nearest LIQUID strike", but
        # nothing here consulted open interest. gate_liquidity scores the
        # structure on min(short OI, long OI), so an illiquid long leg refuses
        # the trade just as surely as an illiquid short one.
        _near_liquid = [r for r in near
                        if oi_by_symbol.get(r["symbol"], 0) >= MIN_OPEN_INTEREST]
        longs = [min(_near_liquid or near, key=lambda r: abs(r["strike"] - want))]
    long_leg = longs[0]
    width = abs(short["strike"] - long_leg["strike"])   # actual, not requested

    credit = _price_credit(short, long_leg, pricing)
    worst_spread = max(filter(None, [spread_pct(short["bid"], short["ask"]),
                                     spread_pct(long_leg["bid"], long_leg["ask"])]),
                       default=None)
    # E74: the DOLLAR cost of crossing both books, opening and closing. A
    # percentage of each option's own price says nothing about what the spread
    # costs relative to what it PAYS - SMH quoted 9% legs and still handed 57%
    # of the credit to the market maker. gate_spread_quality needs this number,
    # and until now nothing computed it, so the friction check never ran.
    def _width_of(leg):
        b, a = leg.get("bid"), leg.get("ask")
        try:
            if b is None or a is None or a <= 0:
                return None
            return max(float(a) - float(b), 0.0)
        except (TypeError, ValueError):
            return None
    _w = [_width_of(short), _width_of(long_leg)]
    roundtrip = sum(x for x in _w if x is not None) if all(
        x is not None for x in _w) else None
    return {
        "structure": "credit",
        "side": side,
        "short": short, "long": long_leg,
        "width": width,
        "credit": credit,
        "max_loss_per_contract": (width - credit) * 100,
        "max_profit_per_contract": credit * 100,
        "worst_leg_spread_pct": worst_spread,
        "roundtrip_cost": roundtrip,
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
                  strike_lo: float, strike_hi: float,
                  skip_expiries=None) -> Optional[tuple]:
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
    LAST_UNREADABLE_OI.clear()          # E88: per-call, read by run.py below
    for c in contracts:
        by_exp.setdefault(c["expiration_date"], {})[c["symbol"]] = _as_int(
            c.get("open_interest"), LAST_UNREADABLE_OI)
    skip = set(skip_expiries or ())
    for exp in sorted(by_exp):                      # ascending date = nearest first
        # E106: a structure already held or working on this expiry is refused
        # downstream anyway, so do not stop here - try the NEXT expiry. Without
        # this the nearest date always won, was always the held one, and the
        # four most tradeable names were locked at one spread per side.
        if exp in skip:
            continue
        oi = by_exp[exp]
        liquid = sum(1 for v in oi.values() if v >= MIN_OPEN_INTEREST)
        if liquid < MIN_LIQUID_STRIKES:
            continue
        # E69: skip expiries the CREDIT BENCHMARK cannot judge. CREDIT_SURFACE
        # was measured on 11- and 18-DTE chains (E34) and is keyed on
        # (delta, width) with no DTE term. A 2-DTE option correctly pays less
        # than an 11-DTE one, so gate_credit_fraction was rejecting properly
        # priced near-dated spreads for missing a benchmark that never applied
        # to them - SPY 4 Sep quoted $1.73 against a $1.80 floor built from
        # 11-18 DTE quotes, and refused, while 18 Sep quoted $2.77 and passed.
        # Until the surface carries a DTE dimension, only judge expiries inside
        # the range it was measured on.
        try:
            dte = (datetime.strptime(exp, "%Y-%m-%d").date() - date.today()).days
        except (ValueError, TypeError):
            continue
        if dte < MIN_BENCHMARK_DTE:
            continue
        best = (exp, oi, liquid)
        break                                       # nearest QUALIFYING wins
    return (best[0], best[1]) if best else None


# E88: raw open-interest values that could not be read on the most recent
# choose_expiry() call. `_as_int` returns 0 for these, which is the SAFE
# direction - gate_liquidity refuses on 0 exactly as it refuses on None - but 0
# is indistinguishable from a genuinely illiquid strike. That mattered at the
# `liquid` count below: a chain whose OI field was garbled looked exactly like a
# chain that is legitimately thin, so the expiry was skipped and the symbol
# dropped with nobody told. Same dark-silent shape as E83/E84; recorded here so
# run.py can say WHICH it was.
LAST_UNREADABLE_OI: list = []


def _as_int(v, bad: "list | None" = None) -> int:
    """Alpaca returns open_interest as a string; normalise to int.

    Returns 0 when the value cannot be read. That fails closed downstream, but
    `bad` (when supplied) records the raw value so an unreadable chain can be
    told apart from an illiquid one.
    """
    try:
        return int(float(v))
    except (TypeError, ValueError):
        if bad is not None:
            bad.append(repr(v)[:40])
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
                roundtrip_cost=cand.get("roundtrip_cost"),
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
