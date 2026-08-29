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
from deltax.feeds import AlpacaFeed
from deltax.ledger import Ledger
from deltax.screener import (INCOME_UNIVERSE, DEFAULT_WIDTH, TARGET_DELTA_BY_WEAK,
                             assess_regime, select_vertical, choose_expiry,
                             BENCHMARKS)
from deltax.gates import evaluate, MIN_DTE, MAX_DTE

MAX_CONCURRENT = 5          # E12: satellite budget redeployed to income


def run(feed, ledger, *, equity: float, today: date, dry_run: bool = True,
        force_window: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    clock = feed.clock()
    allowed, why = entry_allowed(now, bool(clock.get("is_open")))
    if not allowed and not force_window:
        ledger.record_raw({"action": "skip", "reason": why})
        return {"traded": [], "refused": [], "skipped": why}

    snaps = feed.snapshots(BENCHMARKS)
    regime = assess_regime(snaps)
    target = TARGET_DELTA_BY_WEAK[min(regime.weak_count, 3)]

    gte = str(today.fromordinal(today.toordinal() + MIN_DTE))
    lte = str(today.fromordinal(today.toordinal() + MAX_DTE))
    committed, traded, refused = 0.0, [], []

    for symbol in INCOME_UNIVERSE:
        if len(traded) >= MAX_CONCURRENT:
            break
        spot = (feed.snapshots([symbol]).get(symbol) or {})
        from deltax.feeds import latest_price
        px = latest_price(spot)
        if not px:
            continue
        # E11: no directional edge proven, so nominate BOTH sides.
        for side, lo, hi in (("put", 0.80, 1.02), ("call", 0.98, 1.20)):
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
                worst_leg_spread_pct=cand["worst_leg_spread_pct"])
            ledger.record(dec, context={
                "book": "income", "side": side, "regime": regime.note,
                "short": cand["short"]["strike"], "long": cand["long"]["strike"],
                "delta": round(cand["short"]["delta"], 4),
                "credit": round(cand["credit"], 2)})
            if dec.decision != "TRADE":
                refused.append((symbol, side, dec.failed_gate))
                continue
            legs = [execute.Leg(cand["short"]["symbol"], "sell"),
                    execute.Leg(cand["long"]["symbol"], "buy")]
            rec = execute.submit(legs, dec.contracts, cand["credit"],
                                 dry_run=dry_run,
                                 context={"symbol": symbol, "side": side})
            ledger.record_raw(rec)
            committed += dec.max_loss
            traded.append((symbol, side, dec.contracts, cand["credit"],
                           dec.max_loss, rec["result"]))
    return {"regime": regime, "traded": traded, "refused": refused,
            "committed": committed, "skipped": None}


if __name__ == "__main__":
    live = "--live" in sys.argv
    feed, led = AlpacaFeed(), Ledger("logs")
    out = run(feed, led, equity=100_000.0, today=date.today(),
              dry_run=not live, force_window="--force" in sys.argv)
    if out.get("skipped"):
        print(f"SKIPPED: {out['skipped']}")
        sys.exit(0)
    r = out["regime"]
    print(f"regime {r.weak_count}/3 weak {r.weak_symbols}\n")
    print(f"TRADED ({len(out['traded'])}):")
    for sym, side, n, cr, ml, res in out["traded"]:
        print(f"  {sym:5} {side:4} x{n:<3} credit ${cr:.2f}  max loss ${ml:>7,.0f}  {res}")
    print(f"\ncommitted max loss: ${out['committed']:,.0f}")
    print(f"REFUSED ({len(out['refused'])}): "
          f"{', '.join(f'{s}/{d}:{g}' for s, d, g in out['refused'][:12])}")
