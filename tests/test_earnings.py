"""Earnings inference tests. Pure logic, no network."""
import sys, os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.earnings import EarningsProfile, blackout, FOREIGN_FORMS

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

def prof(sym, hist, note=""):
    if len(hist) < 2:
        return EarningsProfile(sym, hist, None, None, None, None, None, note)
    gaps = [(hist[i] - hist[i+1]).days for i in range(len(hist)-1)]
    from statistics import median
    from datetime import timedelta
    med, lo, hi = int(median(gaps)), min(gaps), max(gaps)
    return EarningsProfile(sym, hist, med, lo, hi,
                           hist[0]+timedelta(days=lo), hist[0]+timedelta(days=hi), note)

# AVGO's real cadence
AVGO = prof("AVGO", [date(2026,6,3), date(2026,3,4), date(2025,12,11),
                     date(2025,9,4), date(2025,6,5), date(2025,3,6)])

print("\n── cadence ──")
check("history retained newest-first", AVGO.history[0] == date(2026,6,3))
check("median gap ~quarterly", 85 <= AVGO.median_gap <= 95, str(AVGO.median_gap))
check("window derived from min/max gap",
      AVGO.next_earliest == date(2026,8,25) and AVGO.next_latest == date(2026,9,9),
      f"{AVGO.next_earliest}..{AVGO.next_latest}")
check("confident with 6 filings", AVGO.confident)

print("\n── window overlap ──")
check("expiry after window opens -> overlaps", AVGO.overlaps(date(2026,9,18)))
check("expiry inside window -> overlaps", AVGO.overlaps(date(2026,9,1)))
check("expiry before window -> clear", not AVGO.overlaps(date(2026,8,20)))

print("\n── blackout, fail-closed ──")
b, why = blackout("AVGO", date(2026,9,18), profiles={"AVGO": AVGO})
check("AVGO blocked for Sep 18", b and "2026-08-25" in why, why)
b2, _ = blackout("AVGO", date(2026,8,20), profiles={"AVGO": AVGO})
check("AVGO clear for Aug 20", not b2)

thin = prof("XYZ", [date(2026,6,1), date(2026,3,1)])
check("too little history -> not confident", not thin.confident)
b3, why3 = blackout("XYZ", date(2026,9,18), profiles={"XYZ": thin})
check("thin history BLOCKS (absence != safety)", b3, why3)

foreign = prof("PDD", [], note="foreign private issuer (files 20-F/6-K, not 8-K)")
b4, why4 = blackout("PDD", date(2026,9,18), profiles={"PDD": foreign})
check("foreign issuer blocked", b4)
check("foreign issuer reason surfaced", "foreign private issuer" in why4, why4)
check("6-K/20-F/40-F recognised as foreign", FOREIGN_FORMS == {"6-K","20-F","40-F"})

print("\n── irregular cadence widens the window ──")
irr = prof("IRR", [date(2026,6,1), date(2026,2,1), date(2025,11,1), date(2025,6,1)])
check("wider gap spread -> wider window",
      (irr.next_latest - irr.next_earliest).days > (AVGO.next_latest - AVGO.next_earliest).days)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
