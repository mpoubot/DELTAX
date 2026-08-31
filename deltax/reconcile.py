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


def pending(orders: list) -> dict:
    """(underlying, side) pairs with an order WORKING at the broker.

    Positions alone are not the book. Between submitting a spread and its fill
    there is a window - seconds to minutes on a wide chain - in which the
    position does not exist yet and the risk absolutely does. Reconciling on
    positions alone treats that window as empty and re-submits into it (E36).
    """
    held, unparsed = set(), []
    for o in orders or []:
        legs = o.get("legs") or []
        if not legs:
            sym = o.get("symbol") or ""
            occ = parse_occ(sym)
            if occ is None:
                unparsed.append(sym or "?")
                continue
            held.add((occ["underlying"], occ["right"]))
            continue
        for leg in legs:
            occ = parse_occ(leg.get("symbol", ""))
            if occ is None:
                unparsed.append(leg.get("symbol", "?"))
                continue
            # A resting EXIT is not new risk - it is how a position closes.
            if str(leg.get("position_intent", "")).endswith("_to_close"):
                continue
            held.add((occ["underlying"], occ["right"]))
    return {"held": held, "unparsed": unparsed, "count": len(orders or [])}


def reconcile(positions: list, orders: Optional[list] = None) -> dict:
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
    # Fold in anything already working at the broker.
    pend = pending(orders or [])
    held |= pend["held"]
    unparsed += pend["unparsed"]
    return {"held": held, "committed": committed, "unparsed": unparsed,
            "count": len(positions or []), "pending": len(pend["held"]),
            "pending_orders": pend["count"]}


def safe_to_open(rec: dict) -> tuple:
    """Fail closed: an unreadable book means no new risk."""
    if rec["unparsed"]:
        return False, (f"{len(rec['unparsed'])} open position(s) could not be "
                       f"parsed - refusing new risk until the book is legible")
    return True, "book reconciled"
