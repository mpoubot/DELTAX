"""Append-only decision ledger for the DELTAX options agent.

Every evaluation the agent performs — trade or refusal — is written here as one
JSONL record. This is the audit trail the strategy is built around:

- Refusals are first-class: each record carries every gate checked, the values
  observed, the thresholds applied, and which gate failed first.
- Records are hash-chained (each includes the SHA-256 of the previous record),
  so the file is tamper-evident — the DELTAX counterpart of AURA's append-only
  .17 ledger with provenance hashes.
- Rule provenance: each record stores the git commit of the rules that produced
  it, so any decision can be traced to the exact frozen rule set.

Design rules, same as gates.py: no network, no hidden globals. The clock is
injectable, so tests run deterministically with the market closed.
"""

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
import hashlib
import json
import os
import subprocess
import uuid

from deltax.gates import DecisionRecord

SCHEMA_VERSION = 1
GENESIS_HASH = "0" * 64


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _rules_commit() -> str:
    """Git commit of the rule set in force. 'unknown' outside a repo."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _canonical(obj) -> bytes:
    """Stable serialization for hashing: sorted keys, no whitespace drift."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()


class Ledger:
    """One JSONL file per UTC day, records hash-chained across the whole run.

    Usage:
        ledger = Ledger("logs")
        entry = ledger.record(decision_record, context={...})
    """

    def __init__(
        self,
        directory: str,
        run_id: Optional[str] = None,
        clock: Optional[Callable[[], str]] = None,
        rules_commit: Optional[str] = None,
    ):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self._clock = clock or _utc_now
        self._rules_commit = rules_commit if rules_commit is not None else _rules_commit()
        self._seq, self._prev_hash = self._resume_state()

    # ── internal ────────────────────────────────────────────────────────────

    def _path_for(self, ts_iso: str) -> Path:
        return self.dir / f"decisions-{ts_iso[:10]}.jsonl"

    def _files(self):
        return sorted(self.dir.glob("decisions-*.jsonl"))

    def _resume_state(self):
        """Continue the chain across restarts: pick up seq and last hash."""
        last = None
        for f in self._files():
            for line in f.read_text().splitlines():
                if line.strip():
                    last = json.loads(line)
        if last is None:
            return 0, GENESIS_HASH
        return last["seq"] + 1, last["hash"]

    # ── API ─────────────────────────────────────────────────────────────────

    def record(self, decision: DecisionRecord, context: Optional[dict] = None) -> dict:
        """Append one evaluation. Returns the full entry as written."""
        ts = self._clock()
        entry = {
            "schema_version": SCHEMA_VERSION,
            "seq": self._seq,
            "ts_utc": ts,
            "run_id": self.run_id,
            "rules_commit": self._rules_commit,
            "prev_hash": self._prev_hash,
            "symbol": decision.symbol,
            "decision": decision.decision,
            "failed_gate": decision.failed_gate,
            "contracts": decision.contracts,
            "max_loss": decision.max_loss,
            "max_profit": decision.max_profit,
            "gates": [asdict(g) for g in decision.gates],
            "notes": decision.notes,
            "context": context or {},
        }
        entry["hash"] = hashlib.sha256(
            _canonical({k: v for k, v in entry.items()})
        ).hexdigest()

        with self._path_for(ts).open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

        self._seq += 1
        self._prev_hash = entry["hash"]
        return entry

    def record_raw(self, event: dict) -> dict:
        """Append a non-gate event (order submission, fill, flatten).

        Same hash chain as decisions, so the execution trail is tamper-evident
        alongside the reasoning trail.
        """
        ts = self._clock()
        entry = {
            "schema_version": SCHEMA_VERSION,
            "seq": self._seq,
            "ts_utc": ts,
            "run_id": self.run_id,
            "rules_commit": self._rules_commit,
            "prev_hash": self._prev_hash,
            "kind": "event",
            "event": event,
        }
        entry["hash"] = hashlib.sha256(_canonical(entry)).hexdigest()
        with self._path_for(ts).open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        self._seq += 1
        self._prev_hash = entry["hash"]
        return entry

    def entries(self):
        """All entries across all day files, in sequence order."""
        out = []
        for f in self._files():
            for line in f.read_text().splitlines():
                if line.strip():
                    out.append(json.loads(line))
        out.sort(key=lambda e: e["seq"])
        return out

    def verify(self) -> tuple[bool, str]:
        """Walk the hash chain. Any edit, deletion or reorder breaks it."""
        prev = GENESIS_HASH
        for e in self.entries():
            if e["prev_hash"] != prev:
                return False, f"chain broken at seq {e['seq']}: prev_hash mismatch"
            claimed = e["hash"]
            recomputed = hashlib.sha256(
                _canonical({k: v for k, v in e.items() if k != "hash"})
            ).hexdigest()
            if claimed != recomputed:
                return False, f"chain broken at seq {e['seq']}: content altered"
            prev = claimed
        return True, "chain intact"

    def summary(self) -> dict:
        """The 'evaluated 84, refused 78' numbers, plus refusal reasons."""
        es = [e for e in self.entries() if e.get("kind") != "event"]
        events = [e for e in self.entries() if e.get("kind") == "event"]
        refusals_first, failures_all = {}, {}
        for e in es:
            if e["decision"] == "REFUSE" and e["failed_gate"]:
                refusals_first[e["failed_gate"]] = refusals_first.get(e["failed_gate"], 0) + 1
            for g in e["gates"]:
                if not g["passed"]:
                    failures_all[g["gate"]] = failures_all.get(g["gate"], 0) + 1
        return {
            "evaluated": len(es),
            "trades": sum(1 for e in es if e["decision"] == "TRADE"),
            "refusals": sum(1 for e in es if e["decision"] == "REFUSE"),
            "refusals_by_first_failed_gate": dict(
                sorted(refusals_first.items(), key=lambda kv: -kv[1])),
            "gate_failure_counts": dict(
                sorted(failures_all.items(), key=lambda kv: -kv[1])),
            "committed_max_loss": round(
                sum(e["max_loss"] for e in es if e["decision"] == "TRADE"), 2),
            "events": len(events),
            "runs": sorted({e["run_id"] for e in self.entries()}),
        }


if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else "logs"
    led = Ledger(d)
    ok, msg = led.verify()
    print(json.dumps({"integrity": msg, **led.summary()}, indent=2))
