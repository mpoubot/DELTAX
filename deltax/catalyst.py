"""E58 — Catalyst rule: a defined-risk long vertical on a supply shock.

This is the first structure in DELTAX that BUYS premium. Everything else sells
it. It exists because the 1-4 Sep window presented an actual oil-supply shock
(US strikes near the Strait of Hormuz, crude through $90, USO +5.46% on 1 Sep)
and the income engine has no way to express a directional view.

The rule AUTHORISES A SETUP; it does not force an entry. Every step below can
refuse, and refusing is the common case:

    catalyst true -> liquidity/OI check -> live spread pricing
        -> debit ceiling -> risk sizing -> limit MLeg order -> no fill, no chase

Sizing is derived from the ACTUAL live debit, never from a hardcoded contract
count: a plan that says "123 spreads" is right only at one price and wrong at
every other.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from math import floor
from typing import Optional

UNDERLYING     = "USO"
EXPIRY         = date(2026, 9, 4)
# E59: re-struck from 145/150 after the first real-price backtest showed the
# 3%-OTM structure losing even when USO rose +3.8% into expiry - the breakeven
# sat too far out and the debit ate the move. 140/145 puts the breakeven at
# ~+0.7% instead of +3.4%. (141/146 was the first choice but its legs carry
# OI 310/239, capping size at 11 spreads under the 5%-of-OI rule; the
# liquidity lives at the 140 and 145 strikes: 2,421/7,745.)
LONG_STRIKE    = 140.0
SHORT_STRIKE   = 145.0

# Phase-10 sizing: the ceiling is $10k but evidence strength sets the spend.
# The supporting backtests are ALL LOW_SAMPLE_CONFIDENCE (n<=5), the catalyst
# regime itself split 50/50 continuation/reversal historically (Jul 10 fakeout
# vs Jul 24 continuation), and IV is elevated. MEDIUM confidence -> 75% of max.
RISK_BUDGET    = 7_500.0    # total dollars at risk; the debit IS the max loss
# Ceiling keeps the payoff at worst 1:1 (width 5 - 2.50 = 2.50 max profit) and
# the breakeven at worst 142.50. A debit above this means USO already gapped
# and the entry edge is gone - NO TRADE rather than chase.
MAX_DEBIT      = 2.50
MIN_LEG_OI     = 500        # both legs, independently
MAX_LEG_SPREAD = 0.35       # worst leg bid/ask as a fraction of mid
MAX_OI_FRACTION = 0.05      # never take more than 5% of a leg's open interest
# E59 also caught: 3x a $1.98 debit is $5.94 - ABOVE the $5 width, an exit that
# could never fill. The target is a multiple capped at 90% of width, so the
# resting order is always inside the structure's possible value.
TARGET_MULTIPLE = 2.0
TARGET_WIDTH_CAP = 0.90     # exit never above this fraction of the width

# A move this size in the underlying, on the session before entry, is what marks
# the shock as live rather than remembered.
CATALYST_ENABLED = False   # E81 - see catalyst_active()
CATALYST_MIN_MOVE_PCT = 2.0
CATALYST_KEYWORDS = (
    "hormuz", "iran", "opec", "supply", "sanction", "tanker", "refinery",
    "embargo", "strike", "crude", "oil", "barrel", "output", "pipeline",
)


def occ(underlying: str, expiry: date, right: str, strike: float) -> str:
    """Build an OCC symbol. USO 4 Sep 2026 145 call -> USO260904C00145000."""
    return (f"{underlying}{expiry:%y%m%d}{right.upper()}"
            f"{int(round(strike * 1000)):08d}")


@dataclass
class Vertical:
    """A priced, sized, refusable trade proposal."""
    ok: bool
    reason: str
    debit: Optional[float] = None
    contracts: int = 0
    long_symbol: str = ""
    short_symbol: str = ""
    long_ask: Optional[float] = None
    short_bid: Optional[float] = None
    long_oi: int = 0
    short_oi: int = 0
    worst_spread: Optional[float] = None
    max_loss: float = 0.0
    max_profit: float = 0.0
    breakeven: Optional[float] = None
    exit_limit: Optional[float] = None
    detail: dict = field(default_factory=dict)


def _news(symbols: str = "USO,XLE,XOP,XOM", limit: int = 40) -> list:
    """Headlines. Returns [] on any failure - the catalyst then reads False."""
    try:
        out = subprocess.run(
            ["alpaca", "data", "news", "--symbols", symbols,
             "--limit", str(limit), "--quiet"],
            capture_output=True, text=True, timeout=30, env=os.environ)
        return json.loads(out.stdout).get("news", []) or []
    except Exception:
        return []


def catalyst_active(prev_close: Optional[float], last: Optional[float],
                    headlines: Optional[list] = None) -> tuple:
    """Is the supply shock live RIGHT NOW?

    Two independent confirmations, both required. A price move alone could be
    anything; headlines alone could be stale commentary about a move that has
    already reversed. Fails CLOSED - unreadable data means no catalyst.
    """
    # E81: STRUCTURE RETIRED. The full-year lifecycle backtest on real OPRA
    # prices (46 expiries, Massive) scores this debit structure at -9% of debit
    # per trade, P(mean<0) = 74.5%, max drawdown -89.9%. Its ONE positive bucket
    # is the CATALYST regime itself (n=10, +15%) - which does not survive
    # testing: permutation p = 0.185, and 0.738 after Bonferroni across the four
    # regimes examined. A random 10 of the 46 trades beats it 18.5% of the time.
    #
    # This is the same verdict the TSLA playbook got (news direction p = 0.44,
    # no better than a coin flip). The corroborating-headline requirement below
    # is the part already measured as non-predictive, so it cannot rescue the
    # structure either.
    #
    # Refused at catalyst_active() because BOTH live paths in run.py - the entry
    # at L419 and the add-on at L331 - call it, so one gate closes both. Left in
    # place rather than deleted: the research stands, and the reason it is off
    # must stay readable next to the code it disables.
    if not CATALYST_ENABLED:
        return False, ("catalyst structure retired - backtested negative "
                       "(-9%/trade, P(mean<0)=74.5%); regime edge not "
                       "significant (Bonferroni p=0.74)")
    if not prev_close or not last or prev_close <= 0:
        return False, "no price - catalyst unreadable, fails closed"
    move = (last / prev_close - 1) * 100
    if move < CATALYST_MIN_MOVE_PCT:
        return False, f"{UNDERLYING} {move:+.2f}% < {CATALYST_MIN_MOVE_PCT:.1f}% trigger"
    heads = _news() if headlines is None else headlines
    if not heads:
        return False, "no headlines retrieved - fails closed"
    hits = [h for h in heads
            if any(k in ((h.get("headline") or "") + (h.get("summary") or "")).lower()
                   for k in CATALYST_KEYWORDS)]
    if len(hits) < 3:
        return False, f"only {len(hits)} supply-shock headlines - not corroborated"
    return True, (f"{UNDERLYING} {move:+.2f}% with {len(hits)} corroborating "
                  f"headlines")


def price_vertical(feed, *, underlying: str = UNDERLYING, expiry: date = EXPIRY,
                   long_strike: float = LONG_STRIKE,
                   short_strike: float = SHORT_STRIKE,
                   risk_budget: float = RISK_BUDGET,
                   max_debit: float = MAX_DEBIT) -> Vertical:
    """Price the vertical from the LIVE book and size it from the real debit.

    Refuses on: missing quotes, thin open interest, a wide book, a debit above
    the ceiling, or a size that would take too much of either leg's OI.
    """
    from deltax.screener import _as_int

    long_sym = occ(underlying, expiry, "C", long_strike)
    short_sym = occ(underlying, expiry, "C", short_strike)
    width = short_strike - long_strike

    try:
        cons = feed.option_contracts(
            underlying, option_type="call",
            expiry_gte=str(expiry), expiry_lte=str(expiry),
            strike_gte=long_strike - 1, strike_lte=short_strike + 1, limit=1000)
        oi = {c["symbol"]: _as_int(c.get("open_interest")) for c in cons}
        chain = feed.option_chain(
            underlying, option_type="call",
            expiry_gte=str(expiry), expiry_lte=str(expiry),
            strike_gte=long_strike - 1, strike_lte=short_strike + 1)
    except Exception as e:
        return Vertical(False, f"chain unreadable ({type(e).__name__}) - refused")

    if long_sym not in chain or short_sym not in chain:
        return Vertical(False, f"legs not listed: {long_sym} / {short_sym}")

    lq = (chain[long_sym].get("latestQuote") or {})
    sq = (chain[short_sym].get("latestQuote") or {})
    la, lb = lq.get("ap") or 0.0, lq.get("bp") or 0.0
    sb, sa = sq.get("bp") or 0.0, sq.get("ap") or 0.0
    l_oi, s_oi = oi.get(long_sym, 0), oi.get(short_sym, 0)

    v = Vertical(False, "", long_symbol=long_sym, short_symbol=short_sym,
                 long_ask=la, short_bid=sb, long_oi=l_oi, short_oi=s_oi)

    if la <= 0:
        v.reason = "no ask on the long leg - cannot price"
        return v

    # We PAY the ask on what we buy and RECEIVE the bid on what we sell. Never
    # assume a mid-price fill: E34 was an entire backtest validated at a credit
    # the market never paid.
    debit = round(la - sb, 2)
    v.debit = debit

    l_spr = (la - lb) / ((la + lb) / 2) if (la + lb) > 0 else 9.9
    s_spr = (sa - sb) / ((sa + sb) / 2) if (sa + sb) > 0 else 9.9
    v.worst_spread = round(max(l_spr, s_spr), 4)

    if l_oi < MIN_LEG_OI or s_oi < MIN_LEG_OI:
        v.reason = f"open interest {l_oi}/{s_oi} below floor {MIN_LEG_OI}"
        return v
    if v.worst_spread > MAX_LEG_SPREAD:
        v.reason = f"worst leg spread {v.worst_spread:.0%} > {MAX_LEG_SPREAD:.0%}"
        return v
    if debit <= 0:
        v.reason = f"non-positive debit {debit:.2f} - quotes are crossed or stale"
        return v
    if debit > max_debit:
        v.reason = f"debit ${debit:.2f} above ceiling ${max_debit:.2f} - NO TRADE"
        return v

    contracts = int(floor(risk_budget / (debit * 100)))
    cap = int(min(l_oi, s_oi) * MAX_OI_FRACTION)
    if contracts > cap:
        contracts = cap
        v.detail["oi_capped"] = cap
    if contracts < 1:
        v.reason = f"sized to {contracts} contracts - below one"
        return v

    v.ok = True
    v.contracts = contracts
    v.max_loss = round(debit * 100 * contracts, 2)
    v.max_profit = round((width - debit) * 100 * contracts, 2)
    v.breakeven = round(long_strike + debit, 2)
    v.exit_limit = round(min(debit * TARGET_MULTIPLE, width * TARGET_WIDTH_CAP), 2)
    v.reason = (f"{contracts}x {long_strike:.0f}/{short_strike:.0f} @ ${debit:.2f} "
                f"- risk ${v.max_loss:,.0f}, max ${v.max_profit:,.0f}")
    v.detail.update({"width": width, "long_ask": la, "short_bid": sb,
                     "long_oi": l_oi, "short_oi": s_oi,
                     "worst_spread": v.worst_spread})
    return v


def legs_for(v: Vertical) -> list:
    """Execution legs for the priced vertical. Buy the low strike, sell the high."""
    from deltax.execute import Leg
    return [Leg(v.long_symbol, "buy", 1), Leg(v.short_symbol, "sell", 1)]
