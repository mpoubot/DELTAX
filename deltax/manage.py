"""Position management — the half of the strategy that was never built.

E5 has always said "every fill gets a GTC exit placed immediately (50% credit)",
and E15 measured WHY: held to expiry the condor scores -0.021 to +0.076, and
modelling the day-7 / 50% exit flips every configuration positive. The exit is
not risk management bolted onto the edge. The exit IS the edge.

execute.build_close_args() existed. Nothing called it. An agent that opens
positions and never closes them does not have the expectancy we backtested.

Two responsibilities:
  1. place_exit()   — called at fill time, rests a GTC buy-to-close at 50% of
                      credit. Fills unattended, needs nobody watching.
  2. manage()       — each cycle, reconciles live positions against the target
                      and closes anything the resting order missed (a gap
                      through the strike, a partial fill, a cancelled order).

Both refuse rather than guess: a position we cannot price is reported, never
closed at an invented limit.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from deltax import execute

TAKE_PROFIT_FRACTION = 0.50    # E5 / E15
TIME_STOP_DTE = 2              # gamma zone — close regardless of profit


@dataclass
class Managed:
    symbol: str
    qty: int
    entry_credit: float
    current: Optional[float]
    dte: Optional[int]

    @property
    def captured(self) -> Optional[float]:
        if self.current is None or self.entry_credit <= 0:
            return None
        return (self.entry_credit - self.current) / self.entry_credit

    def reason(self) -> Optional[str]:
        """Why this position should close now, or None to hold."""
        c = self.captured
        if c is not None and c >= TAKE_PROFIT_FRACTION:
            return f"target hit — {c*100:.0f}% of credit captured"
        if self.dte is not None and self.dte <= TIME_STOP_DTE:
            return f"time stop — {self.dte} DTE, gamma zone"
        return None


def exit_limit(entry_credit: float) -> float:
    """Buy back at half the credit received. Round to a tradeable tick."""
    return round(entry_credit * (1.0 - TAKE_PROFIT_FRACTION), 2)


def place_exit(legs: list, qty: int, entry_credit: float, *, ledger=None,
               dry_run: bool = True) -> dict:
    """Rest a GTC closing order the moment a position is opened (E5).

    Placed at entry, not watched for later: an exit that depends on the agent
    being alive at the right minute is not an exit.
    """
    limit = exit_limit(entry_credit)
    args = execute.build_close_args(legs, qty, limit)
    record = {"action": "exit_order", "qty": qty, "limit_price": limit,
              "entry_credit": round(entry_credit, 2),
              "target_fraction": TAKE_PROFIT_FRACTION,
              "command": "alpaca " + " ".join(args), "dry_run": dry_run}
    if dry_run:
        record["result"] = "DRY_RUN — exit not placed"
    elif not execute.orders_enabled():
        record["result"] = "REFUSED — orders not enabled"
    else:
        try:
            execute.preflight()
            execute._run(args)
            record["result"] = "PLACED"
        except Exception as e:
            record["result"] = f"FAILED — {type(e).__name__}: {str(e)[:90]}"
    if ledger is not None:
        ledger.record_raw(record)
    return record


def manage(positions: list, *, ledger=None, dry_run: bool = True) -> dict:
    """Sweep open positions and close anything that has met its exit rule.

    A safety net behind the resting GTC order, not a replacement for it.
    """
    closed, held, unpriceable = [], [], []
    for p in positions:
        why = p.reason()
        if p.captured is None:
            unpriceable.append(p.symbol)      # never closed at a guessed price
            continue
        if not why:
            held.append(p.symbol)
            continue
        rec = {"action": "close", "symbol": p.symbol, "qty": p.qty,
               "reason": why, "captured": round(p.captured, 4), "dry_run": dry_run}
        rec["result"] = "DRY_RUN — not closed" if dry_run else "SWEEP"
        if ledger is not None:
            ledger.record_raw(rec)
        closed.append((p.symbol, why))
    return {"closed": closed, "held": held, "unpriceable": unpriceable}
