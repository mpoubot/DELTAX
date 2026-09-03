"""Freeze state, and the signals that lift it automatically.

WHY A FILE AND NOT A CONSTANT
    NEW_ENTRIES_FROZEN started as a constant in gates.py, which meant lifting it
    required editing and redeploying source. A scheduled job cannot do that
    safely. The live value lives in state/freeze.json; gates.py reads it, and
    bin/unfreeze-check.sh rewrites it every 15 minutes from the signals below.

FAIL CLOSED, ALWAYS
    Missing file, unreadable JSON, wrong shape, unparseable timestamp - every
    one of them means FROZEN. The only way to be unfrozen is for a well-formed
    state file to say so explicitly AND for its evaluation to still be fresh.
    Staleness matters: if the cron dies, an unfrozen state must not persist
    indefinitely, so an evaluation older than MAX_STATE_AGE_MIN re-freezes on
    read without anyone having to act.

THE SIGNALS
    Every one must hold, or the book stays frozen. They are deliberately about
    CAPACITY and TIME rather than market opinion - the 14 gates already decide
    whether a given structure is worth trading, and the regime engine decides
    whether it has positive risk-adjusted edge through judging. This layer only
    answers a narrower question: should the agent be allowed to add exposure at
    all right now.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional
import json
import os

ET = timezone(timedelta(hours=-4))
STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "state", "freeze.json")

# An unfrozen state older than this is treated as stale and re-freezes. If the
# cron stops running, exposure must not stay authorised on a dead signal.
MAX_STATE_AGE_MIN = 45

# ── signal thresholds ────────────────────────────────────────────────────────
# E103: 0.50 -> 0.80 on the operator's instruction. Expected profit scales with
# deployed premium times edge; at 0.50 the agent re-froze with half the cap
# unused. The $30,000 HARD cap in gates.py is unchanged - this only governs how
# much of it the signal check will let the agent reach before pausing entries.
MAX_COMMITTED_FRACTION = 1.00   # E111: 0.80 -> 1.00. Use the whole cap before pausing
MIN_HOURS_TO_FLATTEN   = 6.0    # a new position needs time to decay before 10:00
MIN_EQUITY             = 97_000.0   # do not add risk while bleeding
MAX_CVAR_FRACTION      = 0.12   # E111: 0.05 -> 0.12. Joint 5% tail may reach 12% of equity
CONTEST_FLATTEN = datetime(2026, 9, 4, 10, 0, tzinfo=ET)

DEFAULT_FROZEN_REASON = (
    "E96: new entries frozen - 4.7:1 risk/reward needs an 82.4% win rate vs "
    "~68% implied. Exits, the 50% targets and the Friday 10:00 flatten remain "
    "active.")


def _now() -> datetime:
    return datetime.now(ET)


def read_state(path: Optional[str] = None) -> dict:
    """Current freeze state. ANY doubt returns frozen.

    The path resolves at CALL time. `path: str = STATE_PATH` bound the default
    when this module was imported, so the location could never be redirected
    afterwards - not by a test, and not by any later config change.
    """
    path = path or STATE_PATH
    try:
        with open(path) as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return {"frozen": True, "reason": DEFAULT_FROZEN_REASON,
                "source": "no readable state file - failing closed"}
    if not isinstance(raw, dict) or "frozen" not in raw:
        return {"frozen": True, "reason": DEFAULT_FROZEN_REASON,
                "source": "malformed state file - failing closed"}
    if raw.get("frozen") is not False:
        return {**raw, "frozen": True}
    # Unfrozen: only honoured while the evaluation behind it is fresh.
    try:
        ts = datetime.fromisoformat(str(raw.get("evaluated_at")))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=ET)
    except (TypeError, ValueError):
        return {**raw, "frozen": True,
                "source": "unfrozen state has no readable timestamp - failing closed"}
    age_min = (_now() - ts).total_seconds() / 60.0
    if age_min > MAX_STATE_AGE_MIN:
        return {**raw, "frozen": True,
                "source": f"unfrozen state is {age_min:.0f} min old "
                          f"(max {MAX_STATE_AGE_MIN}) - failing closed"}
    return {**raw, "frozen": False, "age_min": round(age_min, 1)}


def write_state(frozen: bool, reason: str, signals: Optional[dict] = None,
                path: Optional[str] = None) -> dict:
    # Late-bound for the same reason as read_state.
    path = path or STATE_PATH
    state = {"frozen": bool(frozen), "reason": reason,
             "evaluated_at": _now().isoformat(timespec="seconds"),
             "signals": signals or {}}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)          # atomic: a reader never sees a half-file
    return state


def evaluate_signals(*, equity: float, committed: float, portfolio_cap: float,
                     unparsed: list, equities: list, sweep_failed: list,
                     now: Optional[datetime] = None,
                     engine_expected_pnl: Optional[float] = None,
                     engine_score: Optional[float] = None) -> dict:
    """Should new entries be permitted? Every signal must pass.

    Returns {"unfreeze": bool, "signals": {name: {"pass":, "detail":}}}.
    """
    now = now or _now()
    hours_left = (CONTEST_FLATTEN - now).total_seconds() / 3600.0
    sig = {}

    sig["book_legible"] = {
        "pass": not unparsed,
        "detail": f"{len(unparsed)} unparseable position(s)" if unparsed
                  else "book reconciles cleanly"}
    sig["rule_3_clean"] = {
        "pass": not equities,
        "detail": f"equity legs present: {equities}" if equities
                  else "options only"}
    sig["exits_healthy"] = {
        "pass": not sweep_failed,
        "detail": f"{len(sweep_failed)} exit(s) failed to submit" if sweep_failed
                  else "every exit submitted or resting"}
    frac = (committed / portfolio_cap) if portfolio_cap else 1.0
    sig["risk_headroom"] = {
        "pass": frac <= MAX_COMMITTED_FRACTION,
        "detail": f"committed {frac:.0%} of cap (max {MAX_COMMITTED_FRACTION:.0%})"}
    sig["time_to_work"] = {
        "pass": hours_left >= MIN_HOURS_TO_FLATTEN,
        "detail": f"{hours_left:.1f}h to the flatten "
                  f"(min {MIN_HOURS_TO_FLATTEN:.0f}h)"}
    sig["equity_floor"] = {
        "pass": equity >= MIN_EQUITY,
        "detail": f"equity ${equity:,.0f} vs floor ${MIN_EQUITY:,.0f}"}
    # E99: two separate questions, because one number cannot answer both.
    #   deadline_edge     - is the book expected to MAKE money through judging?
    #   tail_survivable   - is its bad case survivable?
    # `engine_score` now carries the JOINT expected shortfall (CVaR 5%), not the
    # candidate ranking score. The ranker subtracts 0.20 x contractual max loss,
    # so summed over a credit-spread book it sits near -8,300 regardless of the
    # market and the signal could never pass - a second freeze in disguise.
    if engine_expected_pnl is None:
        sig["deadline_edge"] = {
            "pass": False,
            "detail": "regime engine produced no reading - failing closed"}
    else:
        sig["deadline_edge"] = {
            "pass": engine_expected_pnl > 0,
            "detail": f"joint E[P&L] to judging ${engine_expected_pnl:+,.0f}"}
    if engine_score is None:
        sig["tail_survivable"] = {
            "pass": False,
            "detail": "no tail reading - failing closed"}
    else:
        limit = MAX_CVAR_FRACTION * equity
        sig["tail_survivable"] = {
            "pass": abs(min(engine_score, 0.0)) <= limit,
            "detail": f"joint CVaR5 ${engine_score:+,.0f} vs tolerance "
                      f"${limit:,.0f} ({MAX_CVAR_FRACTION:.0%} of equity)"}

    failed = [k for k, v in sig.items() if not v["pass"]]
    return {"unfreeze": not failed, "failed": failed, "signals": sig,
            "hours_to_flatten": round(hours_left, 2)}
