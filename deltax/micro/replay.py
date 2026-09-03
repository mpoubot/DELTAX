"""Chronological replay, and forward-outcome measurement that cannot cheat.

The engine used here is the SAME FeatureEngine the live path uses. There is no
research variant. A signal measured in replay is measured by production code.

THE SEALING RULE. A decision is taken from features computed strictly before
its timestamp, then FROZEN. Only after freezing may the outcome window be
opened. `Decision` records are immutable and outcomes attach to a separate
object, so there is no code path by which a forward return could influence the
features that produced the decision - the contamination is prevented by shape,
not by remembering to be careful.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

from deltax.micro.events import Trade, Quote, Bar, merge
from deltax.micro.features import FeatureEngine

FORWARD_HORIZONS_MIN = (5, 15, 30, 60)


@dataclass(frozen=True)
class Decision:
    """Sealed. Everything here was knowable at `ts` and nothing else was."""
    ts: datetime
    symbol: str
    snapshot: dict
    price: Optional[float]


@dataclass
class Outcome:
    """Attached only after the decision was sealed."""
    decision: Decision
    forward: dict = field(default_factory=dict)     # minutes -> return
    mfe: dict = field(default_factory=dict)         # max favourable excursion
    mae: dict = field(default_factory=dict)         # max adverse excursion


class Replay:
    """Feed events in order; sample features at intervals; seal decisions."""

    def __init__(self, symbol: str, events: list, config: Optional[dict] = None):
        self.symbol = symbol
        # sorted once here so `step` never has to reorder - and so a caller
        # cannot hand us a stream whose order silently differs from live
        self.events = sorted(events, key=lambda e: e.ts)
        self.engine = FeatureEngine(symbol, config)
        self.decisions: list = []
        self._i = 0

    def run_to(self, until: datetime) -> None:
        """Consume every event strictly at or before `until`. Nothing later is
        touched, so the engine cannot see past the cursor."""
        while self._i < len(self.events) and self.events[self._i].ts <= until:
            self.engine.step(self.events[self._i])
            self._i += 1

    def sample(self, at: datetime) -> Decision:
        """Advance to `at` and seal what was knowable."""
        self.run_to(at)
        return Decision(ts=at, symbol=self.symbol,
                        snapshot=self.engine.snapshot(),
                        price=self.engine._last_price)

    def walk(self, start: datetime, end: datetime,
             every: timedelta = timedelta(minutes=5)) -> list:
        out, t = [], start
        while t <= end:
            out.append(self.sample(t))
            t += every
        self.decisions = out
        return out

    # ── outcomes: only ever computed from the sealed record ─────────────────
    def measure(self, decision: Decision,
                horizons=FORWARD_HORIZONS_MIN) -> Outcome:
        """Forward returns for one sealed decision.

        Reads events AFTER decision.ts only. The Decision is frozen, so this
        cannot write back into the features that produced it even by mistake.
        """
        o = Outcome(decision=decision)
        base = decision.price
        if base is None or base <= 0:
            return o
        for m in horizons:
            window = [e for e in self.events
                      if isinstance(e, (Trade, Bar))
                      and decision.ts < e.ts <= decision.ts + timedelta(minutes=m)]
            if not window:
                o.forward[m] = None
                continue
            prices = [(e.price if isinstance(e, Trade) else e.close) for e in window]
            o.forward[m] = round((prices[-1] - base) / base * 100, 4)
            o.mfe[m] = round((max(prices) - base) / base * 100, 4)
            o.mae[m] = round((min(prices) - base) / base * 100, 4)
        return o

    def measure_all(self, horizons=FORWARD_HORIZONS_MIN) -> list:
        return [self.measure(d, horizons) for d in self.decisions]


def contamination_check(replay: "Replay", decision: Decision) -> tuple:
    """Prove no feature used data from after the decision.

    Rebuilds the decision from a FRESH engine fed only events <= decision.ts.
    If the rebuilt snapshot differs from the sealed one, something in the
    original run saw further than it should have. The spec says to fail when
    uncertain; a mismatch is a failure, never a warning.
    """
    fresh = FeatureEngine(replay.symbol, replay.engine.cfg)
    for e in replay.events:
        if e.ts > decision.ts:
            break
        fresh.step(e)
    rebuilt = fresh.snapshot()
    a = decision.snapshot.get("features")
    b = rebuilt.get("features")
    if a != b:
        diffs = [x["signal"] for x, y in zip(a, b) if x != y]
        return False, f"features differ when replayed clean: {diffs}"
    if fresh.now is not None and fresh.now > decision.ts:
        return False, "engine consumed an event later than the decision"
    return True, "no lookahead: rebuild from a clean engine is identical"
