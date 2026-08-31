"""What do we already hold? Answered before anything new is opened.

THE BUG THIS EXISTS TO FIX. run() started `committed = 0.0` on every cycle and
never asked the broker what was open. The portfolio_risk gate therefore only
ever saw the current cycle's fills. Scheduled every 5 minutes from 09:30, that
is 96 runs a day, each believing the book was empty - the $30,000 cap would
have been breached on the SECOND run and the account carried roughly 1,150
positions by the close.

Reconciliation is not bookkeeping. It is what makes the risk cap mean anything
at all across more than one cycle.
"""
from __future__ import annotations
from typing import Optional


def parse_occ(sym: str) -> Optional[dict]:
    """SPY260911P00750000 -> underlying SPY, 2026-09-11, put, strike 750.

    Returns None rather than guessing on anything that does not parse - an
    unparseable holding must widen the refusal, never be silently ignored.
    """
    if not sym or len(sym) < 15:
        return None
    body = sym[-15:]
    root = sym[:-15]
    if not root or not body[:6].isdigit() or body[6] not in "CP" or not body[7:].isdigit():
        return None
    return {"underlying": root, "expiry": body[:6],
            "right": "call" if body[6] == "C" else "put",
            "strike": int(body[7:]) / 1000.0}


def reconcile(positions: list) -> dict:
    """Live book -> committed risk and the (underlying, side) pairs held.

    `committed` is deliberately conservative: for a vertical we are short one
    leg and long another, and the true max loss needs both. Summing the SHORT
    legs' notional-at-risk overstates it, which is the safe direction to be
    wrong in when the number gates further risk.
    """
    held, committed, unparsed = set(), 0.0, []
    for p in positions or []:
        sym = p.get("symbol", "")
        occ = parse_occ(sym)
        if occ is None:
            unparsed.append(sym)
            continue
        held.add((occ["underlying"], occ["right"]))
        try:
            qty = abs(float(p.get("qty") or 0))
            basis = abs(float(p.get("cost_basis") or 0))
        except (TypeError, ValueError):
            unparsed.append(sym)
            continue
        # Short legs carry the risk; long legs are the protection already paid for.
        if float(p.get("qty") or 0) < 0:
            committed += max(basis, occ["strike"] * qty * 100 * 0.0)
    return {"held": held, "committed": committed, "unparsed": unparsed,
            "count": len(positions or [])}


def safe_to_open(rec: dict) -> tuple:
    """Fail closed: an unreadable book means no new risk."""
    if rec["unparsed"]:
        return False, (f"{len(rec['unparsed'])} open position(s) could not be "
                       f"parsed - refusing new risk until the book is legible")
    return True, "book reconciled"
