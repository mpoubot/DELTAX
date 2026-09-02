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
from deltax.gates import DEMONSTRATION_MODE, demo_cap, demo_permits
from deltax.manage import place_exit
from deltax.reconcile import reconcile, safe_to_open
from deltax import report
from deltax import news_gate
from deltax import gamma as gamma_mod
from deltax.manage import manage, Managed
from deltax import blocklist
from deltax.feeds import AlpacaFeed
from deltax.ledger import Ledger
from deltax.screener import (
    directional_bias,INCOME_UNIVERSE, DEFAULT_WIDTH, TARGET_DELTA_BY_WEAK,
                             rank_by_vol_premium, vol_premium,
                             assess_regime, select_vertical, choose_expiry,
                             BENCHMARKS)
from deltax.gates import evaluate, MIN_DTE, MAX_DTE

# E50: four concurrent positions, chosen from eight ranked candidates. E44
# measured that a capped-payoff short-premium book gets WORSE with more names -
# each one adds breach risk without adding upside - so the cap holds the tail
# while the ranking improves what fills it.
MAX_CONCURRENT = 4


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
    # Never search past the contest close. choose_expiry takes the nearest
    # qualifying expiry, so an unbounded window finds Sep 11 or Sep 18, builds a
    # candidate, and only then has it refused by gate_contest_window - a wasted
    # chain query and a refusal that reads like a data problem (E41).
    from deltax.gates import CONTEST_CLOSE as _CC
    _far = today.fromordinal(today.toordinal() + MAX_DTE)
    lte = str(min(_far, _CC))

    # What do we ALREADY hold? Without this, every cycle believes the book is
    # empty and re-opens the same positions - 96 times a day on the live
    # schedule. The risk cap only means something across cycles if committed
    # risk is seeded from the broker, not from this run's fills.
    try:
        # Positions AND working orders — an unfilled order is still risk (E36).
        book = reconcile(feed.positions(), feed.open_orders())
    except Exception as e:
        ledger.record_raw({"action": "reconcile_failed", "error": str(e)[:200]})
        return {"regime": regime, "traded": [], "refused": [], "committed": 0.0,
                "permission": perm.state, "advisory_only": False,
                "skipped": f"cannot read open positions - refusing to trade blind: {e}"}
    ok, why = safe_to_open(book)
    ledger.record_raw({"action": "reconcile", "open_positions": book["count"],
                       "working_orders": book.get("pending_orders", 0),
                       "committed": round(book["committed"], 2),
                       "held": sorted(f"{u}/{s_}" for u, s_ in book["held"]),
                       "safe_to_open": ok, "note": why})
    if not ok:
        return {"regime": regime, "traded": [], "refused": [],
                "committed": book["committed"], "permission": perm.state,
                "advisory_only": False, "skipped": why}

    # Exits run BEFORE entries every cycle. Closing a position frees risk budget
    # the gates would otherwise refuse the next candidate for, so an entry-first
    # order silently caps the book at whatever was opened earliest (E39).
    swept = {"closed": [], "held": [], "unpriceable": []}
    try:
        live = []
        for p_ in feed.positions():
            try:
                q = int(float(p_.get("qty") or 0))
                if q >= 0:
                    continue                      # short leg carries the position
                live.append(Managed(symbol=p_.get("symbol", "?"), qty=abs(q),
                                    entry_credit=abs(float(p_.get("avg_entry_price") or 0)),
                                    current=abs(float(p_.get("current_price") or 0)) or None,
                                    dte=None))
            except (TypeError, ValueError):
                continue
        if live:
            swept = manage(live, ledger=ledger, dry_run=dry_run)
    except Exception as e:
        ledger.record_raw({"action": "exit_sweep_failed", "error": str(e)[:160]})

    committed, traded, refused = book["committed"], [], []
    held = book["held"]
    # Earnings blocklist, built once in pre-market. Read here rather than
    # queried, so a SEC timeout can never sit inside the trading loop (E32).
    bl = blocklist.load()
    ledger.record_raw({"action": "earnings_blocklist",
                       "present": bl is not None,
                       "age_hours": round(blocklist.age_hours(bl), 2) if bl else None,
                       "blocked": len((bl or {}).get("blocked") or {}),
                       "clear": len((bl or {}).get("clear") or [])})
    exits_placed = []
    news_checked = {}      # symbol -> verdict, one fetch per name per cycle

    # E50: richest variance premium first. run.py used to walk the list in the
    # order it was typed and stop at the cap, so capital went to whichever name
    # came first rather than whichever paid most. Advisory only - every gate
    # still runs on every candidate, and an unmeasurable name keeps its place.
    from deltax.feeds import latest_price as _px
    from deltax.gates import CONTEST_CLOSE as _RANK_EXPIRY
    try:
        _spots = {s: _px(feed.snapshots([s]).get(s) or {}) for s in INCOME_UNIVERSE}
        _ordered = rank_by_vol_premium(feed, INCOME_UNIVERSE,
                                       str(_RANK_EXPIRY), _spots)
    except Exception:
        _ordered = list(INCOME_UNIVERSE)

    for symbol in _ordered:
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
        # Dealer gamma regime. ADVISORY: it cannot be backtested with this data
        # (open interest has no as-of parameter), and E10 forbids an unvalidated
        # signal gating a trade. Measured, logged, displayed - never blocking.
        try:
            gch = feed.option_chain(symbol, expiry_gte=gte, expiry_lte=lte,
                                    strike_gte=round(px * 0.90, 2),
                                    strike_lte=round(px * 1.10, 2))
            gcs = feed.option_contracts(symbol, expiry_gte=gte, expiry_lte=lte,
                                        strike_gte=round(px * 0.90, 2),
                                        strike_lte=round(px * 1.10, 2), limit=1000)
            gmap = gamma_mod.build(symbol, px,
                                   gch, {c["symbol"]: c.get("open_interest") for c in gcs})
            _, gwhy = gamma_mod.gate_gamma_regime(gmap, require_positive=False)
            ledger.record_raw({"action": "gamma_regime", "symbol": symbol,
                               "regime": gmap.regime, "net_gex": round(gmap.total, 0),
                               "pin": gmap.pin, "flip": gmap.flip,
                               "advisory": True, "note": gwhy})
        except Exception as e:
            ledger.record_raw({"action": "gamma_failed", "symbol": symbol,
                               "error": str(e)[:120]})

        # One earnings decision per symbol, before either side is considered.
        ok_earn, why_earn = blocklist.check(symbol, date.fromisoformat(
            (lte if isinstance(lte, str) else str(lte))), bl)
        if not ok_earn:
            refused.append((symbol, "both", "earnings"))
            continue

        for side, lo, hi in (("put", 0.80, 1.02), ("call", 0.98, 1.20)):
            if (symbol, side) in held:
                refused.append((symbol, side, "already_held"))
                continue
            allowed, why = gate_permission(perm, side)
            # E57: DEMONSTRATION_MODE may proceed through DEFENSIVE - a
            # directional caution - because size is capped at one contract.
            # It may never proceed through HALT or NO_NEW_POSITIONS, which mean
            # broken data or a breached loss limit, not a view on direction.
            if not allowed and DEMONSTRATION_MODE and demo_permits(perm.state):
                allowed = True
                why = f"demo override of {perm.state} at capped size (E57)"
                ledger.record_raw({"action": "demo_permission_override",
                                   "symbol": symbol, "side": side,
                                   "state": perm.state, "reason": why})
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
            # LAST gate before real money: read the tape for THIS name only.
            # Runs here, not earlier, so it screens the handful that survived 13
            # gates rather than the whole universe (E35).
            if symbol not in news_checked:
                news_checked[symbol] = news_gate.screen(symbol)
                ledger.record_raw({"action": "news_gate", "symbol": symbol,
                                   "allowed": news_checked[symbol]["allowed"],
                                   "read": news_checked[symbol]["read"],
                                   "recent": news_checked[symbol]["recent"],
                                   "reachable": news_checked[symbol]["reachable"],
                                   "reason": news_checked[symbol]["reason"]})
            nv = news_checked[symbol]
            if not nv["allowed"]:
                refused.append((symbol, side, "news"))
                continue

            # E57: hard ceiling applied AFTER every risk calculation, so it can
            # only ever reduce size, never raise it.
            qty = demo_cap(dec.contracts)
            if qty != dec.contracts:
                ledger.record_raw({"action": "demo_size_cap", "symbol": symbol,
                                   "side": side, "sized": dec.contracts,
                                   "capped_to": qty, "reason": "E57"})
            try:
                rec = execute.submit(legs, qty, cand["credit"],
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
                ex = place_exit(legs, qty, cand["credit"],
                                ledger=ledger, dry_run=dry_run)
                exits_placed.append((symbol, side, ex.get("limit_price")))
            # Risk actually committed follows the CAPPED size, not the sized
            # quantity, or the book would reserve budget it never spent.
            committed += dec.max_loss * (qty / dec.contracts if dec.contracts else 1)
            traded.append((symbol, f"{side}/{bias}", qty, cand["credit"],
                           dec.max_loss, rec["result"]))
    return {"regime": regime, "traded": traded, "refused": refused,
            "committed": committed, "skipped": None,
            "permission": perm.state, "advisory_only": perm_override,
            "book": book, "exits": exits_placed, "swept": swept}


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
        # Even a skipped cycle narrates: account state, why, and what it holds.
        try:
            acct = feed.account()
            eq, csh = float(acct.get("equity") or 0), float(acct.get("cash") or 0)
        except Exception:
            eq = csh = 0.0
        print(report.render(equity=eq, cash=csh,
                            market_open=bool(feed.clock().get("is_open")),
                            regime=getattr(out.get("regime"), "note", "—"),
                            permission=out.get("permission", "—"),
                            events=[("refuse", "CYCLE", out["skipped"])]))
        sys.exit(0)

    try:
        acct = feed.account()
        eq, csh = float(acct.get("equity") or 0), float(acct.get("cash") or 0)
    except Exception:
        eq = csh = 0.0
    r = out["regime"]
    events = [("open", sym, f"OPENED {side} · {ct} ct · credit ${cr*100*ct:,.0f} → {res}")
              for sym, side, ct, cr, ml, res in out["traded"]]
    events += [("exit", sym, f"EXIT RESTING at {lim:.2f} (50% of credit) · fills unattended")
               for sym, side, lim in out.get("exits", []) if lim]
    print(report.render(
        equity=eq, cash=csh, market_open=True,
        unrealized=0.0, realized=0.0,
        positions=[], events=events, refused=out["refused"],
        regime=f"{r.weak_count}/3 weak", permission=out.get("permission", "—")))
