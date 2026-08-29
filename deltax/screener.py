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
from deltax.gates import evaluate, MIN_DTE, MAX_DTE

BENCHMARKS = ["SPY", "QQQ", "IWM"]

# Elsa's dynamic-threshold table, ported: more weak benchmarks -> further OTM.
TARGET_DELTA_BY_WEAK = {0: 0.30, 1: 0.27, 2: 0.24, 3: 0.20}
DELTA_BAND = (0.15, 0.35)      # rule R3: short strike stays inside 15-35 delta
# The chain endpoint pages from the lowest strike, so an unbounded request
# returns deep-ITM contracts with unpopulated greeks. Always bound around spot.
STRIKE_BAND = {"put": (0.80, 1.02), "call": (0.98, 1.20)}
DEFAULT_WIDTH = {"SPY": 5.0, "QQQ": 5.0, "IWM": 2.0}


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

def assess_regime(snapshots: dict) -> RegimeState:
    """Alyrise §4: a benchmark is weak when latest price < its intraday VWAP."""
    weak, detail, complete = [], {}, True
    for sym in BENCHMARKS:
        snap = snapshots.get(sym) or {}
        price, vwap = feeds.latest_price(snap), feeds.intraday_vwap(snap)
        if price is None or vwap is None:
            complete = False
            detail[sym] = {"price": price, "vwap": vwap, "weak": None}
            continue
        is_weak = price < vwap
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


def select_vertical(chain: dict, *, side: str, target_delta: float, width: float,
                    oi_by_symbol: dict) -> Optional[dict]:
    """Pick the short strike nearest target delta, then the long leg one width away.

    Returns a candidate dict, or None when the chain can't support the structure.
    """
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
    want = short["strike"] - width if side == "put" else short["strike"] + width
    longs = [r for r in rows if abs(r["strike"] - want) < 0.01]
    if not longs:
        return None
    long_leg = longs[0]

    credit = short["bid"] - long_leg["ask"]          # conservative: sell bid, buy ask
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
