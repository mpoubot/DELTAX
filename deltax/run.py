"""End-to-end strategy run: screen -> gate -> log -> execute (dry by default).

This is the whole agent in one entry point. Direction-neutral income core per
E11/E12; both sides of a condor are nominated and gated independently.

  python3 -m deltax.run             # dry run, nothing submitted
  python3 -m deltax.run --live      # requires DELTAX_ORDERS_ALLOWED=1 as well
"""

from datetime import date, datetime, timezone
import sys

from deltax import execute
from deltax.calendar import entry_allowed
from deltax.permission import Evidence, recommend_state, gate_permission
from deltax.manage import place_exit
from deltax.reconcile import reconcile, safe_to_open
from deltax.feeds import AlpacaFeed
from deltax.ledger import Ledger
from deltax.screener import (
    directional_bias,INCOME_UNIVERSE, DEFAULT_WIDTH, TARGET_DELTA_BY_WEAK,
                             assess_regime, select_vertical, choose_expiry,
                             BENCHMARKS)
from deltax.gates import evaluate, MIN_DTE, MAX_DTE

MAX_CONCURRENT = 5          # E12: satellite budget redeployed to income


def run(feed, ledger, *, equity: float, today: date, dry_run: bool = True,
        force_window: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    # --force is an ANALYSIS switch: it relaxes the calendar window and the
    # permission state so the pipeline can be exercised outside session
    # hours. It is inert whenever real orders are possible.
    analysis = force_window and dry_run
    clock = feed.clock()
    allowed, why = entry_allowed(now, bool(clock.get("is_open")))
    if not allowed and not analysis:
        ledger.record_raw({"action": "skip", "reason": why})
        return {"traded": [], "refused": [], "skipped": why}

    snaps = feed.snapshots(BENCHMARKS)
    regime = assess_regime(snaps)
    target = TARGET_DELTA_BY_WEAK[min(regime.weak_count, 3)]

    # Global permission sits ABOVE strategy - no candidate can override it.
    perm = recommend_state(Evidence(
        benchmarks_weak=regime.weak_count,
        data_stale=not regime.complete,
        market_open=bool(clock.get("is_open")),
        drawdown_pct=0.0,
    ))
    # --force is an ANALYSIS switch. It may relax permission only while
    # dry-running; with real orders enabled the state is absolute.
    perm_override = analysis
    ledger.record_raw({"action": "permission", "state": perm.state,
                       "reasons": perm.reasons, "overridden": perm_override})
    if perm.policy["size_factor"] <= 0 and not perm_override:
        return {"regime": regime, "traded": [], "refused": [], "committed": 0.0,
                "permission": perm.state, "advisory_only": False,
                "skipped": f"{perm.state}: {perm.reasons[0]}"}

    gte = str(today.fromordinal(today.toordinal() + MIN_DTE))
    lte = str(today.fromordinal(today.toordinal() + MAX_DTE))

    # What do we ALREADY hold? Without this, every cycle believes the book is
    # empty and re-opens the same positions - 96 times a day on the live
    # schedule. The risk cap only means something across cycles if committed
    # risk is seeded from the broker, not from this run's fills.
    try:
        book = reconcile(feed.positions())
    except Exception as e:
        ledger.record_raw({"action": "reconcile_failed", "error": str(e)[:200]})
        return {"regime": regime, "traded": [], "refused": [], "committed": 0.0,
                "permission": perm.state, "advisory_only": False,
                "skipped": f"cannot read open positions - refusing to trade blind: {e}"}
    ok, why = safe_to_open(book)
    ledger.record_raw({"action": "reconcile", "open_positions": book["count"],
                       "committed": round(book["committed"], 2),
                       "held": sorted(f"{u}/{s_}" for u, s_ in book["held"]),
                       "safe_to_open": ok, "note": why})
    if not ok:
        return {"regime": regime, "traded": [], "refused": [],
                "committed": book["committed"], "permission": perm.state,
                "advisory_only": False, "skipped": why}

    committed, traded, refused = book["committed"], [], []
    held = book["held"]

    for symbol in INCOME_UNIVERSE:
        if len(traded) >= MAX_CONCURRENT:
            break
        spot = (feed.snapshots([symbol]).get(symbol) or {})
        from deltax.feeds import latest_price
        px = latest_price(spot)
        if not px:
            continue
        # E25: an instrument with clean history may not exist today. Age the
        # last bar and let gate_listed decide; unknown fails closed.
        bar_age = None
        db = spot.get("dailyBar") or {}
        if db.get("t"):
            try:
                bar_t = datetime.fromisoformat(str(db["t"]).replace("Z", "+00:00"))
                bar_age = (now - bar_t).total_seconds() / 86400.0
            except (ValueError, TypeError):
                bar_age = None
        # E11: no directional edge proven, so nominate BOTH sides.
        for side, lo, hi in (("put", 0.80, 1.02), ("call", 0.98, 1.20)):
            if (symbol, side) in held:
                refused.append((symbol, side, "already_held"))
                continue
            allowed, why = gate_permission(perm, side)
            if not allowed and not perm_override:
                refused.append((symbol, side, f"permission:{perm.state}"))
                continue
            klo, khi = round(px*lo, 2), round(px*hi, 2)
            picked = choose_expiry(feed, symbol, side, gte, lte, klo, khi)
            if not picked:
                continue
            expiry_str, oi = picked
            # One expiry per query - the endpoint pages by expiry then strike.
            chain = feed.option_chain(symbol, option_type=side,
                                      expiry_gte=expiry_str, expiry_lte=expiry_str,
                                      strike_gte=klo, strike_lte=khi)
            if not chain:
                continue
            cand = select_vertical(chain, side=side, target_delta=target,
                                   width=DEFAULT_WIDTH.get(symbol, 5.0),
                                   oi_by_symbol=oi)
            if not cand:
                continue
            dec = evaluate(
                symbol=symbol, equity=equity,
                max_loss_per_contract=cand["max_loss_per_contract"],
                max_profit_per_contract=cand["max_profit_per_contract"],
                credit=cand["credit"], expiry=date.fromisoformat(cand["expiry"]),
                today=today, open_interest=cand["open_interest"],
                open_portfolio_max_loss=committed, structure="credit",
                width=cand["width"], short_delta=cand["short"]["delta"],
                worst_leg_spread_pct=cand["worst_leg_spread_pct"],
                tradable=True, last_bar_age_days=bar_age, asset_class="equity")
            bias, bias_icon, bias_note = directional_bias(side, "credit")
            ledger.record(dec, context={
                "book": "income", "side": side, "regime": regime.note,
                # bias is the DIRECTION expressed. short_leg/long_leg are the
                # spread's legs. Both used to be called "short"/"long", which
                # made the ledger unreadable on exactly the question the team
                # asked: which way are we leaning?
                "bias": bias, "bias_note": bias_note,
                "short_leg": cand["short"]["strike"],
                "long_leg": cand["long"]["strike"],
                "delta": round(cand["short"]["delta"], 4),
                "credit": round(cand["credit"], 2)})
            if dec.decision != "TRADE":
                refused.append((symbol, side, dec.failed_gate))
                continue
            legs = [execute.Leg(cand["short"]["symbol"], "sell"),
                    execute.Leg(cand["long"]["symbol"], "buy")]
            try:
                rec = execute.submit(legs, dec.contracts, cand["credit"],
                                     dry_run=dry_run,
                                     context={"symbol": symbol, "side": side})
            except Exception as e:
                # One rejected order must not kill the loop. Record it, skip
                # this candidate, keep the rest of the book intact.
                ledger.record_raw({"action": "submit_failed", "symbol": symbol,
                                   "side": side, "error": f"{type(e).__name__}: {str(e)[:160]}"})
                refused.append((symbol, side, "submit_failed"))
                continue
            ledger.record_raw(rec)
            # E5/E15: the exit is placed AT ENTRY, not watched for later. An
            # exit that needs the agent alive at the right minute is not an
            # exit — and the 50% close is where the measured edge lives.
            if str(rec.get("result", "")).startswith(("SUBMITTED", "DRY_RUN")):
                place_exit(legs, dec.contracts, cand["credit"],
                           ledger=ledger, dry_run=dry_run)
            committed += dec.max_loss
            traded.append((symbol, f"{side}/{bias}", dec.contracts, cand["credit"],
                           dec.max_loss, rec["result"]))
    return {"regime": regime, "traded": traded, "refused": refused,
            "committed": committed, "skipped": None,
            "permission": perm.state, "advisory_only": perm_override}


if __name__ == "__main__":
    live = "--live" in sys.argv
    if live and "--force" in sys.argv:
        sys.exit("REFUSED: --force is an analysis switch and cannot be "
                 "combined with --live. Trade permission is absolute for "
                 "real orders.")
    feed, led = AlpacaFeed(), Ledger("logs")
    out = run(feed, led, equity=100_000.0, today=date.today(),
              dry_run=not live, force_window="--force" in sys.argv)
    if out.get("skipped"):
        print(f"SKIPPED: {out['skipped']}")
        sys.exit(0)
    r = out["regime"]
    print(f"regime {r.weak_count}/3 weak {r.weak_symbols}")
    print(f"permission: {out['permission']}")
    if out.get("advisory_only"):
        print("*** ADVISORY ONLY - permission overridden for dry-run "
              "analysis. These are NOT tradeable decisions. ***")
    print()
    print(f"TRADED ({len(out['traded'])}):")
    for sym, side, n, cr, ml, res in out["traded"]:
        print(f"  {sym:5} {side:4} x{n:<3} credit ${cr:.2f}  max loss ${ml:>7,.0f}  {res}")
    print(f"\ncommitted max loss: ${out['committed']:,.0f}")
    print(f"REFUSED ({len(out['refused'])}): "
          f"{', '.join(f'{s}/{d}:{g}' for s, d, g in out['refused'][:12])}")
