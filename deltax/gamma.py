"""Dealer gamma exposure — where market makers are forced to hedge.

THE MECHANISM. Retail is net long options; dealers are net short them. To stay
delta-neutral a dealer must hedge, and the SIGN of their gamma decides which way
that hedging pushes price:

  POSITIVE gamma — dealers buy weakness and sell strength. Hedging LEANS AGAINST
                   the move and the tape holds a range. Good for premium selling.
  NEGATIVE gamma — dealers sell weakness and buy strength. Hedging goes WITH the
                   move and the tape trends. A short-premium book is on the wrong
                   side of every hedge.

Per strike:  GEX = open_interest x gamma x 100 x spot^2 x 0.01
Calls count positive, puts negative, which is the standard dealer-perspective
convention.

WHY THIS DATA AND NOT PRICE. Open interest updates once a day and is therefore
immune to the 15-minute delay on free-tier options quotes. Everything else we
gate on is delayed; this is not (E38).

Used as a GATE, never as a signal. It can refuse to sell premium into a
trending regime; it cannot originate a trade.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GammaMap:
    symbol: str
    spot: float
    by_strike: dict = field(default_factory=dict)   # strike -> net GEX
    total: float = 0.0
    flip: Optional[float] = None      # spot where net GEX crosses zero
    pin: Optional[float] = None       # strike carrying the most positive GEX
    complete: bool = True

    @property
    def regime(self) -> str:
        if not self.complete:
            return "UNKNOWN"
        return "POSITIVE" if self.total > 0 else "NEGATIVE"

    @property
    def premium_selling_favoured(self) -> bool:
        return self.regime == "POSITIVE"


def _strike(occ: str) -> Optional[float]:
    try:
        return int(occ[-8:]) / 1000.0
    except (ValueError, TypeError):
        return None


def build(symbol: str, spot: float, chain: dict, oi_by_symbol: dict) -> GammaMap:
    """Net dealer gamma per strike from a live chain plus open interest."""
    m = GammaMap(symbol=symbol, spot=spot)
    if not chain or spot <= 0:
        m.complete = False
        return m
    priced = 0
    for occ, row in chain.items():
        k = _strike(occ)
        g = (row.get("greeks") or {}).get("gamma")
        oi = oi_by_symbol.get(occ)
        if k is None or g is None or not oi:
            continue
        try:
            oi = int(float(oi))
        except (TypeError, ValueError):
            continue
        # Dealer perspective: short calls carry positive gamma exposure,
        # short puts negative.
        sign = 1.0 if "C" in occ[-9:-8] else -1.0
        gex = sign * oi * float(g) * 100.0 * spot * spot * 0.01
        m.by_strike[k] = m.by_strike.get(k, 0.0) + gex
        m.total += gex
        priced += 1
    if priced < 10:                      # too thin to characterise a regime
        m.complete = False
        return m
    pos = {k: v for k, v in m.by_strike.items() if v > 0}
    if pos:
        m.pin = max(pos, key=pos.get)
    m.flip = _zero_crossing(m.by_strike, spot)
    return m


def _zero_crossing(by_strike: dict, spot: float) -> Optional[float]:
    """Strike where cumulative GEX flips sign — the flip point.

    Walks strikes upward accumulating exposure; the level where the running
    total changes sign is where dealer hedging reverses direction.
    """
    if not by_strike:
        return None
    run, prev_k, prev_run = 0.0, None, 0.0
    for k in sorted(by_strike):
        run += by_strike[k]
        if prev_k is not None and (prev_run < 0 <= run or prev_run > 0 >= run):
            span = run - prev_run
            if span:
                return round(prev_k + (k - prev_k) * (-prev_run / span), 2)
            return k
        prev_k, prev_run = k, run
    return None


def gate_gamma_regime(m: Optional[GammaMap], *, require_positive: bool = True) -> tuple:
    """(allowed, reason). Fails OPEN on an unbuildable map.

    A thin or missing chain means we could not measure the regime - not that the
    regime is bad. The 13 existing gates have already judged this candidate on
    price, structure and liquidity; an unmeasurable secondary signal should not
    veto that. Contrast E28, where a missing earnings check leaves a KNOWN
    scheduled risk unexamined and must block.
    """
    if m is None or not m.complete:
        return True, "gamma regime unmeasurable - not blocking"
    if not require_positive:
        return True, f"gamma {m.regime}, gate advisory only"
    if m.premium_selling_favoured:
        return True, (f"gamma POSITIVE (net {m.total/1e9:+.2f}B) - dealers damp "
                      f"moves, pin {m.pin}")
    return False, (f"gamma NEGATIVE (net {m.total/1e9:+.2f}B) - dealer hedging "
                   f"amplifies moves, premium selling is on the wrong side")
