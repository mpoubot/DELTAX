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


# Daily loss limit. Distinct from the cumulative drawdown check below: this
# reacts to a SHOCK - one bad session - while the drawdown check reacts to slow
# bleed. Measured at 30% deployed risk it fires in ~19-23% of weeks (5.6-7.0%
# of days), which is affordable because HALT stops NEW positions and does not
# force-close the existing book (E24).
DAILY_LOSS_LIMIT_PCT = -5.0


@dataclass
class Evidence:
    """Inputs to the state decision. None means UNKNOWN, which fails closed."""
    vix_change_pct: Optional[float] = None      # session change in VIX
    benchmarks_weak: Optional[int] = None       # 0-3, our existing regime read
    data_stale: bool = False                    # any feed failed freshness
    drawdown_pct: Optional[float] = None
    daily_loss_pct: Optional[float] = None      # today's P&L as % of equity        # live drawdown, negative
    # Halt at two-thirds of the deployed risk budget, not at all of it. With
    # PORTFOLIO_RISK_PCT at 0.30 the modelled worst case is -30%, but a circuit
    # breaker that only fires once the entire budget is gone is not a circuit
    # breaker. -20% stops us with a third of the risk budget still unspent and
    # 80% of the account intact. CAUTION fires at 60% of this, i.e. -12%.
    max_backtested_drawdown_pct: float = -20.0  # S5 kill-switch threshold
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

    # Daily loss limit. A shock filter, separate from the cumulative check
    # below: one bad session halts new risk even if the account is still up on
    # the week. HALT stops NEW positions - it does not force-close the book -
    # so a false trigger costs little.
    if ev.daily_loss_pct is not None and ev.daily_loss_pct <= DAILY_LOSS_LIMIT_PCT:
        raise_to(HALT, f"daily loss {ev.daily_loss_pct:.1f}% breached "
                       f"{DAILY_LOSS_LIMIT_PCT:.1f}% limit")

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
