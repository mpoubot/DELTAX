"""Full-year lifecycle backtest of the DELTAX catalyst structure, on REAL
option prices (OPRA via Massive).

Model mirrors what the agent actually does:
  entry   2 sessions before expiry, at the OPEN, ATM 5-wide call debit spread
  price   (long open - short open) x 1.05 friction; never a midpoint assumption
  exit    resting limit at 2x debit, capped at 90% of width; fills when the
          spread's HIGH touches it on any later session
  settle  otherwise valued at expiry from the underlying close
"""
import json, os, datetime, random
from math import log, sqrt
from statistics import stdev, mean

SC = os.path.dirname(os.path.abspath(__file__))
cache = json.load(open(f"{SC}/mcache.json"))
spot = json.load(open(f"{SC}/spot_full.json"))
days = sorted(spot)
day = lambda t: datetime.datetime.fromtimestamp(t / 1000, datetime.UTC).strftime("%Y-%m-%d")
bars = lambda t, a, b: cache.get(f"{t}|{a}|{b}") or []
occ = lambda e, k: f"O:USO{e[2:4]}{e[5:7]}{e[8:10]}C{int(round(k*1000)):08d}"

FRICTION, EXIT_MULT, WIDTH_CAP, WIDTH = 1.05, 2.0, 0.90, 5

fri = [d for d in days if datetime.date.fromisoformat(d).weekday() == 4]
fri = [e for e in fri if days.index(e) >= 3]

rows, skipped = [], {}
for exp in fri:
    i = days.index(exp)
    entry = days[i - 2]
    s = spot[entry]["c"]
    prev = spot[days[i - 3]]["c"]
    k = round(s)
    b1 = {day(x["t"]): x for x in bars(occ(exp, k), entry, exp)}
    b2 = {day(x["t"]): x for x in bars(occ(exp, k + WIDTH), entry, exp)}
    if entry not in b1 or entry not in b2:
        skipped["no entry print"] = skipped.get("no entry print", 0) + 1
        continue
    debit = round((b1[entry]["o"] - b2[entry]["o"]) * FRICTION, 2)
    if debit <= 0:
        skipped["crossed/zero debit"] = skipped.get("crossed/zero debit", 0) + 1
        continue
    target = round(min(debit * EXIT_MULT, WIDTH * WIDTH_CAP), 2)
    hit = any(b1[d]["h"] - b2[d]["h"] >= target
              for d in sorted(set(b1) & set(b2)) if d > entry)
    fin = spot[exp]["c"]
    settle = max(0.0, min(fin - k, WIDTH))
    pnl = (target - debit) if hit else (settle - debit)
    ret = pnl / debit * 100
    # regime from information available BEFORE the trade
    c20 = [spot[x]["c"] for x in days[i - 22:i - 1]]
    rv = stdev([log(c20[j] / c20[j - 1]) for j in range(1, len(c20))]) * sqrt(252) if len(c20) > 2 else 0
    mv = (s / prev - 1) * 100
    regime = ("CATALYST" if mv >= 2.0 else
              "HIVOL" if rv > 0.45 else
              "SELLOFF" if mv <= -2.0 else "NORMAL")
    rows.append(dict(exp=exp, entry=entry, spot=s, k=k, debit=debit, target=target,
                     hit=hit, fin=fin, settle=settle, pnl=pnl, ret=ret,
                     regime=regime, mv=mv, rv=rv,
                     out="2x EXIT" if hit else ("expired ITM" if settle > 0 else "expired 0")))

print(f"  expiries with usable option prices: {len(rows)} of {len(fri)}")
for k_, v in skipped.items():
    print(f"    skipped ({k_}): {v}")

r = [x["ret"] for x in rows]
wins = [x for x in rows if x["ret"] > 0]
hits = [x for x in rows if x["hit"]]
print(f"\n  ── HEADLINE (n={len(rows)}) ──")
print(f"    win rate        {len(wins)/len(r)*100:.0f}%")
print(f"    2x exit hit     {len(hits)/len(r)*100:.0f}%  ({len(hits)}/{len(r)})")
print(f"    mean return     {mean(r):+.0f}% of debit")
print(f"    median          {sorted(r)[len(r)//2]:+.0f}%")
print(f"    worst / best    {min(r):+.0f}% / {max(r):+.0f}%")

# equity curve at a flat $10,000 risk per trade
eq, peak, dd = 100_000.0, 100_000.0, 0.0
for x in rows:
    eq += 10_000 * x["ret"] / 100
    peak = max(peak, eq)
    dd = min(dd, (eq - peak) / peak * 100)
print(f"\n  ── $10,000 risked per trade, {len(rows)} trades ──")
print(f"    ending equity   ${eq:,.0f}   ({eq-100_000:+,.0f})")
print(f"    max drawdown    {dd:.1f}%")

print(f"\n  ── BY REGIME ──")
print(f"    {'regime':<10}{'n':>4}{'win%':>7}{'mean':>8}{'2x hit':>9}")
for g in ("CATALYST", "HIVOL", "SELLOFF", "NORMAL"):
    sub = [x for x in rows if x["regime"] == g]
    if not sub:
        continue
    rr = [x["ret"] for x in sub]
    print(f"    {g:<10}{len(sub):>4}{sum(1 for x in rr if x>0)/len(rr)*100:>6.0f}%"
          f"{mean(rr):>+8.0f}{sum(1 for x in sub if x['hit'])/len(sub)*100:>8.0f}%")

print(f"\n  ── BOOTSTRAP (10k resamples of per-trade returns) ──")
sims = sorted(mean(random.choices(r, k=len(r))) for _ in range(10000))
print(f"    P(mean < 0)     {sum(1 for x in sims if x < 0)/100:.1f}%")
print(f"    p5 / p50 / p95  {sims[500]:+.0f}% / {sims[5000]:+.0f}% / {sims[9500]:+.0f}%")

print(f"\n  ── WORST 5 TRADES ──")
for x in sorted(rows, key=lambda z: z["ret"])[:5]:
    print(f"    {x['exp']}  {x['regime']:<9} debit {x['debit']:>5.2f} "
          f"{x['out']:<12} USO {x['spot']:.2f}->{x['fin']:.2f}  {x['ret']:+.0f}%")
json.dump(rows, open(f"{SC}/bt_rows.json", "w"))
