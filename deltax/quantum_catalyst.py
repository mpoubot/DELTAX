"""Regime-mixture P&L engine for the judging deadline. Ported from the team's
`deltax_quantum_catalyst.py` to the standard library.

WHAT THIS IS FOR
    Evaluate a candidate spread through Fri 4 Sep 2026 10:00 ET - the moment
    the book is flattened for judging - under several market regimes at once,
    and report the full P&L distribution rather than a point estimate.

TWO CHANGES FROM THE ORIGINAL, both forced:

  * numpy is not installed on ANY interpreter on this machine, cron's pinned
    /opt/homebrew/bin/python3 included, and the rest of DELTAX is stdlib-only.
    Installing a C extension into the live trading interpreter 43 hours before
    judging is not a risk worth taking for vectorisation. The maths is
    unchanged; the loops are explicit. 40k paths x 7 structures runs in a few
    seconds, which is nothing against a 15-minute cron.

  * REQUIRED_GATE_COUNT was 17. gates.evaluate() actually produces 14, so
    run_all_existing_gates() raised on every call and the engine rejected
    everything it was ever shown. The intent behind the number - proof the gate
    stack has not been silently shortened - is right and is kept: the count is
    pinned to the real 14 and tests/test_gates.py asserts evaluate() still
    produces exactly that, so a reduction fails the suite instead of passing
    unnoticed.

WHAT IT ANCHORS TO
    Implied volatility, solved per structure from the broker's own mark - never
    realized vol. Pricing a live book at realized vol overstated every spread
    here by $0.40-$1.77 and manufactured losses that did not exist.

WHAT IT MEASURES
    Incremental P&L FROM NOW, not from entry. P&L from entry is already sunk
    and answers a question nobody is asking when deciding what to do next.

This module places no orders. It returns a recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from math import erf, exp, log, sqrt
from typing import Callable, Optional, Sequence
import random

ET = timezone(timedelta(hours=-4))          # EDT; the contest runs inside DST
JUDGING_DEADLINE = datetime(2026, 9, 4, 10, 0, 0, tzinfo=ET)

# Pinned to what gates.evaluate() actually emits. A tripwire, not a guess:
# if the stack is shortened this stops matching and the engine fails closed.
REQUIRED_GATE_COUNT = 14

N_SIMULATIONS = 40_000

# Ranking penalties. Deliberately NOT profit-maximising: a structure with a
# large nominal payoff and a heavy left tail must score badly.
TAIL_RISK_WEIGHT = 0.75
MAX_LOSS_WEIGHT = 0.20
UNCERTAINTY_WEIGHT = 0.15


@dataclass(frozen=True)
class OptionLeg:
    symbol: str
    strike: float
    option_type: str            # "call" | "put"
    quantity: int               # + long, - short
    expiry: datetime
    iv: float                   # implied vol, decimal
    entry_price: float
    current_price: float


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    underlying: str
    spot: float
    legs: tuple
    multiplier: int = 100


@dataclass(frozen=True)
class GateOutcome:
    name: str
    passed: bool
    reason: str


@dataclass
class MarketEvidence:
    trend: float = 0.0              # -1 bearish .. +1 bullish
    momentum: float = 0.0
    vol_pressure: float = 0.0       # -1 crush .. +1 expansion
    catalyst_direction: float = 0.0
    liquidity_quality: float = 0.0
    evidence_confidence: float = 0.5


@dataclass(frozen=True)
class Regime:
    name: str
    drift_annual: float
    vol_multiplier: float


@dataclass
class Evaluation:
    candidate_id: str
    probability_gain: float
    expected_pnl: float
    median_pnl: float
    percentile_05: float
    percentile_01: float
    cvar_05: float
    contractual_max_profit: float
    contractual_max_loss: float
    evidence_confidence: float
    risk_adjusted_score: float
    gates_passed: int
    gates_total: int
    action: str
    reason: str


REGIMES = (
    Regime("BULL", +0.18, 1.00),
    Regime("BEAR", -0.18, 1.15),
    Regime("RANGE", 0.00, 0.75),
    Regime("VOL_EXPANSION", 0.00, 1.45),
    Regime("VOL_COMPRESSION", 0.00, 0.60),
)


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def bs_price(spot: float, strike: float, t_years: float, rate: float,
             sigma: float, option_type: str) -> float:
    if t_years <= 0:
        return (max(spot - strike, 0.0) if option_type == "call"
                else max(strike - spot, 0.0))
    if sigma <= 0:
        raise ValueError("Implied volatility must be positive.")
    d1 = (log(spot / strike) + (rate + 0.5 * sigma ** 2) * t_years) / (
        sigma * sqrt(t_years))
    d2 = d1 - sigma * sqrt(t_years)
    if option_type == "call":
        return spot * norm_cdf(d1) - strike * exp(-rate * t_years) * norm_cdf(d2)
    if option_type == "put":
        return strike * exp(-rate * t_years) * norm_cdf(-d2) - spot * norm_cdf(-d1)
    raise ValueError(f"Unknown option type: {option_type}")


def _softmax(xs: list) -> list:
    m = max(xs)
    e = [exp(x - m) for x in xs]
    t = sum(e)
    return [v / t for v in e]


def regime_probabilities(evidence: MarketEvidence) -> dict:
    """Competing market states, held simultaneously until evidence reweights.

    The amplitude representation in the original (sqrt of the probability, then
    squared back via the Born rule) is an exact identity - it returns precisely
    the softmax it was given. It is kept because it documents the intent, but it
    is arithmetic, not a quantum speedup, and nothing here claims otherwise.
    """
    scores = [
        (+1.20 * evidence.trend + 0.90 * evidence.momentum
         + 0.45 * evidence.catalyst_direction),
        (-1.20 * evidence.trend - 0.90 * evidence.momentum
         - 0.45 * evidence.catalyst_direction),
        (-0.80 * abs(evidence.trend) - 0.60 * abs(evidence.momentum)),
        (+1.25 * evidence.vol_pressure),
        (-1.25 * evidence.vol_pressure),
    ]
    probabilities = _softmax(scores)
    amplitudes = [sqrt(p) for p in probabilities]        # |a|^2 == p
    return {r.name: a * a for r, a in zip(REGIMES, amplitudes)}


def option_value_at_deadline(leg: OptionLeg, spot: float, deadline: datetime,
                             rate: float, vol_multiplier: float) -> float:
    remaining = (leg.expiry.astimezone(ET) - deadline).total_seconds()
    t = max(remaining / (365.0 * 24 * 3600), 0.0)
    sigma = max(leg.iv * vol_multiplier, 0.01)
    return bs_price(spot, leg.strike, t, rate, sigma, leg.option_type)


def terminal_contract_value(candidate: Candidate, price: float) -> float:
    v = 0.0
    for leg in candidate.legs:
        intrinsic = (max(price - leg.strike, 0.0) if leg.option_type == "call"
                     else max(leg.strike - price, 0.0))
        v += intrinsic * leg.quantity * candidate.multiplier
    return v


def entry_cashflow(candidate: Candidate) -> float:
    """Positive = net credit received; negative = net debit paid."""
    return -sum(leg.entry_price * leg.quantity * candidate.multiplier
                for leg in candidate.legs)


def exact_contractual_bounds(candidate: Candidate) -> tuple:
    """Max profit / max loss. The payoff is piecewise linear and only changes
    slope at a strike, so testing 0, every strike, and far above the top strike
    finds both bounds exactly."""
    strikes = sorted({leg.strike for leg in candidate.legs})
    tests = [0.0] + list(strikes) + ([max(strikes) * 5.0] if strikes else [])
    cash = entry_cashflow(candidate)
    pnls = [terminal_contract_value(candidate, p) + cash for p in tests]
    return float(max(pnls)), float(min(pnls))


def simulate_deadline_pnl(candidate: Candidate, evidence: MarketEvidence,
                          now: datetime, rate: float = 0.04,
                          n: int = N_SIMULATIONS, seed: int = 95) -> list:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    horizon = (JUDGING_DEADLINE - now.astimezone(ET)).total_seconds()
    if horizon <= 0:
        raise ValueError("Judging deadline has already passed.")
    hy = horizon / (365.0 * 24 * 3600)

    probs = regime_probabilities(evidence)
    weights = [probs[r.name] for r in REGIMES]
    cum, acc = [], 0.0
    for w in weights:
        acc += w
        cum.append(acc)

    ivs = sorted(leg.iv for leg in candidate.legs)
    base_iv = ivs[len(ivs) // 2] if len(ivs) % 2 else (
        (ivs[len(ivs) // 2 - 1] + ivs[len(ivs) // 2]) / 2.0)

    current_value = sum(leg.current_price * leg.quantity * candidate.multiplier
                        for leg in candidate.legs)

    rng = random.Random(seed)
    out = []
    for _ in range(n):
        u = rng.random() * cum[-1]
        idx = 0
        while idx < len(cum) - 1 and u > cum[idx]:
            idx += 1
        regime = REGIMES[idx]
        sigma = base_iv * regime.vol_multiplier
        z = rng.gauss(0.0, 1.0)
        spot = candidate.spot * exp(
            (regime.drift_annual - 0.5 * sigma ** 2) * hy + sigma * sqrt(hy) * z)
        future = 0.0
        for leg in candidate.legs:
            mark = option_value_at_deadline(
                leg, spot, JUDGING_DEADLINE, rate, regime.vol_multiplier)
            future += mark * leg.quantity * candidate.multiplier
        out.append(future - current_value)
    return out


def summarize_distribution(pnl: list) -> dict:
    s = sorted(pnl)
    n = len(s)
    q = lambda p: s[min(int(p * n), n - 1)]
    p05, p01 = q(0.05), q(0.01)
    tail = [x for x in s if x <= p05]
    return {
        "probability_gain": sum(1 for x in s if x > 0) / n,
        "expected_pnl": sum(s) / n,
        "median_pnl": s[n // 2],
        "p05": p05,
        "p01": p01,
        "cvar05": (sum(tail) / len(tail)) if tail else p05,
    }


GateFunction = Callable[[Candidate], GateOutcome]


def run_all_existing_gates(candidate: Candidate,
                           gates: Sequence) -> list:
    """Every gate runs; an exception is a FAILURE, never a skip."""
    if len(gates) != REQUIRED_GATE_COUNT:
        raise RuntimeError(
            f"Expected exactly {REQUIRED_GATE_COUNT} gates; received {len(gates)}.")
    results = []
    for gate in gates:
        try:
            results.append(gate(candidate))
        except Exception as exc:
            results.append(GateOutcome(
                name=getattr(gate, "__name__", "UNKNOWN_GATE"),
                passed=False,
                reason=f"Gate exception: {type(exc).__name__}"))
    return results


def calculate_edge_score(stats: dict, contractual_max_loss: float,
                         confidence: float) -> float:
    """Higher is better. Penalises the left tail, the contractual loss, and
    uncertainty - so a big nominal payoff with a heavy tail scores badly."""
    tail_penalty = abs(min(stats["cvar05"], 0.0))
    max_loss_penalty = abs(min(contractual_max_loss, 0.0))
    uncertainty = 1.0 - confidence
    return (stats["expected_pnl"]
            - TAIL_RISK_WEIGHT * tail_penalty
            - MAX_LOSS_WEIGHT * max_loss_penalty
            - UNCERTAINTY_WEIGHT * uncertainty * max_loss_penalty)


def evaluate_candidate(candidate: Candidate, evidence: MarketEvidence,
                       gates: Sequence, now: datetime, *,
                       freeze_new_entries: bool = True,
                       risk_reducing_order: bool = False) -> Evaluation:
    """Gates first, always. Scenario analysis never overrides a deterministic
    refusal - it only ever decides between REJECT and approval among candidates
    that already cleared every gate.

    `freeze_new_entries` is a PARAMETER, not a module constant: the live value
    lives in the freeze state file so cron can change it without editing code,
    and a stale copy compiled into this module would silently disagree with it.
    """
    results = run_all_existing_gates(candidate, gates)
    passed = sum(1 for r in results if r.passed)
    if passed != REQUIRED_GATE_COUNT:
        failed = [r.name for r in results if not r.passed]
        return Evaluation(
            candidate_id=candidate.candidate_id, probability_gain=0.0,
            expected_pnl=0.0, median_pnl=0.0, percentile_05=0.0,
            percentile_01=0.0, cvar_05=0.0, contractual_max_profit=0.0,
            contractual_max_loss=0.0,
            evidence_confidence=evidence.evidence_confidence,
            risk_adjusted_score=float("-inf"),
            gates_passed=passed, gates_total=REQUIRED_GATE_COUNT,
            action="REJECT",
            reason="Deterministic gate failure: " + ", ".join(failed))

    max_profit, max_loss = exact_contractual_bounds(candidate)
    stats = summarize_distribution(
        simulate_deadline_pnl(candidate, evidence, now))
    score = calculate_edge_score(stats, max_loss, evidence.evidence_confidence)

    if risk_reducing_order:
        action = "ALLOW_RISK_REDUCTION"
        reason = ("Order reduces existing portfolio risk. Risk-reducing exits "
                  "remain authorized.")
    elif freeze_new_entries:
        action = "REJECT_NEW_EXPOSURE"
        reason = ("All gates passed and scenario analysis completed, but "
                  "capital-preservation mode forbids increasing exposure.")
    elif stats["expected_pnl"] > 0 and score > 0:
        action = "PAPER_APPROVE"
        reason = ("All deterministic gates passed and deadline risk-adjusted "
                  "edge is positive.")
    else:
        action = "REJECT"
        reason = "No positive risk-adjusted edge through the judging deadline."

    return Evaluation(
        candidate_id=candidate.candidate_id,
        probability_gain=stats["probability_gain"],
        expected_pnl=stats["expected_pnl"], median_pnl=stats["median_pnl"],
        percentile_05=stats["p05"], percentile_01=stats["p01"],
        cvar_05=stats["cvar05"],
        contractual_max_profit=max_profit, contractual_max_loss=max_loss,
        evidence_confidence=evidence.evidence_confidence,
        risk_adjusted_score=score,
        gates_passed=passed, gates_total=REQUIRED_GATE_COUNT,
        action=action, reason=reason)
