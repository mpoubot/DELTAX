"""E61 guards: the touch-probability posterior."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.probability import (p_touch_base, update, catalyst_status,
                                size_band, P_FLOOR, P_CEIL)

passed = failed = 0
def check(name, cond, detail=""):
    global passed, failed
    if not isinstance(name, str) or not isinstance(cond, (bool, type(None))):
        raise TypeError("check(label:str, cond:bool, detail)")
    if cond: passed += 1; print(f"  ✓ {name}")
    else: failed += 1; print(f"  ✗ {name}  {detail}")

print("── base rate from the option market ──")
p150 = p_touch_base(140.98, 150.0, 0.60, 1.9)
p144 = p_touch_base(140.98, 144.0, 0.60, 1.9)
check("P(150) ~23% at IV 60%, 1.9 sessions", p150 is not None and 0.19 < p150 < 0.28, str(p150))
check("P(144) ~68% — nearer level, much likelier", p144 is not None and 0.62 < p144 < 0.74, str(p144))
check("nearer levels always likelier", p144 > p150)
check("level at spot is certain", p_touch_base(141.0, 141.0, 0.60, 1.9) == 1.0)
check("higher IV raises P(touch)",
      p_touch_base(141.0, 150.0, 0.90, 1.9) > p_touch_base(141.0, 150.0, 0.40, 1.9))
check("more time raises P(touch)",
      p_touch_base(141.0, 150.0, 0.60, 4.0) > p150)
check("zero IV -> None, never a number", p_touch_base(141.0, 150.0, 0.0, 1.9) is None)
check("missing spot -> None", p_touch_base(0.0, 150.0, 0.6, 1.9) is None)

print("\n── posterior updates in log-odds ──")
up = update(0.42, {"hormuz_physical_disruption": True, "wti_breakout_holds": True,
                   "uso_confirms": True, "options_reasonably_priced": True})
check("Pautax's ladder: 42% + full confirmation reaches ~65-80%",
      up.p is not None and 0.63 < up.p < 0.82, str(up.p))
down = update(0.63, {"de_escalation": True, "oil_reversal": True, "momentum_lost": True})
check("fade ladder: 63% collapses under de-escalation", down.p < 0.40, str(down.p))
check("no evidence leaves the base unchanged",
      abs(update(0.42, {}).p - 0.42) < 1e-9)
check("bounded above", update(0.94, {k: True for k in
      ("hormuz_physical_disruption","supply_confirmed_hit","wti_breakout_holds")}).p <= P_CEIL)
check("bounded below", update(0.05, {"de_escalation": True, "oil_reversal": True}).p >= P_FLOOR)
check("unknown base propagates as unknown", update(None, {"uso_confirms": True}).p is None)
try:
    update(0.5, {"tpyo_flag": True})
    check("a typo'd evidence flag raises loudly", False, "accepted silently")
except KeyError:
    check("a typo'd evidence flag raises loudly", True)

print("\n── catalyst status ──")
check("2+ physical confirmations -> ESCALATING",
      catalyst_status({"hormuz_physical_disruption": True, "wti_breakout_holds": True}) == "ESCALATING")
check("negatives dominate -> FADING",
      catalyst_status({"de_escalation": True, "wti_breakout_holds": True,
                       "oil_reversal": True}) == "FADING")
check("nothing new -> UNCHANGED", catalyst_status({}) == "UNCHANGED")

print("\n── size follows evidence, ceiling is a ceiling ──")
check("unknown -> $0", size_band(None)[0] == 0.0)
check("weak -> $2,500", size_band(0.40)[0] == 2500.0)
check("good -> $5,000", size_band(0.55)[0] == 5000.0)
check("very strong -> $7,500", size_band(0.69)[0] == 7500.0)
check("exceptional on PRICE evidence alone caps at $10,000",
      size_band(0.90, physical=0)[0] == 10000.0)
check("bands are monotone", size_band(0.40)[0] <= size_band(0.55)[0]
      <= size_band(0.69)[0] <= size_band(0.90)[0])

print("\n── E62: the escalation ladder needs PHYSICAL confirmation ──")
from deltax.probability import HARD_MAX_RISK, physical_count
check("one physical confirmation -> $15,000",
      size_band(0.80, physical=1)[0] == 15000.0)
check("two physical + p>=0.85 -> $20,000 hard max",
      size_band(0.88, physical=2)[0] == HARD_MAX_RISK)
check("two physical but p<0.85 stays at $15,000",
      size_band(0.80, physical=2)[0] == 15000.0)
check("physical evidence cannot rescue a weak posterior",
      size_band(0.50, physical=2)[0] == 5000.0)
check("nothing exceeds HARD_MAX_RISK",
      all(size_band(p, ph)[0] <= HARD_MAX_RISK
          for p in (0.5, 0.8, 0.95) for ph in (0, 1, 2, 3)))
check("physical_count reads only the physical flags",
      physical_count({"hormuz_physical_disruption": True, "uso_confirms": True,
                      "wti_breakout_holds": True}) == 2)
_run = open("deltax/run.py").read()
check("run.py passes physical count into sizing", "physical" in _run and "size_band(_post.p" in _run)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
