"""Market data access for DELTAX, via the Alpaca CLI.

Every call shells out to the `alpaca` binary rather than hitting REST directly:
CLI usage is a graded hackathon requirement, and the JSON output is stable.

All network access in the agent lives in this file. Everything downstream takes
a feed object, so the screener and gates stay testable with the market closed.
"""

from typing import Optional
import json
import subprocess
import time


class FeedError(RuntimeError):
    pass


class AlpacaFeed:
    """Thin wrapper over the Alpaca CLI. Credentials come from the environment."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    # E76: a transient network blip must not cost a whole cycle. On 2 Sep a TLS
    # handshake timeout killed a run outright; E75 made that fail closed, which
    # is safe but still surrenders five minutes of exit management and
    # reconciliation. The right answer is to RETRY: these failures clear in
    # under a second, and the previous behaviour treated a hiccup like an
    # outage.
    #
    # Retried ONLY for transport faults. An API-level rejection - bad symbol,
    # unauthorised, malformed order - is a real answer and must surface on the
    # first attempt; retrying it would hammer the broker and hide the fault.
    TRANSIENT = ("tls handshake", "timeout", "connection refused", "connection reset",
                 "eof", "no such host", "temporary failure", "i/o timeout",
                 "502", "503", "504", "bad gateway", "service unavailable")
    RETRIES = 3
    BACKOFF = 0.6          # seconds; 0.6, 1.2, 2.4 - well inside a 5-minute cycle

    @classmethod
    def _is_transient(cls, msg: str) -> bool:
        low = (msg or "").lower()
        return any(t in low for t in cls.TRANSIENT)

    def _run(self, args: list) -> dict:
        cmd = ["alpaca"] + args + ["--quiet"]
        last = None
        for attempt in range(self.RETRIES):
            if attempt:
                time.sleep(self.BACKOFF * (2 ** (attempt - 1)))
            try:
                out = subprocess.run(cmd, capture_output=True, text=True,
                                     timeout=self.timeout)
            except subprocess.TimeoutExpired as e:
                last = FeedError(f"timeout after {self.timeout}s: {' '.join(cmd)}")
                continue                      # a timeout is always worth retrying
            if out.returncode != 0:
                err = out.stderr.strip()[:200]
                last = FeedError(f"{' '.join(cmd)} -> {err}")
                if self._is_transient(err):
                    continue
                raise last                    # a real rejection: surface it now
            try:
                payload = json.loads(out.stdout)
            except json.JSONDecodeError as e:
                last = FeedError(f"bad JSON from {' '.join(cmd)}")
                continue                      # truncated response - retry
            if isinstance(payload, dict) and payload.get("error"):
                msg = str(payload["error"])[:200]
                last = FeedError(msg)
                if self._is_transient(msg):
                    continue
                raise last
            return payload
        raise FeedError(f"{self.RETRIES} attempts failed - {last}")

    # ── account state ───────────────────────────────────────────────────────

    def account(self) -> dict:
        """Live account. Raises on failure - never returns a plausible blank,
        because a dashboard that invents an equity number is worse than one
        that refuses to draw."""
        return self._run(["account", "get"])

    def open_orders(self) -> list:
        """Orders working at the broker but not yet filled.

        An unfilled order is invisible to positions(), which is how two
        identical spreads were submitted a minute apart on 31 Aug (E36).
        """
        p = self._run(["order", "list", "--status", "open", "--limit", "100"])
        if isinstance(p, list):
            return p
        return p.get("orders", []) or []

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

    def daily_bars(self, symbol: str, start: str, end: str, limit: int = 60) -> list:
        """Daily bars. E50: needed for realized vol, which nothing fetched before."""
        payload = self._run(["data", "bars", "--symbol", symbol,
                             "--timeframe", "1Day", "--start", start, "--end", end,
                             "--limit", str(limit), "--feed", "iex"])
        return (payload or {}).get("bars") or []

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
    """Close of the last COMPLETED session — not blindly prevDailyBar.

    E66: before the open the bars have not rolled. On 2 Sep at 09:29 the
    snapshot carried dailyBar = 1 Sep (140.98) and prevDailyBar = 31 Aug
    (133.715), so reading prevDailyBar made USO look +4.12% when it was
    actually DOWN 1.26% against Tuesday's close. The catalyst gate would have
    fired on a fading move, and every downstream number - posterior, evidence
    flags, size band - would have inherited the error.

    Rule: if dailyBar is today's session, the previous close is prevDailyBar.
    If dailyBar is an EARLIER session (pre-market, or a stale feed), then
    dailyBar IS the last completed session and is the correct reference.
    """
    from datetime import datetime, timezone, timedelta
    daily = snapshot.get("dailyBar") or {}
    prev = snapshot.get("prevDailyBar") or {}

    def _date(bar):
        t = bar.get("t")
        if not t:
            return None
        try:
            return datetime.fromisoformat(str(t).replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None

    d_day = _date(daily)
    # Session date in ET; UTC would roll the day at 20:00 ET and mislabel bars.
    today_et = datetime.now(timezone(timedelta(hours=-4))).date()

    if d_day is not None and d_day < today_et and daily.get("c") is not None:
        return float(daily["c"])          # bars have not rolled yet
    return float(prev["c"]) if prev.get("c") is not None else None


def quote(contract: dict) -> tuple:
    """(bid, ask) for a chain contract; (None, None) when unquoted."""
    q = contract.get("latestQuote") or {}
    return q.get("bp"), q.get("ap")


def delta(contract: dict) -> Optional[float]:
    g = contract.get("greeks") or {}
    return g.get("delta")
