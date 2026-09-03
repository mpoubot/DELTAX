"""Inventory, participants and regime nesting.

The tests that matter here are the ones asserting the system stays HONEST:
that it never claims to know who is positioned where, that confidence falls
when horizons disagree, and that a missing horizon is marked rather than faked.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deltax.micro.inventory import (build_profile, cluster, Zone,
                                    participant_hypotheses, HORIZON_WEIGHT,
                                    VALUE_AREA, _bucket_size)
from deltax.micro.regime import stack, _classify, LADDER

passed = failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  {d}")

def bars(closes, vols=None, vw=None):
    vols = vols or [1000] * len(closes)
    vw = vw or closes
    return [{"c": c, "v": v, "vw": w} for c, v, w in zip(closes, vols, vw)]

print("\n── profiles: missing history is marked, never approximated ──")
p = build_profile(bars([100] * 2), "5D")
check("too few bars -> UNAVAILABLE", p.status == "UNAVAILABLE", p.reason)
check("and no POC is invented", p.poc is None)
check("the reason states the shortfall", "need" in p.reason, p.reason)
check("a 1Y profile needs far more bars than a 5D one",
      build_profile(bars([100] * 20), "1Y").status == "UNAVAILABLE"
      and build_profile(bars([100] * 20), "5D").status == "OK")

print("\n── profile arithmetic ──")
p2 = build_profile(bars([100.0] * 10 + [110.0] * 2,
                        [10000] * 10 + [100] * 2,
                        [100.0] * 10 + [110.0] * 2), "5D")
check("POC is the highest-volume price", abs(p2.poc - 100.0) < 0.3, str(p2.poc))
check("VAL <= POC <= VAH", p2.val <= p2.poc <= p2.vah, str(p2.as_dict()))
check("value area is the configured share", abs(VALUE_AREA - 0.70) < 1e-9)
check("buckets scale with price",
      _bucket_size(20.0) < _bucket_size(700.0))

print("\n── clustering: agreement across horizons is weighted by age ──")
z = cluster({"5D": build_profile(bars([100.0] * 10), "5D"),
             "1Y": build_profile(bars([100.0] * 200), "1Y")})
check("overlapping levels merge into one zone", len(z) == 1, str(len(z)))
check("the zone names every horizon that confirmed it",
      set(z[0].horizons) == {"5D", "1Y"}, str(z[0].horizons))
check("a long horizon outweighs a short one",
      HORIZON_WEIGHT["1Y"] > HORIZON_WEIGHT["5D"])
check("a 2Y confirmation is the heaviest", HORIZON_WEIGHT["2Y"] ==
      max(HORIZON_WEIGHT.values()))
far = cluster({"5D": build_profile(bars([100.0] * 10), "5D"),
               "1Y": build_profile(bars([200.0] * 200), "1Y")})
check("distant levels stay separate zones", len(far) == 2, str(len(far)))
check("no profiles yields no zones", cluster({}) == [])

print("\n── participants: possibilities, never probabilities ──")
Z = Zone(low=100.0, high=101.0, horizons=["5D", "20D", "1Y"],
         strength=8.0, total_volume=1e6)
above = participant_hypotheses(110.0, Z)
check("price above inventory is identified",
      above["state"] == "PRICE_ABOVE_INVENTORY", above.get("state"))
check("longs there MAY be profitable",
      above["hypotheses"]["long_inventory_profitable"] == "HIGH")
check("shorts there MAY be underwater",
      "short_inventory_underwater" in above["hypotheses"])
below = participant_hypotheses(90.0, Z)
check("price below inventory is identified",
      below["state"] == "PRICE_BELOW_INVENTORY")
check("longs there MAY be underwater",
      below["hypotheses"]["long_inventory_underwater"] == "HIGH")
check("breakeven selling is anticipated on a rally back",
      "breakeven_selling_on_rally" in below["hypotheses"])
inside = participant_hypotheses(100.5, Z)
check("price inside inventory refuses to pick a side",
      inside["state"] == "PRICE_INSIDE_INVENTORY"
      and inside["hypotheses"]["positioning_mixed"] == "HIGH")
# the honesty guarantee
check("every read carries the not-observable caveat",
      all("NOT" in r["caveat"] and "observable" in r["caveat"]
          for r in (above, below, inside)))
check("values are possibility LEVELS, not numbers",
      all(isinstance(v, str) for v in above["hypotheses"].values()),
      "a number here would fabricate precision that does not exist")
check("each read says what a move would force",
      all(len(r["if_price_moves"]) > 40 for r in (above, below, inside)))
check("no price yields UNAVAILABLE",
      participant_hypotheses(0.0, Z)["status"] == "UNAVAILABLE")

print("\n── regime nesting: disagreement must LOWER confidence ──")
up = list(range(100, 400))
agree = stack("T", bars=bars([float(x) for x in up]))
check("a uniformly rising series aligns", agree["alignment"] > 0.9,
      str(agree["alignment"]))
check("and reads UP", agree["direction"] == "UP", agree["direction"])
mixed = stack("T", bars=bars([float(x) for x in up[:-20]] +
                             [float(up[-20] - i * 3) for i in range(20)]))
check("a reversal at the short end lowers alignment",
      mixed["alignment"] < agree["alignment"],
      f"{mixed['alignment']} vs {agree['alignment']}")
check("confidence falls with it", mixed["confidence"] < agree["confidence"],
      f"{mixed['confidence']} vs {agree['confidence']}")
check("the stack is NOT collapsed to one label",
      len(mixed["stack"]) == len(LADDER))
check("it reads longest horizon first",
      mixed["stack"][0]["horizon"] == "2Y" and mixed["stack"][-1]["horizon"] == "5D")
check("the narrative nests with 'inside'", "inside" in mixed["narrative"],
      mixed["narrative"])
thin = stack("T", bars=bars([100.0, 101.0, 102.0]))
check("horizons without history are UNKNOWN, not guessed",
      "2Y" in thin["unavailable"], str(thin["unavailable"]))
check("data quality reflects how many horizons were readable",
      thin["data_quality"] in ("LOW", "MEDIUM"), thin["data_quality"])
check("no bars at all does not raise",
      stack("T", bars=[])["data_quality"] == "LOW")

print("\n── regime classification is scaled to each horizon's own vol ──")
flat = _classify(bars([100.0 + (i % 2) * 0.01 for i in range(60)]), "20D")
check("a flat series is RANGE or compression",
      flat.label in ("RANGE", "VOL_COMPRESSION"), flat.label)
check("its reason cites the measurement", len(flat.reason) > 10, flat.reason)

print(f"\n{'='*52}\n  {passed} passed, {failed} failed\n{'='*52}")
sys.exit(1 if failed else 0)
