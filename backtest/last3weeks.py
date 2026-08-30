"""The last three weeks, every sleeve, rendered as the live dashboard.

WEEKS: Mon→Fri entries ending on the last completed session (2026-08-28).

SLEEVES, at the team allocation:
  options  $30,000 risk   iron condors, 11 DTE, delta 0.20, gate-floor credit
  stocks   $60,000        covered calls, IV = 1.20 x realized
  crypto   $10,000        spot, equal-weight across the listed pairs

Prices are real. Fills are modelled: condor credit sits at the gate's MINIMUM,
so a real fill at or above it does better. Nothing here was traded.
"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from math import exp, log, sqrt
from statistics import stdev
from datetime import date, datetime, timedelta
from bs import call as bs_call, condor_value, implied_vol
from deltax.gates import CREDIT_DELTA_MULTIPLE, PORTFOLIO_RISK_PCT, PER_POSITION_RISK_PCT
from deltax.dashboard import render_backtest, GRN, RED, YEL, CYN, MAG

EQ=100_000.0
OPT_RISK=EQ*PORTFOLIO_RISK_PCT; PER_POS=EQ*PER_POSITION_RISK_PCT
STOCK_CAP, CRYPTO_CAP = 60_000.0, 10_000.0
DELTA, Z, DTE, LOOK, VRP = 0.20, 0.8416, 11, 20, 1.20
# 15+ names, because $30,000 at a $2,000 per-position cap CANNOT be deployed
# across fewer. Ten names left a third of the budget idle (E22).
OPT_NAMES=[("SPY",5.0),("QQQ",5.0),("IWM",2.0),("DIA",5.0),("XLF",1.0),
           ("XLE",1.0),("XLU",1.0),("XLP",1.0),("XLV",2.5),("XLI",2.5),
           ("XLK",5.0),("MA",5.0),("KO",1.0),("PG",2.5),("XOM",1.0),
           ("WMT",1.0),("V",5.0)]
# Deliberately disjoint from OPT_NAMES: holding a condor and a covered call on
# the SAME underlying stacks two short-call positions on one name.
STOCK_NAMES=["UNH","JNJ","HD","MSFT","AAPL","CVX"]
COINS=["BTC/USD","ETH/USD","SOL/USD","XRP/USD"]

def ebars(s):
    o=subprocess.run(["alpaca","data","bars","--symbol",s,"--timeframe","1Day",
        "--start","2026-05-01","--end","2026-08-28","--limit","500","--feed","iex","--quiet"],
        capture_output=True,text=True,env=os.environ)
    try: return json.loads(o.stdout).get("bars",[]) or []
    except Exception: return []

def cbars(s):
    o=subprocess.run(["alpaca","data","crypto","bars","--symbols",s,"--timeframe","1Day",
        "--start","2026-05-01","--end","2026-08-28","--limit","500","--quiet"],
        capture_output=True,text=True,env=os.environ)
    try: return (json.loads(o.stdout).get("bars") or {}).get(s,[]) or []
    except Exception: return []

def rv(c,i,ann=252,n=LOOK):
    return stdev([log(c[j]/c[j-1]) for j in range(i-n+1,i+1)])*sqrt(ann)

def idx_of(bars, d):
    for i,b in enumerate(bars):
        if b["t"][:10]==d.isoformat(): return i
    return None

def classify(pnl, kept, breached, kind="condor"):
    """A breach means opposite things by structure. For a CONDOR it is the loss
    case. For a COVERED CALL it means the stock was called away - the gain is
    capped, not lost. Colouring both red misreads a profit as a failure."""
    if breached and kind == "condor":  return "🔴","breached",RED
    if breached and kind == "covered": return "🔒","called away",CYN
    if kept is not None and kept>=0.50: return "💰","target hit",GRN
    if pnl>0:               return "🟢","profit",GRN
    if pnl==0:              return "⚪","flat",""
    return "🟡","loss",YEL

def main():
    eq={s:ebars(s) for s,_ in OPT_NAMES}
    for s in STOCK_NAMES:
        if s not in eq: eq[s]=ebars(s)
    cr={s:cbars(s) for s in COINS}
    ref=eq["SPY"]
    if not ref: print("no data"); return 1
    # last three Monday→Friday windows ending on the final session
    mons=[i for i,b in enumerate(ref)
          if datetime.fromisoformat(b["t"].replace("Z","+00:00")).weekday()==0]
    mons=[i for i in mons if i+4 < len(ref)][-3:]

    per_name=OPT_RISK/len(OPT_NAMES)
    stock_each=STOCK_CAP/len(STOCK_NAMES)
    coin_each=CRYPTO_CAP/max(1,len([c for c in cr.values() if c]))
    weeks=[]
    deployed=[0.0]
    for mi in mons:
        d_in=date.fromisoformat(ref[mi]["t"][:10]); d_out=date.fromisoformat(ref[mi+4]["t"][:10])
        rows=[]; sl={"options":0.0,"stocks":0.0,"crypto":0.0}

        for sym,W in OPT_NAMES:
            b=eq.get(sym) or []
            i=idx_of(b,d_in)
            if i is None or i<LOOK+1 or i+4>=len(b): continue
            c=[x["c"] for x in b]; s0=c[i]; sig=rv(c,i)
            if sig<=0: continue
            T0=DTE/365.0; mv=Z*sig*sqrt(T0); kp,kc=s0*exp(-mv),s0*exp(mv)
            cred=2.0*CREDIT_DELTA_MULTIPLE*DELTA*W
            iv=implied_vol(cred,s0,kp,kc,W,T0)
            if iv is None: continue
            maxloss=(W-cred)*100.0
            n=max(1,int(min(per_name,PER_POS)//maxloss))
            deployed[0]+=n*maxloss
            out=condor_value(c[i+4],kp,kc,W,max(DTE-4,0.2)/365.0,iv)
            pnl=(cred-out)*100.0*n; kept=(cred-out)/cred
            br=not (kp<=c[i+4]<=kc)
            e,l,col=classify(pnl,kept,br)
            sl["options"]+=pnl
            rows.append(dict(sym=sym,sleeve=f"options x{n}",
                struct=f"condor {kp:.0f}/{kc:.0f}",entry=cred,exit=out,
                pnl=pnl,kept=kept,emoji=e,label=l,colour=col))

        for sym in STOCK_NAMES:
            b=eq.get(sym) or []
            i=idx_of(b,d_in)
            if i is None or i<LOOK+1 or i+4>=len(b): continue
            c=[x["c"] for x in b]; s0,s1=c[i],c[i+4]; sig=rv(c,i)
            if sig<=0: continue
            T0=DTE/365.0; k=s0*exp(Z*sig*sqrt(T0)); sh=stock_each/s0
            prem=bs_call(s0,k,T0,sig*VRP); back=bs_call(s1,k,max(DTE-4,0.2)/365.0,sig*VRP)
            pnl=(s1-s0)*sh+(prem-back)*sh
            e,l,col=classify(pnl,None,s1>k,kind="covered")
            sl["stocks"]+=pnl
            rows.append(dict(sym=sym,sleeve="cov call",struct=f"own+short {k:.0f}c",
                entry=s0,exit=s1,pnl=pnl,kept=None,emoji=e,label=l,colour=col))

        for sym,b in cr.items():
            if not b: continue
            i=idx_of(b,d_in)
            if i is None or i+4>=len(b): continue
            c=[x["c"] for x in b]
            pnl=(c[i+4]/c[i]-1.0)*coin_each
            e,l,col=classify(pnl,None,False)
            sl["crypto"]+=pnl
            rows.append(dict(sym=sym.split("/")[0],sleeve="spot",struct="long",
                entry=c[i],exit=c[i+4],pnl=pnl,kept=None,emoji=e,label=l,colour=col))

        weeks.append(dict(entry=d_in,exit=d_out,rows=rows,sleeves=sl,
                          total=sum(sl.values())))
        used=deployed[0]; deployed[0]=0.0
        weeks[-1]["deployed"]=used

    print(render_backtest(weeks,
        title=f"DELTAX BACKTEST · last {len(weeks)} weeks · all sleeves",
        assumptions=[
          f"options ${OPT_RISK:,.0f} risk / {len(OPT_NAMES)} names, credit at the GATE FLOOR "
          f"({CREDIT_DELTA_MULTIPLE} x delta x width) - real fills would do better",
          f"stocks ${STOCK_CAP:,.0f} covered calls, IV = {VRP} x realized (conservative end of measured VRP)",
          f"crypto ${CRYPTO_CAP:,.0f} spot, equal weight, NO options exist on this venue",
          "4-day Mon->Fri hold; no commissions or slippage charged",
          "implied vol held constant entry to exit - a vol spike would hurt the condors",
          "options and covered-call sleeves use DISJOINT underlyings - no doubled short calls",
        ]))
    return 0

if __name__ == "__main__":
    sys.exit(main())
