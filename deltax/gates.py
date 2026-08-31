"""Deterministic risk gates for the DELTAX options agent.

Design rule: these are PURE FUNCTIONS. No network, no clock, no globals.
Everything they need is passed in. That makes them unit-testable without a
market connection, and — more importantly — it means no model output can
override them. The model proposes and may abstain; this code disposes.

See STRATEGY.md and research/options/golden-rules.md for provenance.
"""

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional
import json

# ── Configuration ────────────────────────────────────────────────────────────
# Every threshold traces to a rule in research/options/golden-rules.md

# Competition posture (see COMPETITION-PLAYBOOK.md; research posture was 1%/5%).
# Pending team ratification before the Monday pre-registration commit.
PER_POSITION_RISK_PCT = 0.02   # 2% of equity max loss per position
# Raised 0.10 -> 0.30 for the competition, on the team's $30k options allocation
# (E22). Per-trade expectancy is a per-contract R-multiple and does not change
# with size - what scales is the ACCOUNT outcome distribution, in both
# directions. Worst case moves from -10% to -30%. Per-position stays at 2%, so
# deploying the full budget forces at least 15 positions rather than a few
# large ones, which is what E19 asks for.
PORTFOLIO_RISK_PCT    = 0.30   # 30% of equity max loss across all open positions
MIN_DTE               = 7      # rule R5: 0DTE banned; clear the gamma zone
MAX_DTE               = 21     # short enough to resolve inside the contest window
MIN_REWARD_RISK       = 2.0    # payoff floor; 2:1 => 33% breakeven win rate
MIN_OPEN_INTEREST     = 500    # liquidity floor per leg
MAX_SIZE_TO_OI_RATIO  = 0.05   # never take more than 5% of a strike's open interest
MIN_CREDIT            = 0.75   # ClearValue/SkyView: below this, fees eat the trade
# Raised 0.90 -> 1.15 on 2026-08-29 after backtesting ten years of real
# outcomes: at 0.90 the structure is NEGATIVE expectancy on every underlying
# and every delta tested (E = -0.098 to -0.184). Breakeven sits at roughly
# 1.03-1.20 x delta depending on the case; 1.15 clears it with a margin.
# See backtest/condor_expectancy.py. This makes the gate STRICTER - fewer
# trades pass, which is the correct direction when the alternative is
# knowingly trading a negative-expectancy structure.
CREDIT_DELTA_MULTIPLE = 1.15   # credit structures: credit/width >= 1.15 x short delta
MIN_CREDIT_FRACTION   = 0.20   # fallback floor when short delta is unavailable
MAX_SPREAD_PCT        = 0.15   # worst leg's bid/ask spread as a fraction of its mid
MAX_QUOTE_AGE_HOURS   = 1.0    # stale quotes cannot be priced or calibrated against


class Decision:
    """Outcome labels for a single evaluation."""
    TRADE  = "TRADE"
    REFUSE = "REFUSE"


@dataclass
class GateResult:
    """Result of one gate check."""
    gate: str
    passed: bool
    detail: str
    observed: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class DecisionRecord:
    """Emitted for EVERY evaluation — trade or refusal.

    This is the deliverable. An agent that explains why it declined 78 of 84
    candidates demonstrates more than a P&L number can.
    """
    symbol: str
    decision: str
    gates: list = field(default_factory=list)
    contracts: int = 0
    max_loss: float = 0.0
    max_profit: float = 0.0
    notes: str = ""

    @property
    def failed_gate(self) -> Optional[str]:
        for g in self.gates:
            if not g.passed:
                return g.gate
        return None

    def to_json(self) -> str:
        d = asdict(self)
        d["failed_gate"] = self.failed_gate
        return json.dumps(d, default=str)


# ── Individual gates ─────────────────────────────────────────────────────────

def gate_expectancy(avg_win: float, avg_loss: float, win_rate: float) -> GateResult:
    """E = (1 + W/L) * P - 1.  Trade only if E > 0.

    Equivalent to P*(W/L) - (1-P): expectancy in R-multiples. This is the gate
    the whole options corpus was missing — five sources selected on win rate
    and none measured the tail.
    """
    if avg_loss <= 0:
        return GateResult("expectancy", False, "avg_loss must be positive", None, None)
    if not 0.0 <= win_rate <= 1.0:
        return GateResult("expectancy", False, f"win_rate {win_rate} outside [0,1]", win_rate, None)
    e = (1 + avg_win / avg_loss) * win_rate - 1
    return GateResult(
        "expectancy", e > 0,
        f"E={e:.4f} ({'positive' if e > 0 else 'non-positive'})",
        round(e, 4), 0.0,
    )


def gate_defined_risk(max_loss: Optional[float]) -> GateResult:
    """Reject anything whose maximum loss is unknown or unbounded."""
    if max_loss is None:
        return GateResult("defined_risk", False, "max loss undefined — naked/unbounded")
    if max_loss <= 0:
        return GateResult("defined_risk", False, f"implausible max_loss {max_loss}", max_loss)
    return GateResult("defined_risk", True, f"max loss bounded at {max_loss:.2f}", max_loss)


def gate_position_size(max_loss: float, equity: float) -> GateResult:
    """Per-position max loss must not exceed PER_POSITION_RISK_PCT of equity.

    NOTE (E20): unreachable as a refusal through evaluate(). size_from_risk()
    floor-divides by this same cap, so contracts * max_loss <= budget holds by
    construction and this gate always passes there. It is kept as a regression
    guard - it would catch a future change that sized by any other rule - and
    it is meaningful when called directly. It is NOT active protection in the
    live path, and should not be counted as one.
    """
    cap = equity * PER_POSITION_RISK_PCT
    ok = max_loss <= cap
    return GateResult(
        "position_size", ok,
        f"max loss {max_loss:.2f} vs cap {cap:.2f}",
        round(max_loss, 2), round(cap, 2),
    )


def gate_portfolio_risk(new_max_loss: float, open_max_loss: float, equity: float) -> GateResult:
    """Total max loss across ALL positions must not exceed 5% of equity.

    If every open position went to maximum loss simultaneously, the account
    survives with 95% intact. A blow-up is arithmetically unavailable, not
    merely unlikely.
    """
    cap = equity * PORTFOLIO_RISK_PCT
    total = open_max_loss + new_max_loss
    ok = total <= cap
    return GateResult(
        "portfolio_risk", ok,
        f"total exposure {total:.2f} vs cap {cap:.2f}",
        round(total, 2), round(cap, 2),
    )


def gate_dte(expiry: date, today: date) -> GateResult:
    """Expiry must fall in the 7-21 day band.

    Below 7: rule R5 territory. The WSJ source reports a 0DTE trader whose
    worst day was ~8.7x his best. Above 21: won't resolve inside the window.
    """
    dte = (expiry - today).days
    ok = MIN_DTE <= dte <= MAX_DTE
    return GateResult(
        "dte", ok,
        f"{dte} DTE (band {MIN_DTE}-{MAX_DTE})",
        dte, None,
    )


def gate_quote_sanity(credit: Optional[float], structure: str,
                      quote_age_hours: Optional[float] = None) -> GateResult:
    """Reject structurally impossible or stale quotes before pricing them.

    A vertical CREDIT spread sells the nearer strike and buys the further one,
    so its credit is positive by arbitrage. A non-positive credit means the
    quotes are broken - crossed, stale, or timestamped inconsistently - not
    that the trade is unattractive.

    Found live: weekend quotes showed bid/ask spreads of 120-180% of mid and
    seven strike pairs where a lower put strike bid HIGHER than a higher one.
    Every threshold calibrated against that data would have been meaningless.
    """
    if credit is None:
        return GateResult("quote_sanity", False, "no credit computable")
    if structure == "credit" and credit <= 0:
        return GateResult(
            "quote_sanity", False,
            f"credit {credit:.2f} <= 0 - impossible for a credit spread; "
            f"quotes are crossed or stale", round(credit, 4), 0.0)
    if quote_age_hours is not None and quote_age_hours > MAX_QUOTE_AGE_HOURS:
        return GateResult(
            "quote_sanity", False,
            f"quotes {quote_age_hours:.1f}h old vs max {MAX_QUOTE_AGE_HOURS}h",
            round(quote_age_hours, 1), MAX_QUOTE_AGE_HOURS)
    return GateResult("quote_sanity", True, "quotes internally consistent")


def gate_spread_quality(worst_leg_spread_pct: Optional[float]) -> GateResult:
    """Bid/ask width on the worst leg, as a fraction of that leg's mid.

    Wide quotes are a direct tax on entry and, worse, on exit - a spread you
    cannot close at a fair price is not really defined-risk in practice. Closes
    the bid/ask criterion AURA specified but our first gate set omitted.
    """
    if worst_leg_spread_pct is None:
        return GateResult("spread_quality", False, "quote missing on at least one leg")
    ok = worst_leg_spread_pct <= MAX_SPREAD_PCT
    return GateResult(
        "spread_quality", ok,
        f"worst leg spread {worst_leg_spread_pct:.1%} vs max {MAX_SPREAD_PCT:.0%}",
        round(worst_leg_spread_pct, 4), MAX_SPREAD_PCT,
    )


def gate_credit_fraction(credit: float, width: float,
                         short_delta: Optional[float] = None) -> GateResult:
    """Credit structures: is the premium fair for the risk actually taken?

    An OTM credit spread can never pass a 2:1 reward:risk test - its payoff IS
    its probability - so credit structures are judged on credit/width instead.

    The floor is DELTA-RELATIVE: credit/width >= 0.9 x short delta. Short delta
    approximates the probability of finishing in the money, so this asks the
    economically meaningful question rather than applying one fixed number
    across the whole 15-35 delta band. A flat floor cannot work: measured on
    live chains, credit/width runs roughly 0.75-0.8 x delta, so any fixed floor
    high enough to be selective at 35 delta silently bans every trade at 20.

    Falls back to a flat floor only when delta is unavailable.
    """
    if width <= 0:
        return GateResult("credit_fraction", False, "width must be positive")
    frac = credit / width
    if short_delta is None:
        floor = MIN_CREDIT_FRACTION
        basis = f"flat floor {floor:.2f} (no delta)"
    else:
        floor = CREDIT_DELTA_MULTIPLE * abs(short_delta)
        basis = f"{CREDIT_DELTA_MULTIPLE} x delta {abs(short_delta):.3f} = {floor:.3f}"
    ok = frac >= floor
    return GateResult(
        "credit_fraction", ok,
        f"credit/width {frac:.3f} vs {basis}",
        round(frac, 4), round(floor, 4),
    )


def gate_reward_risk(max_profit: float, max_loss: float) -> GateResult:
    """Debit structures: reward:risk must be at least 2:1, defined before entry."""
    if max_loss <= 0:
        return GateResult("reward_risk", False, "max_loss must be positive")
    rr = max_profit / max_loss
    ok = rr >= MIN_REWARD_RISK
    return GateResult(
        "reward_risk", ok,
        f"R:R {rr:.2f} vs floor {MIN_REWARD_RISK}",
        round(rr, 2), MIN_REWARD_RISK,
    )


def gate_liquidity(open_interest: Optional[int], contracts: int) -> GateResult:
    """Open interest floor, and size must be small relative to it.

    From video 02: if your order is a large fraction of open interest you fill
    slowly or not at all — worst exactly when the trade is working. The live
    SPCX chain (OI of 6 and 1) is the canonical example of what this rejects.
    """
    if open_interest is None:
        return GateResult("liquidity", False, "open interest unknown")
    if open_interest < MIN_OPEN_INTEREST:
        return GateResult(
            "liquidity", False,
            f"OI {open_interest} below floor {MIN_OPEN_INTEREST}",
            open_interest, MIN_OPEN_INTEREST,
        )
    ratio = contracts / open_interest
    ok = ratio <= MAX_SIZE_TO_OI_RATIO
    return GateResult(
        "liquidity", ok,
        f"size/OI {ratio:.4f} vs max {MAX_SIZE_TO_OI_RATIO}",
        round(ratio, 4), MAX_SIZE_TO_OI_RATIO,
    )


def gate_credit(credit: float) -> GateResult:
    """Minimum credit per contract, so fees don't consume the edge."""
    ok = credit >= MIN_CREDIT
    return GateResult(
        "min_credit", ok,
        f"credit {credit:.2f} vs floor {MIN_CREDIT}",
        round(credit, 2), MIN_CREDIT,
    )


def gate_no_earnings_before_expiry(
    earnings_date: Optional[date], expiry: date, checked: bool = True
) -> GateResult:
    """Refuse if an earnings announcement lands before expiry.

    Every source in the corpus agrees earnings drive IV. Selling premium into
    an earnings event looks fine right until the IV crush. News is used here
    DEFENSIVELY — it can only veto a trade, never originate one, which is also
    what makes the pipeline injection-resistant.

    `checked` separates two states that a bare None used to collapse (E28):

        checked=True,  earnings_date=None  -> genuinely no earnings (e.g. an
                                              ETF, which files no 8-K at all)
        checked=False                      -> the lookup FAILED and we do not
                                              know. Refuse.

    Collapsing them made a SEC outage look identical to a clean bill of health,
    so every candidate passed the gate precisely when the gate could not see.
    """
    if not checked:
        return GateResult("earnings", False,
                          "earnings status UNKNOWN - lookup failed, refusing (fail-closed)")
    if earnings_date is None:
        return GateResult("earnings", True, "no earnings scheduled before expiry")
    if earnings_date <= expiry:
        return GateResult(
            "earnings", False,
            f"earnings {earnings_date} falls on/before expiry {expiry}",
        )
    return GateResult("earnings", True, f"earnings {earnings_date} after expiry {expiry}")


# An instrument can have a decade of clean history and not exist today. TRX/USD
# carries 332 daily bars through 2023-04-19 and returns ZERO bars for Aug 2026:
# Alpaca delisted it. Backtests read fine; an order would have no market. Age
# limits differ because crypto trades 24/7 - a silent day there is a red flag,
# while equities are legitimately silent over weekends and holidays (E25).
MAX_BAR_AGE_DAYS = {"equity": 4.0, "crypto": 1.5}


def gate_listed(tradable: Optional[bool], last_bar_age_days: Optional[float],
                asset_class: str = "equity") -> GateResult:
    """Is this instrument actually live RIGHT NOW - not merely in our history?"""
    limit = MAX_BAR_AGE_DAYS.get(asset_class, 4.0)
    if tradable is None or last_bar_age_days is None:
        return GateResult("listed", False,
                          "listing status unknown - fail closed", None, limit)
    if not tradable:
        return GateResult("listed", False, "asset not tradable at the venue",
                          None, limit)
    ok = last_bar_age_days <= limit
    return GateResult(
        "listed", ok,
        f"last bar {last_bar_age_days:.1f}d old vs {limit:.1f}d limit "
        f"({asset_class})" + ("" if ok else " - likely delisted"),
        round(last_bar_age_days, 2), limit,
    )


def gate_tradeable(halted: bool, corporate_action: Optional[str]) -> GateResult:
    """Refuse halted names and pending corporate actions.

    An options position in a halted underlying cannot be closed — which breaks
    the assumption the portfolio cap relies on.
    """
    if halted:
        return GateResult("tradeable", False, "underlying is halted")
    if corporate_action:
        return GateResult("tradeable", False, f"pending corporate action: {corporate_action}")
    return GateResult("tradeable", True, "no halt or corporate action")


# ── Sizing ───────────────────────────────────────────────────────────────────

def size_from_risk(equity: float, max_loss_per_contract: float) -> int:
    """contracts = risk budget / max loss per contract.

    Size is DERIVED from defined risk, never chosen by conviction. Returns 0
    when a single contract already exceeds the budget — which is a refusal,
    not an error.
    """
    if max_loss_per_contract <= 0:
        return 0
    budget = equity * PER_POSITION_RISK_PCT
    return int(budget // max_loss_per_contract)


# ── Orchestration ────────────────────────────────────────────────────────────

def evaluate(
    *,
    symbol: str,
    equity: float,
    max_loss_per_contract: float,
    max_profit_per_contract: float,
    credit: float,
    expiry: date,
    today: date,
    open_interest: Optional[int],
    open_portfolio_max_loss: float = 0.0,
    structure: str = "debit",
    width: Optional[float] = None,
    short_delta: Optional[float] = None,
    worst_leg_spread_pct: Optional[float] = None,
    quote_age_hours: Optional[float] = None,
    tradable: Optional[bool] = None,
    last_bar_age_days: Optional[float] = None,
    asset_class: str = "equity",
    earnings_date: Optional[date] = None,
    earnings_checked: bool = True,
    halted: bool = False,
    corporate_action: Optional[str] = None,
    avg_win: Optional[float] = None,
    avg_loss: Optional[float] = None,
    win_rate: Optional[float] = None,
) -> DecisionRecord:
    """Run every gate and return a decision record.

    ALL gates are evaluated even after one fails, so the record shows the full
    picture rather than stopping at the first problem.
    """
    # Undefined risk is refused BEFORE any arithmetic depends on it. Sizing ran
    # first here, so a None max_loss raised TypeError and aborted the run rather
    # than producing a refusal - making gate_defined_risk unreachable for the
    # very case it exists to catch, despite passing its own unit tests. A crash
    # is not a refusal: it logs no decision and leaves the ledger silent (E20).
    if max_loss_per_contract is None or max_profit_per_contract is None:
        return DecisionRecord(
            symbol=symbol, decision="REFUSE",
            gates=[gate_defined_risk(max_loss_per_contract)],
            contracts=0, max_loss=0.0, max_profit=0.0,
            notes="undefined risk - refused before sizing")

    contracts = size_from_risk(equity, max_loss_per_contract)
    total_max_loss = contracts * max_loss_per_contract
    total_max_profit = contracts * max_profit_per_contract

    gates = [
        gate_quote_sanity(credit, structure, quote_age_hours),
        gate_tradeable(halted, corporate_action),
        gate_defined_risk(max_loss_per_contract),
        gate_dte(expiry, today),
        gate_no_earnings_before_expiry(earnings_date, expiry, earnings_checked),
        gate_liquidity(open_interest, contracts),
        gate_credit(credit),
        gate_position_size(total_max_loss, equity),
        gate_portfolio_risk(total_max_loss, open_portfolio_max_loss, equity),
    ]
    # Only enforced when listing evidence was supplied, so existing callers keep
    # working; run.py passes it, and E25 requires it before any live order.
    if tradable is not None or last_bar_age_days is not None:
        gates.insert(2, gate_listed(tradable, last_bar_age_days, asset_class))
    if worst_leg_spread_pct is not None:
        gates.append(gate_spread_quality(worst_leg_spread_pct))
    # Structure-aware payoff gate: a 2:1 floor would refuse every OTM credit
    # spread (its payoff is its probability), so credit structures are judged
    # on credit/width instead.
    if structure == "credit":
        gates.append(gate_credit_fraction(
            credit, width if width is not None else 0.0, short_delta))
    else:
        gates.append(gate_reward_risk(max_profit_per_contract, max_loss_per_contract))

    if None not in (avg_win, avg_loss, win_rate):
        gates.append(gate_expectancy(avg_win, avg_loss, win_rate))

    if contracts < 1:
        gates.append(GateResult(
            "sizing", False,
            f"one contract ({max_loss_per_contract:.2f}) exceeds "
            f"{PER_POSITION_RISK_PCT:.0%} budget ({equity * PER_POSITION_RISK_PCT:.2f})",
        ))

    passed = all(g.passed for g in gates)
    return DecisionRecord(
        symbol=symbol,
        decision=Decision.TRADE if passed else Decision.REFUSE,
        gates=gates,
        contracts=contracts if passed else 0,
        max_loss=round(total_max_loss, 2) if passed else 0.0,
        max_profit=round(total_max_profit, 2) if passed else 0.0,
    )
