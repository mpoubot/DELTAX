"""Scheduled signal check: decide whether new entries may be permitted.

Run every 15 minutes by bin/unfreeze-check.sh. Reads the live book, prices it
through the judging deadline with the regime-mixture engine, evaluates every
signal, and rewrites state/freeze.json.

It never places an order and never touches a position. Its only side effect is
one small JSON file, written atomically.

Fail closed everywhere: if the account cannot be read, the engine cannot price,
or anything raises, it writes FROZEN with the reason.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from math import sqrt
import json
import subprocess
import sys

from deltax import freeze as fz
from deltax import quantum_catalyst as qc
from deltax.reconcile import parse_occ, reconcile
from deltax import feeds as _feeds

PORTFOLIO_CAP = 30_000.0


def _cli(*args) -> list:
    out = subprocess.run(["alpaca"] + list(args) + ["--quiet"],
                         capture_output=True, text=True, timeout=45)
    return json.loads(out.stdout) if out.stdout.strip() else []


def _solve_iv(S, K, T, mark, right) -> float:
    """Implied vol from the broker's own mark. Never realized vol - pricing a
    live book at realized vol overstated every spread here by $0.40-$1.77."""
    lo, hi = 0.01, 3.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if qc.bs_price(S, K, T, 0.04, mid, right) < mark:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _simulate_book(cands: list, now: datetime, n: int = 8000,
                   seed: int = 95, rho: float = 0.75) -> list:
    """One market, many underlyings. Returns book P&L from NOW to the deadline.

    Each path draws one regime and one MARKET shock shared by every underlying,
    plus an idiosyncratic shock per name, combined at correlation `rho`. Index
    ETFs on the same session are strongly co-moving - treating them as
    independent would understate the joint tail, and simply adding up separate
    per-structure tails overstates it.
    """
    import random as _r
    from math import exp as _exp, sqrt as _sqrt
    horizon = (qc.JUDGING_DEADLINE - now.astimezone(fz.ET)).total_seconds()
    hy = max(horizon, 1.0) / (365.0 * 24 * 3600)
    probs = qc.regime_probabilities(qc.MarketEvidence(evidence_confidence=0.5))
    cum, acc = [], 0.0
    for reg in qc.REGIMES:
        acc += probs[reg.name]
        cum.append(acc)
    names = sorted({c.underlying for c in cands})
    base_iv = {}
    for c in cands:
        ivs = sorted(l.iv for l in c.legs)
        base_iv.setdefault(c.underlying, []).append(ivs[len(ivs) // 2])
    iv_of = {u: sum(v) / len(v) for u, v in base_iv.items()}
    now_val = sum(l.current_price * l.quantity * c.multiplier
                  for c in cands for l in c.legs)
    rng = _r.Random(seed)
    out = []
    for _ in range(n):
        u_ = rng.random() * cum[-1]
        i = 0
        while i < len(cum) - 1 and u_ > cum[i]:
            i += 1
        reg = qc.REGIMES[i]
        z_mkt = rng.gauss(0.0, 1.0)
        spots = {}
        for u in names:
            z_idio = rng.gauss(0.0, 1.0)
            z = rho * z_mkt + _sqrt(max(1.0 - rho * rho, 0.0)) * z_idio
            sig = iv_of[u] * reg.vol_multiplier
            S0 = next(c.spot for c in cands if c.underlying == u)
            spots[u] = S0 * _exp((reg.drift_annual - 0.5 * sig * sig) * hy
                                 + sig * _sqrt(hy) * z)
        fut = 0.0
        for c in cands:
            for l in c.legs:
                fut += qc.option_value_at_deadline(
                    l, spots[c.underlying], qc.JUDGING_DEADLINE, 0.04,
                    reg.vol_multiplier) * l.quantity * c.multiplier
        out.append(fut - now_val)
    return out


def run() -> dict:
    now = datetime.now(fz.ET)
    try:
        acct = _cli("account", "get")
        pos = _cli("position", "list")
        orders = _cli("order", "list", "--status", "open")
        equity = float(acct["equity"])
    except Exception as e:
        return fz.write_state(True,
                              f"account unreadable ({type(e).__name__}) - failing closed")

    book = reconcile(pos, orders)
    feed = _feeds.AlpacaFeed()

    # E99: price the CURRENT book through the deadline JOINTLY.
    #
    # The first version summed calculate_edge_score() across structures. That
    # function is a CANDIDATE RANKER - it subtracts 0.20 x contractual max loss
    # to punish fat-tailed structures - so summing it over a book of seven
    # credit spreads gives about -8,300 no matter how the market behaves. The
    # signal could never pass, which makes it a second freeze wearing the
    # costume of a signal.
    #
    # A book is judged on two things instead: is it expected to MAKE money
    # through judging, and is its bad case survivable. Both are measured on ONE
    # joint simulation - the same market shock applied to every underlying,
    # plus an idiosyncratic part - because adding up seven separate 5% tails
    # assumes all seven crater on the same day, which overstates the tail badly
    # and would again freeze forever for the wrong reason.
    exp_total = score_total = 0.0
    engine_ok = True
    forecast = None
    try:
        structs = {}
        for p in pos:
            occ = parse_occ(p["symbol"])
            if occ is None:
                continue
            structs.setdefault(
                (occ["underlying"], occ["right"], occ["expiry"]), []).append(
                (p["symbol"], occ["strike"], occ["right"], int(float(p["qty"])),
                 abs(float(p["avg_entry_price"])),
                 abs(float(p.get("current_price") or 0))))
        unds = sorted({k[0] for k in structs})
        snaps = feed.snapshots(unds) if unds else {}
        spot = {u: _feeds.latest_price(snaps.get(u) or {}) for u in unds}
        cands = []
        for (u, r, e), legs in structs.items():
            S = spot.get(u)
            if not S:
                engine_ok = False
                break
            expd = datetime(2000 + int(e[:2]), int(e[2:4]), int(e[4:6]),
                            16, 0, tzinfo=fz.ET)
            T = max((expd - now).total_seconds() / (365 * 24 * 3600), 1e-6)
            ol = []
            for sym, K, right, q, ent, cur in legs:
                ol.append(qc.OptionLeg(sym, K, right, q, expd,
                                       _solve_iv(S, K, T, max(cur, 0.01), right),
                                       ent, cur))
            cands.append(qc.Candidate(f"{u}-{r}-{e}", u, S, tuple(ol)))
        if engine_ok and cands:
            book_pnl = _simulate_book(cands, now)
            stats = qc.summarize_distribution(book_pnl)
            exp_total = stats["expected_pnl"]
            score_total = stats["cvar05"]        # expected shortfall, joint
            # E100: keep the whole forecast, not just the two numbers the
            # signals need. The board asks what we EXPECT at judging and how
            # confident that is; recomputing it there would run the simulation
            # on every 3-minute publish for a figure this job already has.
            forecast = {
                "expected_pnl": round(stats["expected_pnl"], 2),
                "median_pnl": round(stats["median_pnl"], 2),
                "probability_gain": round(stats["probability_gain"], 4),
                "p05": round(stats["p05"], 2),
                "cvar05": round(stats["cvar05"], 2),
                "paths": len(book_pnl),
                "structures": len(cands),
            }
    except Exception as e:
        engine_ok = False
        exp_total = score_total = 0.0
        _err = f"{type(e).__name__}: {str(e)[:80]}"
    else:
        _err = None

    res = fz.evaluate_signals(
        equity=equity, committed=book["committed"], portfolio_cap=PORTFOLIO_CAP,
        unparsed=book.get("unparsed") or [], equities=book.get("equities") or [],
        sweep_failed=[], now=now,
        engine_expected_pnl=exp_total if engine_ok else None,
        engine_score=score_total if engine_ok else None)

    # E98: `frozen` is the INVERSE of `unfreeze`. Passing res["unfreeze"]
    # straight into write_state(frozen=...) inverted the polarity, so a check
    # with a FAILING signal wrote frozen=False and authorised new entries - a
    # fail-OPEN, in the one place that must fail closed. Named explicitly here
    # so the two words can never be transposed again.
    should_unfreeze = bool(res["unfreeze"])
    frozen = not should_unfreeze
    if should_unfreeze:
        reason = ("all signals pass - new entries permitted until the next "
                  "check re-evaluates them")
    else:
        reason = "frozen: " + "; ".join(
            f"{k} ({res['signals'][k]['detail']})" for k in res["failed"])
    if _err:
        reason += f" | engine error {_err}"
        frozen = True                    # an engine error can only ever freeze
    if forecast:
        res["forecast"] = forecast
    return fz.write_state(frozen, reason, res)


if __name__ == "__main__":
    st = run()
    print(json.dumps(st, indent=1, sort_keys=True))
    sys.exit(0)
