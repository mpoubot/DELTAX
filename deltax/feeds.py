"""Market data access for DELTAX, via the Alpaca CLI.

Every call shells out to the `alpaca` binary rather than hitting REST directly:
CLI usage is a graded hackathon requirement, and the JSON output is stable.

All network access in the agent lives in this file. Everything downstream takes
a feed object, so the screener and gates stay testable with the market closed.
"""

from typing import Optional
import json
import subprocess


class FeedError(RuntimeError):
    pass


class AlpacaFeed:
    """Thin wrapper over the Alpaca CLI. Credentials come from the environment."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def _run(self, args: list) -> dict:
        cmd = ["alpaca"] + args + ["--quiet"]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired as e:
            raise FeedError(f"timeout: {' '.join(cmd)}") from e
        if out.returncode != 0:
            raise FeedError(f"{' '.join(cmd)} -> {out.stderr.strip()[:200]}")
        try:
            payload = json.loads(out.stdout)
        except json.JSONDecodeError as e:
            raise FeedError(f"bad JSON from {' '.join(cmd)}") from e
        if isinstance(payload, dict) and payload.get("error"):
            raise FeedError(str(payload["error"])[:200])
        return payload

    # ── account state ───────────────────────────────────────────────────────

    def account(self) -> dict:
        """Live account. Raises on failure - never returns a plausible blank,
        because a dashboard that invents an equity number is worse than one
        that refuses to draw."""
        return self._run(["account", "get"])

    def positions(self) -> list:
        """Open positions, or [] when genuinely flat."""
        p = self._run(["position", "list"])
        if isinstance(p, list):
            return p
        return p.get("positions", []) or []

    # ── market state ────────────────────────────────────────────────────────

    def clock(self) -> dict:
        return self._run(["clock"])

    def snapshots(self, symbols: list) -> dict:
        d = self._run(["data", "multi-snapshots", "--symbols", ",".join(symbols)])
        return d.get("snapshots", d)

    # ── options ─────────────────────────────────────────────────────────────

    def option_chain(
        self,
        underlying: str,
        *,
        option_type: Optional[str] = None,
        expiry_gte: Optional[str] = None,
        expiry_lte: Optional[str] = None,
        strike_gte: Optional[float] = None,
        strike_lte: Optional[float] = None,
    ) -> dict:
        """Chain snapshot: greeks, IV and latest quote per contract, one call."""
        args = ["data", "option", "chain", "--underlying-symbol", underlying]
        if option_type: args += ["--type", option_type]
        if expiry_gte:  args += ["--expiration-date-gte", expiry_gte]
        if expiry_lte:  args += ["--expiration-date-lte", expiry_lte]
        if strike_gte is not None: args += ["--strike-price-gte", str(strike_gte)]
        if strike_lte is not None: args += ["--strike-price-lte", str(strike_lte)]
        d = self._run(args)
        return d.get("snapshots", d)

    def option_contracts(self, underlying: str, **kw) -> list:
        """Contract reference data — carries open_interest, which the chain does not."""
        args = ["option", "contracts", "--underlying-symbols", underlying]
        for flag, key in (("--type", "option_type"), ("--expiration-date-gte", "expiry_gte"),
                          ("--expiration-date-lte", "expiry_lte"),
                          ("--strike-price-gte", "strike_gte"),
                          ("--strike-price-lte", "strike_lte")):
            if kw.get(key) is not None:
                args += [flag, str(kw[key])]
        args += ["--limit", str(kw.get("limit", 100))]
        return self._run(args).get("option_contracts", [])


# ── helpers over feed payloads (pure) ────────────────────────────────────────

def latest_price(snapshot: dict) -> Optional[float]:
    t = snapshot.get("latestTrade") or {}
    if t.get("p") is not None:
        return float(t["p"])
    b = snapshot.get("dailyBar") or {}
    return float(b["c"]) if b.get("c") is not None else None


def intraday_vwap(snapshot: dict) -> Optional[float]:
    b = snapshot.get("dailyBar") or {}
    return float(b["vw"]) if b.get("vw") is not None else None


def previous_close(snapshot: dict) -> Optional[float]:
    b = snapshot.get("prevDailyBar") or {}
    return float(b["c"]) if b.get("c") is not None else None


def quote(contract: dict) -> tuple:
    """(bid, ask) for a chain contract; (None, None) when unquoted."""
    q = contract.get("latestQuote") or {}
    return q.get("bp"), q.get("ap")


def delta(contract: dict) -> Optional[float]:
    g = contract.get("greeks") or {}
    return g.get("delta")
