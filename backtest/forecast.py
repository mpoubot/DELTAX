"""Outcome DISTRIBUTION for the coming week. Not a prediction of direction.

What this is NOT: a forecast that the market goes up or down. We tested five
directional strategies and all five failed (E11/E21). Nothing here claims to
know Friday's price.

What this IS: the book we intend to hold, run over every historical Mon->Fri
window available, producing the empirical distribution of outcomes. The claim
is "weeks like this one have landed here", not "this week will land here".

Conditioning: the current volatility regime is reported, and a matched subset
of history at a similar regime is shown alongside the unconditional spread,
because a condor's payoff depends on realized vol relative to what was priced.
"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from math import exp, log, sqrt
from statistics import mean, median, stdev
from datetime import datetime
from bs import call as bs_call, condor_value, implied_vol
from deltax.gates import CREDIT_DELTA_MULTIPLE, PORTFOLIO_RISK_PCT, PER_POSITION_RISK_PCT
from deltax.permission import DAILY_LOSS_LIMIT_PCT

EQ=100_000.0
OPT_RISK=EQ*PORTFOLIO_RISK_PCT; PER_POS=EQ*PER_POSITION_RISK_PCT
STOCK_CAP, CRYPTO_CAP = 60_000.0, 10_000.0
DELTA,Z,DTE,HOLD,LOOK,VRP = 0.20,0.8416,11,4,20,1.20
OPT=[("SPY",5.0),("QQQ",5.0),("IWM",2.0),("DIA",5.0),("XLF",1.0),("XLE",1.0),
     ("XLU",1.0),("XLP",1.0),("XLV",2.5),("XLI",2.5),("XLK",5.0),("MA",5.0),
     ("KO",1.0),("PG",2.5),("XOM",1.0),("WMT",1.0),("V",5.0)]
STK=["UNH","JNJ","HD","MSFT","AAPL","CVX"]

def bars(s):
    o=subprocess.run(["alpaca","data","bars","--symbol",s,"--timeframe","1Day",
        "--start","2021-01-01","--end","2026-08-28","--limit","10000","--feed","iex","--quiet"],
        capture_output=True,text=True,env=os.environ)
    try: return json.loads(o.stdout).get("bars",[]) or []
    except Exception: return []

def rv(c,i,n=LOOK): return stdev([log(c[j]/c[j-1]) for j in range(i-n+1,i+1)])*sqrt(252)

def pct(v,p):
    v=sorted(v); k=(len(v)-1)*p/100.0; f=int(k)
    return v[f] if f+1>=len(v) else v[f]+(v[f+1]-v[f])*(k-f)

def main():
    data={s:bars(s) for s,_ in OPT}
    for s in STK:
        if s not in data: data[s]=bars(s)
    ref=data["SPY"]
    if not ref: print("no data"); return 1
    dates={s:{b["t"][:10]:i for i,b in enumerate(v)} for s,v in data.items()}
    mons=[(i,b["t"][:10]) for i,b in enumerate(ref)
          if datetime.fromisoformat(b["t"].replace("Z","+00:00")).weekday()==0]

    weeks=[]   # (total_pnl, entry_vol)
    for _,d in mons:
        tot=0.0; vol_at=None; n_ok=0
        for sym,W in OPT:
            i=dates.get(sym,{}).get(d)
            b=data.get(sym) or []
            if i is None or i<LOOK+1 or i+HOLD>=len(b): continue
            c=[x["c"] for x in b]; s0=c[i]; sig=rv(c,i)
            if sig<=0: continue
            if sym=="SPY": vol_at=sig
            T0=DTE/365.0; mv=Z*sig*sqrt(T0); kp,kc=s0*exp(-mv),s0*exp(mv)
            cred=2.0*CREDIT_DELTA_MULTIPLE*DELTA*W
            iv=implied_vol(cred,s0,kp,kc,W,T0)
            if iv is None: continue
            ml=(W-cred)*100.0
            nct=max(1,int(min(OPT_RISK/len(OPT),PER_POS)//ml))
            out=condor_value(c[i+HOLD],kp,kc,W,max(DTE-HOLD,0.2)/365.0,iv)
            tot+=(cred-out)*100.0*nct; n_ok+=1
        each=STOCK_CAP/len(STK)
        for sym in STK:
            i=dates.get(sym,{}).get(d); b=data.get(sym) or []
            if i is None or i<LOOK+1 or i+HOLD>=len(b): continue
            c=[x["c"] for x in b]; s0,s1=c[i],c[i+HOLD]; sig=rv(c,i)
            if sig<=0: continue
            T0=DTE/365.0; k=s0*exp(Z*sig*sqrt(T0)); sh=each/s0
            tot+=(s1-s0)*sh+(bs_call(s0,k,T0,sig*VRP)
                             -bs_call(s1,k,max(DTE-HOLD,0.2)/365.0,sig*VRP))*sh
        if n_ok>=10 and vol_at: weeks.append((tot,vol_at))

    cur=rv([x["c"] for x in ref], len(ref)-1)
    vals=[w for w,_ in weeks]
    band=[w for w,v in weeks if abs(v-cur)/cur<=0.35]

    B="\033[1m"; R="\033[0m"; D="\033[2m"; G="\033[32m"; RD="\033[31m"; Y="\033[33m"; C="\033[36m"
    W_=78
    print(f"{B}╔{'═'*W_}╗{R}")
    print(f"{B}║{' DELTAX · outcome distribution for Mon 31 Aug → Fri 4 Sep':<{W_}}║{R}")
    print(f"{B}╚{'═'*W_}╝{R}")
    print(f"  {Y}╔{'═'*62}╗{R}")
    print(f"  {Y}║  🎲  NOT A PREDICTION — a distribution of historical outcomes  ║{R}")
    print(f"  {Y}║      We cannot forecast direction. This says where weeks      ║{R}")
    print(f"  {Y}║      like this one have LANDED, with what frequency.          ║{R}")
    print(f"  {Y}╚{'═'*62}╝{R}")
    print(f"\n  current SPY 20-day realised vol {B}{cur*100:.1f}%{R}   "
          f"·  {len(vals)} historical weeks  ·  {len(band)} at a similar vol regime\n")

    for lbl,v in (("ALL WEEKS",vals),(f"SIMILAR VOL (±35%)",band)):
        if len(v)<20: continue
        m=mean(v); wins=sum(1 for x in v if x>0)
        print(f"{B}  ── {lbl}  (n={len(v)}) {'─'*(52-len(lbl))}{R}")
        for p,name in ((5,"very bad  "),(25,"poor      "),(50,"MEDIAN    "),
                       (75,"good      "),(95,"very good ")):
            x=pct(v,p); col=G if x>=0 else RD
            bar_n=int(min(abs(x)/200,34))
            bar=("█"*bar_n) if x>=0 else ("▓"*bar_n)
            print(f"    {name} p{p:<3}{col}{x:>9,.0f}{R} ({x/EQ*100:>6.2f}%)  {col}{bar}{R}")
        print(f"    {D}mean {m:+,.0f}   ·   weeks positive {wins}/{len(v)} = {wins/len(v)*100:.0f}%"
              f"   ·   worst ever {min(v):+,.0f}{R}")
        kill=sum(1 for x in v if x<=DAILY_LOSS_LIMIT_PCT/100*EQ)
        print(f"    {D}weeks losing more than {abs(DAILY_LOSS_LIMIT_PCT):.0f}% of equity: "
              f"{kill}/{len(v)} = {kill/len(v)*100:.0f}%{R}\n")

    v=band if len(band)>=20 else vals
    print(f"{B}  {'═'*W_}{R}")
    print(f"  {B}Most likely: a small gain.{R} Median {G}{pct(v,50):+,.0f}{R}, "
          f"positive in {sum(1 for x in v if x>0)/len(v)*100:.0f}% of comparable weeks.")
    print(f"  {B}The risk is not symmetric.{R} Upside is capped by the credit collected; "
          f"downside\n  is capped by defined risk but is far larger. "
          f"p5 is {RD}{pct(v,5):+,.0f}{R} against p95 of {G}{pct(v,95):+,.0f}{R}.")
    print(f"  {D}One draw. E19: this distribution describes many weeks; we get one.{R}")
    print(f"{B}  {'═'*W_}{R}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
