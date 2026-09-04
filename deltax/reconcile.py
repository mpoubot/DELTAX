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
    held, unparsed, equities = set(), [], []
    for o in orders or []:
        legs = o.get("legs") or []
        if not legs:
            sym = o.get("symbol") or ""
            occ = parse_occ(sym)
            if occ is None:
                # E72: an equity ORDER is not an illegible option. A working
                # IGV buy was landing in `unparsed`, which made safe_to_open
                # refuse every new options trade - the same cross-strategy
                # deadlock the positions path had, one layer up.
                cls = str(o.get("asset_class") or "").lower()
                if cls in ("us_equity", "equity") or (
                        sym.isalpha() and 1 <= len(sym) <= 5):
                    equities.append(sym)
                    continue
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
    return {"held": held, "unparsed": unparsed, "equities": equities,
            "count": len(orders or [])}


def reconcile(positions: list, orders: Optional[list] = None) -> dict:
    """Live book -> committed risk and the (underlying, side) pairs held.

    `committed` is deliberately conservative: for a vertical we are short one
    leg and long another, and the true max loss needs both. Summing the SHORT
    legs' notional-at-risk overstates it, which is the safe direction to be
    wrong in when the number gates further risk.
    """
    held, committed, unparsed, equities = set(), 0.0, [], []
    held_exp: set = set()       # E106: (underlying, right, expiry) - per structure
    structs: dict = {}          # E79: (underlying, right, expiry) -> legs
    for p in positions or []:
        sym = p.get("symbol", "")
        occ = parse_occ(sym)
        if occ is None:
            # E72: an EQUITY ticker is not an unparseable option. The rotation
            # and Alyrise engines hold plain shares (XOP, IGV), and treating
            # those as "illegible" made safe_to_open refuse ALL new options
            # risk - one strategy silently disabling another. A short OCC
            # symbol that is not a valid contract is still a real anomaly and
            # must stay in `unparsed`; a clean ticker is simply equity.
            cls = str(p.get("asset_class") or "").lower()
            if cls in ("us_equity", "equity") or (
                    sym.isalpha() and 1 <= len(sym) <= 5):
                equities.append(sym)
                try:
                    committed += abs(float(p.get("cost_basis") or 0))
                except (TypeError, ValueError):
                    # E85: `pass` here counted the holding as ZERO committed
                    # risk. The portfolio cap then silently understated the
                    # book - the same shape as E79, where the risk number did
                    # not measure risk. The options path below already treats
                    # an unreadable position as `unparsed`, which fails closed
                    # via safe_to_open; this module's own contract says an
                    # unparseable holding must WIDEN the refusal, never be
                    # silently ignored. Made consistent.
                    #
                    # This path is reachable in normal operation: an assigned
                    # short option becomes an equity position without any order
                    # being placed, so it bypasses the E82 rule-3 guard.
                    unparsed.append(sym)
                continue
            unparsed.append(sym)
            continue
        held.add((occ["underlying"], occ["right"]))
        held_exp.add((occ["underlying"], occ["right"], occ["expiry"]))
        try:
            qty = float(p.get("qty") or 0)
            entry = abs(float(p.get("avg_entry_price") or 0))
        except (TypeError, ValueError):
            unparsed.append(sym)
            continue
        # E79: collect the legs; committed risk is computed from the PAIRED
        # structure below. The previous line was
        #     committed += max(basis, occ["strike"] * qty * 100 * 0.0)
        # whose second term is multiplied by ZERO, so it reduced to `basis` -
        # the premium RECEIVED on the short leg. That is not max loss. Max loss
        # on a vertical is (width - credit) x 100 x qty, and the two numbers are
        # unrelated: measured live on 2 Sep the book's true risk was $32,988
        # against a believed $27,722, and the 30% portfolio cap was already
        # breached by $3,175 with no gate aware of it.
        structs.setdefault((occ["underlying"], occ["right"], occ["expiry"]), {})[
            "short" if qty < 0 else "long"] = (abs(qty), entry, occ["strike"])
    # E79: TRUE max loss, per paired structure. A short leg alone tells you
    # what was received, never what can be lost. Anything unpaired is treated
    # as a naked short and charged its full notional - the conservative
    # direction, and the only safe assumption when the protective leg is
    # missing from the book.
    for (_u, _r, _e), v in structs.items():
        sh = v.get("short")
        if not sh:
            continue                       # long-only: paid for, carries no risk
        sq, se, sk = sh
        lg = v.get("long")
        if lg:
            lq, le, lk = lg
            width = abs(sk - lk)
            credit = se - le
            n = min(sq, lq)
            committed += max(width - credit, 0.0) * 100 * n
            if sq > lq:                    # partially covered: the rest is naked
                committed += sk * 100 * (sq - lq)
        else:
            committed += sk * 100 * sq     # naked short: full notional

    # Fold in anything already working at the broker.
    pend = pending(orders or [])
    held |= pend["held"]
    unparsed += pend["unparsed"]
    equities += pend.get("equities") or []
    # E106: pending opens also count against their expiry, so two cycles cannot
    # race the same structure into the book (the E36 window, one key wider).
    for o in orders or []:
        for leg in (o.get("legs") or [o]):
            if str(leg.get("position_intent", "")).endswith("_to_close"):
                continue
            occ = parse_occ(leg.get("symbol", ""))
            if occ:
                held_exp.add((occ["underlying"], occ["right"], occ["expiry"]))
    return {"held": held, "held_exp": held_exp, "committed": committed,
            "unparsed": unparsed, "equities": equities,
            "count": len(positions or []), "pending": len(pend["held"]),
            "pending_orders": pend["count"]}


def safe_to_open(rec: dict) -> tuple:
    """Fail closed: an unreadable book means no new risk."""
    if rec["unparsed"]:
        return False, (f"{len(rec['unparsed'])} open position(s) could not be "
                       f"parsed - refusing new risk until the book is legible")
    return True, "book reconciled"
