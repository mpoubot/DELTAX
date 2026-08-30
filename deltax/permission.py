"""Global trade-permission state.

From Matin's proposal: a single state that sits ABOVE strategy and that no
strategy can override. Evidence recommends a state; this deterministic code
decides it; the gates enforce it.

    evidence -> recommend_state() -> PermissionState -> gate_permission()

States are ordered by restriction. The agent always adopts the MOST
restrictive state any input justifies - never the average, never the
optimistic reading.

Translated for an options condor book:
  * "long" side  = put credit spreads  (profit if the underlying holds up)
  * "short" side = call credit spreads (profit if it fails to rally)
So bearish exposure already exists as a structure. We never short stock, which
also sidesteps borrow and locate entirely.
"""

from dataclasses import dataclass, field
from typing import Optional

NORMAL = "NORMAL"
CAUTION = "CAUTION"
DEFENSIVE = "DEFENSIVE"
NO_NEW_POSITIONS = "NO_NEW_POSITIONS"
HALT = "HALT"

# most permissive first; index doubles as restriction rank
ORDER = [NORMAL, CAUTION, DEFENSIVE, NO_NEW_POSITIONS, HALT]

# What each state permits. size_factor scales position sizing.
POLICY = {
    NORMAL:           {"put_side": True,  "call_side": True,  "size_factor": 1.00},
    CAUTION:          {"put_side": True,  "call_side": True,  "size_factor": 0.50},
    DEFENSIVE:        {"put_side": False, "call_side": True,  "size_factor": 0.50},
    NO_NEW_POSITIONS: {"put_side": False, "call_side": False, "size_factor": 0.00},
    HALT:             {"put_side": False, "call_side": False, "size_factor": 0.00},
}


@dataclass
class Evidence:
    """Inputs to the state decision. None means UNKNOWN, which fails closed."""
    vix_change_pct: Optional[float] = None      # session change in VIX
    benchmarks_weak: Optional[int] = None       # 0-3, our existing regime read
    data_stale: bool = False                    # any feed failed freshness
    drawdown_pct: Optional[float] = None        # live drawdown, negative
    max_backtested_drawdown_pct: float = -10.0  # S5 kill-switch threshold
    market_open: Optional[bool] = None


@dataclass
class Decision:
    state: str
    reasons: list = field(default_factory=list)

    @property
    def policy(self) -> dict:
        return POLICY[self.state]


def _worst(a: str, b: str) -> str:
    return a if ORDER.index(a) >= ORDER.index(b) else b


def recommend_state(ev: Evidence) -> Decision:
    """Evidence -> state. Always the most restrictive justified reading."""
    state, reasons = NORMAL, []

    def raise_to(s, why):
        nonlocal state
        if ORDER.index(s) > ORDER.index(state):
            state = s
        reasons.append(f"{s}: {why}")

    # Fail closed on unusable data - E13, and Matin's DATA UNCERTAIN -> HALT.
    if ev.data_stale:
        raise_to(HALT, "feed failed freshness check")
    if ev.market_open is None:
        raise_to(HALT, "market status unknown")
    elif not ev.market_open:
        raise_to(NO_NEW_POSITIONS, "market closed")

    # S5: a live drawdown past the backtested worst case means the edge
    # changed. Halt rather than persevere.
    if ev.drawdown_pct is not None:
        if ev.drawdown_pct <= ev.max_backtested_drawdown_pct:
            raise_to(HALT, f"drawdown {ev.drawdown_pct:.1f}% past backtested "
                           f"worst case {ev.max_backtested_drawdown_pct:.1f}%")
        elif ev.drawdown_pct <= ev.max_backtested_drawdown_pct * 0.6:
            raise_to(CAUTION, f"drawdown {ev.drawdown_pct:.1f}% approaching limit")

    # Volatility shock. A condor is short vega; an IV spike hurts both sides.
    if ev.vix_change_pct is None:
        raise_to(CAUTION, "volatility reading unavailable")
    elif ev.vix_change_pct >= 30:
        raise_to(NO_NEW_POSITIONS, f"VIX +{ev.vix_change_pct:.0f}% - volatility shock")
    elif ev.vix_change_pct >= 15:
        raise_to(DEFENSIVE, f"VIX +{ev.vix_change_pct:.0f}% - stress rising")

    # Broad weakness. Not a directional call - a caution on selling puts into
    # a falling tape, which is the side that gets run over.
    if ev.benchmarks_weak is None:
        raise_to(CAUTION, "regime reading unavailable")
    elif ev.benchmarks_weak == 3:
        raise_to(DEFENSIVE, "all three benchmarks weak")

    if not reasons:
        reasons.append("NORMAL: no restriction triggered")
    return Decision(state, reasons)


def gate_permission(decision: Decision, side: str):
    """Enforce the state for one candidate. Returns (allowed, reason)."""
    p = decision.policy
    key = "put_side" if side == "put" else "call_side"
    if not p[key]:
        return False, f"{decision.state} blocks {side} spreads"
    if p["size_factor"] <= 0:
        return False, f"{decision.state} permits no new positions"
    return True, f"{decision.state} permits {side} at {p['size_factor']:.0%} size"
