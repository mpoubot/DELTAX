"""E70 — Alyrise ETF engine: dip-buying against a VWAP reference.

Implements the INTRADAY strategy from `research/stocks/golden-rules.md`, the
authoritative stock specification by **Ilze Rosicka (Elsa)**. Parameters are
hers; only the capital scale is changed, and that change is stated below.

    buy   latest <= intraday_vwap * (1 - threshold)  AND  latest < prev_close
    sell  stop loss -> trailing stop -> take profit -> max hold   (her order)

INTRADAY was chosen over CORE/ACTIVE because the contest closes 4 Sep: CORE and
ACTIVE reference 7- and 20-day VWAPs and carry -30% stops, horizons this window
cannot express. INTRADAY's +2.0% target and 24-hour max hold fit the days left.

**Scale.** Elsa's spec sets entry_unit $30 on a $2,850 pool - her own review
notes it is "calibrated for a small live account". Scaled x66 for a $100,000
paper account, preserving her 95-unit pool structure:
    entry_unit $2,000 · pool $20,000 (10 concurrent positions max)

**Compliance note.** Core requirement 3 is that every strategy incorporate
options. Alyrise is stocks-only by design and Elsa's file says so - it cannot
carry the submission alone. The options engine remains the compliance vehicle;
this runs beside it because equity dip-buying is what the operator asked for
and what Elsa's data supports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# ── Elsa's INTRADAY parameters (golden-rules.md §3) ─────────────────────────
BUY_THRESHOLD_BY_WEAK = {0: 0.025, 1: 0.030, 2: 0.035, 3: 0.050}
FALLBACK_THRESHOLD    = 0.035     # missing data -> conservative (her §4)
TAKE_PROFIT           = 0.020
STOP_LOSS             = -0.035
TRAIL_ACTIVATE        = 0.012
TRAIL_DISTANCE        = 0.010
MAX_HOLD_HOURS        = 24
MAX_HOLD_MIN_PNL      = 0.0007    # her §8: below this, time alone never sells
MAX_BUYS_PER_CYCLE    = 10

# ── scale (see module docstring) ────────────────────────────────────────────
ENTRY_UNIT   = 2_000.0
ENTRY_POOL   = 20_000.0

# Liquid, optionable ETFs. Deliberately excludes SPY/QQQ/IWM: Elsa's §4 states
# the regime benchmarks "must not become buy candidates".
UNIVERSE = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB",
            "SMH", "SOXX", "XOP", "KRE", "DIA", "EEM", "TLT"]


@dataclass
class Intent:
    """An auditable intent. Elsa's §9: scans generate intents, never orders."""
    strategy: str
    symbol: str
    side: str
    reason: str
    reference_price: Optional[float] = None
    latest_price: Optional[float] = None
    drop_pct: Optional[float] = None
    notional_usd: Optional[float] = None
    ts_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def buy_threshold(weak_count: Optional[int]) -> float:
    """Regime-adjusted discount. Unknown regime -> her conservative fallback."""
    if weak_count is None:
        return FALLBACK_THRESHOLD
    return BUY_THRESHOLD_BY_WEAK.get(min(max(int(weak_count), 0), 3),
                                     FALLBACK_THRESHOLD)


def buy_signal(latest: Optional[float], intraday_vwap: Optional[float],
               prev_close: Optional[float], weak_count: Optional[int]) -> tuple:
    """(fires, drop_pct, reason). Fails CLOSED on any missing input."""
    if not latest or not intraday_vwap or not prev_close:
        return False, None, "missing price data - no signal"
    if intraday_vwap <= 0:
        return False, None, "unusable vwap"
    thr = buy_threshold(weak_count)
    trigger = intraday_vwap * (1 - thr)
    drop = latest / intraday_vwap - 1
    if latest > trigger:
        return False, drop, f"{drop:+.2%} vs required {-thr:.2%} of VWAP"
    if latest >= prev_close:
        return False, drop, "not below previous close (her second condition)"
    return True, drop, (f"{drop:+.2%} below VWAP (needs {-thr:.2%}) "
                        f"and under prev close")


def sell_signal(entry: Optional[float], latest: Optional[float],
                peak: Optional[float], held_hours: float,
                trail_armed: bool = False) -> tuple:
    """(fires, reason, now_armed). Priority is Elsa's §8 order, unchanged:
    stop loss -> trailing stop -> take profit -> max hold."""
    if not entry or not latest or entry <= 0:
        return False, "unpriceable - never sold at a guess", trail_armed
    pnl = latest / entry - 1
    high = max(peak or latest, latest)
    armed = trail_armed or (high / entry - 1) >= TRAIL_ACTIVATE

    if pnl <= STOP_LOSS:
        return True, f"stop loss {pnl:+.2%}", armed
    if armed and latest <= high * (1 - TRAIL_DISTANCE):
        return True, f"trailing stop {pnl:+.2%} ({high:.2f} peak)", armed
    if pnl >= TAKE_PROFIT:
        return True, f"take profit {pnl:+.2%}", armed
    if held_hours >= MAX_HOLD_HOURS:
        # Her §8: below the floor, time alone never forces a sale.
        if pnl >= MAX_HOLD_MIN_PNL:
            return True, f"max hold {held_hours:.0f}h at {pnl:+.2%}", armed
        return False, f"max hold reached but {pnl:+.2%} below floor", armed
    return False, f"hold {pnl:+.2%}", armed


def _px(snap: dict) -> Optional[float]:
    t = (snap.get("latestTrade") or {}).get("p")
    if t is not None:
        return float(t)
    c = (snap.get("dailyBar") or {}).get("c")
    return float(c) if c is not None else None


def _vw(snap: dict) -> Optional[float]:
    v = (snap.get("dailyBar") or {}).get("vw")
    return float(v) if v is not None else None


def _pc(snap: dict) -> Optional[float]:
    c = (snap.get("prevDailyBar") or {}).get("c")
    return float(c) if c is not None else None


def scan(snapshots: dict, weak_count: Optional[int], held: set,
         pool_balance: float, universe: Optional[list] = None) -> list:
    """Generate buy intents, deepest drop first (her §5 selection rule).

    Reads snapshots directly rather than importing deltax.feeds: this module
    must stay testable in isolation, and a scan that cannot be tested is a
    scan that ships unverified.
    """
    out = []
    for sym in (universe or UNIVERSE):
        if sym in held:
            continue                       # never add to an open position (§6)
        snap = snapshots.get(sym) or {}
        px, vw, pc = _px(snap), _vw(snap), _pc(snap)
        fires, drop, why = buy_signal(px, vw, pc, weak_count)
        if not fires:
            continue
        out.append(Intent("INTRADAY", sym, "buy", why, reference_price=vw,
                          latest_price=px, drop_pct=drop,
                          notional_usd=ENTRY_UNIT))
    out.sort(key=lambda i: i.drop_pct if i.drop_pct is not None else 0.0)
    affordable = int(pool_balance // ENTRY_UNIT)
    return out[:min(MAX_BUYS_PER_CYCLE, max(affordable, 0))]
