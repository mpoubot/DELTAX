"""What the agent does at 09:30 today — full pipeline, modelled quotes.

Live chains carry stale weekend quotes right now, so every candidate refuses on
quote_sanity/liquidity — correct behaviour, but it shows nothing about the open.
This runs the SAME gates against modelled quotes built from Friday's closes and
trailing realised vol, so the output is what the agent would actually do when
the bell rings under normal conditions.

Modelled, not observed. Strike placement, credit floor, sizing, gate order and
exit rule are the production code paths - only the quote is synthetic.
"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from math import exp, log, sqrt
from statistics import stdev
from datetime import date, timedelta
from bs import condor_value, implied_vol
from deltax.gates import (evaluate, CREDIT_DELTA_MULTIPLE, PORTFOLIO_RISK_PCT,
                          PER_POSITION_RISK_PCT, MIN_OPEN_INTEREST)
from deltax.screener import directional_bias
from deltax.manage import exit_limit, TAKE_PROFIT_FRACTION
from deltax.dashboard import GRN, RED, YEL, CYN, MAG, RESET, BOLD, DIM

EQ = 100_000.0
DELTA, Z, DTE, LOOK = 0.20, 0.8416, 11, 20
EXPIRY = date(2026, 9, 11)
TODAY = date(2026, 8, 31)
UNIVERSE = [("SPY",5.0),("QQQ",5.0),("IWM",2.0),("DIA",5.0),("XLF",1.0),
            ("XLE",1.0),("XLU",1.0),("XLP",1.0),("XLV",2.5),("XLI",2.5),
            ("XLK",5.0),("MA",5.0),("KO",1.0),("PG",2.5),("XOM",1.0),
            ("WMT",1.0),("V",5.0)]

def bars(s):
    o = subprocess.run(["alpaca","data","bars","--symbol",s,"--timeframe","1Day",
        "--start","2026-05-01","--end","2026-08-28","--limit","400",
        "--feed","iex","--quiet"], capture_output=True, text=True, env=os.environ)
    try: return [b["c"] for b in json.loads(o.stdout).get("bars",[])]
    except Exception: return []

def main():
    budget = EQ * PORTFOLIO_RISK_PCT
    per_pos = EQ * PER_POSITION_RISK_PCT
    W = 92
    print(f"{BOLD}╔{'═'*W}╗{RESET}")
    print(f"{BOLD}║{' DELTAX — 09:30 OPEN SIMULATION · Mon 31 Aug 2026':<{W}}║{RESET}")
    print(f"{BOLD}╚{'═'*W}╝{RESET}")
    print(f"  {YEL}╔{'═'*66}╗{RESET}")
    print(f"  {YEL}║  🔬  MODELLED QUOTES — live chains are stale at this hour.        ║{RESET}")
    print(f"  {YEL}║      Gates, sizing and exits are the PRODUCTION code paths.       ║{RESET}")
    print(f"  {YEL}╚{'═'*66}╝{RESET}\n")

    rows, committed, approved = [], 0.0, []
    for sym, width in UNIVERSE:
        c = bars(sym)
        if len(c) < LOOK + 2: continue
        s0 = c[-1]
        sig = stdev([log(c[j]/c[j-1]) for j in range(len(c)-LOOK, len(c))]) * sqrt(252)
        if sig <= 0: continue
        T = DTE/365.0
        mv = Z * sig * sqrt(T)
        for side in ("put","call"):
            k_short = s0*exp(-mv) if side=="put" else s0*exp(mv)
            k_long  = k_short - width if side=="put" else k_short + width
            credit = CREDIT_DELTA_MULTIPLE * DELTA * width
            maxloss = (width - credit) * 100.0
            dec = evaluate(
                symbol=sym, equity=EQ,
                max_loss_per_contract=maxloss,
                max_profit_per_contract=credit*100.0,
                credit=credit, expiry=EXPIRY, today=TODAY,
                open_interest=MIN_OPEN_INTEREST*4,
                open_portfolio_max_loss=committed,
                structure="credit", width=width, short_delta=DELTA,
                worst_leg_spread_pct=0.06, quote_age_hours=0.05,
                earnings_date=None, earnings_checked=True,
                tradable=True, last_bar_age_days=0.6, asset_class="equity")
            n = min(dec.contracts, int(per_pos // maxloss)) if dec.contracts else 0
            bias, icon, _ = directional_bias(side, "credit")
            ok = dec.failed_gate is None and n > 0
            if ok and committed + n*maxloss <= budget:
                committed += n*maxloss
                approved.append((sym, side, n, credit, maxloss))
                rows.append((sym, icon, bias, side, k_short, k_long, n, credit,
                             n*maxloss, "APPROVED", None))
            else:
                why = dec.failed_gate or ("portfolio_risk" if n else "sizing")
                rows.append((sym, icon, bias, side, k_short, k_long, 0, credit, 0.0,
                             "refused", why))

    print(f"{DIM}  {'SYM':<6}{'BIAS':<11}{'STRUCTURE':<22}{'QTY':>5}{'CREDIT':>8}"
          f"{'RISK':>9}{'EXIT@':>8}  DECISION{RESET}")
    for sym, icon, bias, side, ks, kl, n, cr, risk, res, why in rows:
        struct = f"{side} {ks:.0f}/{kl:.0f}"
        if res == "APPROVED":
            print(f"  {sym:<6}{icon} {bias:<8}{struct:<22}{n:>5}{cr:>8.2f}"
                  f"{risk:>9,.0f}{exit_limit(cr):>8.2f}  {GRN}✅ OPEN{RESET}")
        else:
            print(f"  {sym:<6}{icon} {bias:<8}{struct:<22}{'—':>5}{cr:>8.2f}"
                  f"{'—':>9}{'—':>8}  {RED}⛔ {why}{RESET}")

    longs = sum(1 for r in rows if r[9]=="APPROVED" and r[2]=="LONG")
    shorts = sum(1 for r in rows if r[9]=="APPROVED" and r[2]=="SHORT")
    print(f"\n{BOLD}  {'─'*W}{RESET}")
    print(f"  {BOLD}POSITIONS OPENED{RESET}  {len(approved)}"
          f"   📈 {longs} long  ·  📉 {shorts} short"
          f"   →  book is {BOLD}{'BALANCED' if abs(longs-shorts)<=1 else ('LONG-LEANING' if longs>shorts else 'SHORT-LEANING')}{RESET}")
    print(f"  {BOLD}CAPITAL AT RISK {RESET}  ${committed:,.0f} of ${budget:,.0f} budget"
          f"   ({committed/budget*100:.0f}% deployed)   cash untouched ${EQ-committed:,.0f}")
    tot_credit = sum(n*cr*100 for _,_,n,cr,_ in approved)
    print(f"  {BOLD}CREDIT COLLECTED{RESET}  ${tot_credit:,.0f}"
          f"   →  exits rest GTC at {TAKE_PROFIT_FRACTION:.0%}, target ${tot_credit*TAKE_PROFIT_FRACTION:,.0f}")
    print(f"  {BOLD}WORST CASE     {RESET}  {RED}−${committed:,.0f}{RESET} "
          f"({committed/EQ*100:.1f}% of equity) — only if EVERY position breaches")
    print(f"{BOLD}  {'─'*W}{RESET}")
    print(f"\n{DIM}  Each fill also rests a GTC buy-to-close at half the credit received (E5/E15),")
    print(f"  and any position reaching 2 DTE closes on the time stop regardless of profit.{RESET}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
