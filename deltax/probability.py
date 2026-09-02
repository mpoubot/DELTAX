"""E61 — P(target touched before exit | current evidence), continuously updated.

Pautax's architecture: the number that matters is not P(USO goes up) but
P(the exit level is TOUCHED before the position closes). Base rate comes from
the option market itself (ATM IV, driftless reflection principle); live
evidence then moves it in log-odds space, so updates compound like a posterior
and can never push probability past its bounds.

The prior is market-implied, so "yesterday's +5.4% already priced a lot in"
is automatically respected: a bigger prior move raises IV, which raises the
base P(touch) for nearby levels and the debit you pay — the evidence layer
only adds what the option price does NOT already know (physical disruption,
cross-market confirmation, de-escalation headlines).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import erf, log, sqrt
from typing import Optional

_N = lambda x: 0.5 * (1.0 + erf(x / sqrt(2.0)))

# Log-odds adjustments. Each counts ONCE - repeated headlines about the same
# event are the same evidence (supervisor rule 2).
EVIDENCE_WEIGHTS = {
    "hormuz_physical_disruption": +0.40,   # traffic/shipping actually impaired
    "supply_confirmed_hit":       +0.35,   # barrels off the market, not threats
    "wti_breakout_holds":         +0.30,   # crude new high AND holds the level
    "uso_confirms":               +0.25,   # above VWAP and prior close intraday
    "options_reasonably_priced":  +0.10,   # debit inside ceiling, spread tight
    "de_escalation":              -0.50,   # ceasefire / talks / traffic normal
    "oil_reversal":               -0.40,   # WTI/USO give back the move
    "momentum_lost":              -0.25,   # USO below VWAP
}

P_FLOOR, P_CEIL = 0.02, 0.95

# E62: the escalation ladder. Above the $10k base ceiling, size requires
# PHYSICAL confirmation - flags the option price cannot already contain.
# Price momentum alone (uso_confirms) can never unlock maximum size, or a
# gap-up buys risk on nothing but its own reflection.
HARD_MAX_RISK = 20_000.0
PHYSICAL_FLAGS = ("hormuz_physical_disruption", "supply_confirmed_hit",
                  "wti_breakout_holds")


def physical_count(evidence: dict) -> int:
    return sum(1 for k in PHYSICAL_FLAGS if evidence.get(k))


def p_touch_base(spot: float, level: float, iv: float,
                 sessions: float) -> Optional[float]:
    """Market-implied P(level touched within `sessions` trading days).

    Driftless GBM reflection: P = 2*N(-d), d = ln(L/S)/(sigma*sqrt(T)).
    Returns None when inputs are unusable - callers must treat None as
    'unknown', never as zero and never as certainty.
    """
    if not spot or not level or not iv or spot <= 0 or iv <= 0 or sessions <= 0:
        return None
    if level <= spot:
        return 1.0
    d = log(level / spot) / (iv * sqrt(sessions / 252.0))
    return max(P_FLOOR, min(P_CEIL, 2.0 * _N(-d)))


@dataclass
class Posterior:
    base: Optional[float]
    p: Optional[float]
    applied: list = field(default_factory=list)
    note: str = ""


def update(base: Optional[float], evidence: dict) -> Posterior:
    """Move the base probability by the ACTIVE evidence flags, in log-odds.

    `evidence` maps EVIDENCE_WEIGHTS keys to booleans. Unknown keys are
    rejected loudly - a typo in an evidence name must never silently count
    as 'no evidence'.
    """
    if base is None:
        return Posterior(None, None, note="base unusable - probability unknown")
    for k in evidence:
        if k not in EVIDENCE_WEIGHTS:
            raise KeyError(f"unknown evidence flag: {k}")
    b = min(max(base, P_FLOOR), P_CEIL)
    lo = log(b / (1.0 - b))
    applied = []
    for k, on in evidence.items():
        if on:
            lo += EVIDENCE_WEIGHTS[k]
            applied.append(f"{k}{EVIDENCE_WEIGHTS[k]:+.2f}")
    p = 1.0 / (1.0 + 2.718281828459045 ** (-lo))
    return Posterior(base, max(P_FLOOR, min(P_CEIL, p)), applied)


def catalyst_status(evidence: dict) -> str:
    """ESCALATING / UNCHANGED / FADING from the same flags."""
    pos = sum(1 for k in ("hormuz_physical_disruption", "supply_confirmed_hit",
                          "wti_breakout_holds") if evidence.get(k))
    neg = sum(1 for k in ("de_escalation", "oil_reversal", "momentum_lost")
              if evidence.get(k))
    if neg and neg >= pos:
        return "FADING"
    if pos >= 2:
        return "ESCALATING"
    return "UNCHANGED"


def size_band(p: Optional[float], physical: int = 0) -> tuple:
    """Risk follows evidence strength. E62: the ladder climbs past $10k only
    on physical confirmation, and never past HARD_MAX_RISK.

    Returns (max_risk_dollars, label). Unknown probability -> $0.
    """
    if p is None:
        return 0.0, "NO_TRADE (probability unknown)"
    if p < 0.45:
        return 2_500.0, "weak/conflicting"
    if p < 0.60:
        return 5_000.0, "good"
    if p < 0.75:
        return 7_500.0, "very strong"
    if physical >= 2 and p >= 0.85:
        return HARD_MAX_RISK, "MAX ESCALATION - 2+ physical confirmations"
    if physical >= 1:
        return 15_000.0, "escalated - physical confirmation"
    return 10_000.0, "exceptionally strong (price evidence only)"
