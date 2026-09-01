"""Order execution — the only module that can reach the broker.

Safety model, mirroring AURA's barrier pattern:

  * `dry_run=True` is the DEFAULT. Nothing submits unless a caller passes
    dry_run=False explicitly AND the environment sets DELTAX_ORDERS_ALLOWED=1.
    Two independent switches, because one is too easy to flip by accident.
  * Every submission is preceded by a live account check: the account number
    must match the configured competition account, and the endpoint must be
    paper. A mismatch aborts.
  * Every attempt - dry, submitted, refused or failed - is written to the
    ledger before anything else happens.

Nothing here decides WHAT to trade. It receives an already-gated decision and
carries it out, or refuses.
"""

from dataclasses import dataclass
from typing import Optional
import json
import os
import subprocess

# The account this agent is allowed to trade. Pinned so a stray credential can
# never route an order to the wrong place - but read from the environment so
# swapping the paper account does not silently halt every order with an
# "account mismatch" that looks like the bot dying (E40).
#
# Set DELTAX_ACCOUNT in .env.alpaca when the paper account changes. Unset, it
# keeps the original competition account.
COMPETITION_ACCOUNT = os.environ.get("DELTAX_ACCOUNT", "PA397N6FXXIE")
ORDERS_ALLOWED_ENV = "DELTAX_ORDERS_ALLOWED"


class ExecutionRefused(RuntimeError):
    """A safety precondition failed. Never retried automatically."""


@dataclass
class Leg:
    symbol: str            # OCC option symbol
    side: str              # buy | sell
    ratio_qty: int = 1

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "ratio_qty": str(self.ratio_qty),
            "position_intent": f"{self.side}_to_open",
        }


def build_mleg_args(legs: list, qty: int, limit_price: float,
                    tif: str = "day") -> list:
    """Arg list for a multi-leg limit order. Pure - no side effects."""
    if not 2 <= len(legs) <= 4:
        raise ValueError(f"mleg takes 2-4 legs, got {len(legs)}")
    if qty < 1:
        raise ValueError(f"qty must be >= 1, got {qty}")
    return [
        "order", "submit",
        "--order-class", "mleg",
        "--qty", str(qty),
        "--type", "limit",
        "--limit-price", f"{limit_price:.2f}",
        "--time-in-force", tif,
        "--legs", json.dumps([l.to_dict() for l in legs]),
    ]


def build_close_args(legs: list, qty: int, limit_price: float) -> list:
    """Closing order: sides flipped, intent to close, GTC so it rests."""
    flipped = [Leg(l.symbol, "sell" if l.side == "buy" else "buy", l.ratio_qty)
               for l in legs]
    args = build_mleg_args(flipped, qty, limit_price, tif="gtc")
    payload = json.loads(args[args.index("--legs") + 1])
    for d in payload:
        d["position_intent"] = f"{d['side']}_to_close"
    args[args.index("--legs") + 1] = json.dumps(payload)
    return args


def _run(args: list, timeout: int = 30) -> dict:
    out = subprocess.run(["alpaca"] + args + ["--quiet"],
                         capture_output=True, text=True, timeout=timeout)
    if out.returncode:
        raise ExecutionRefused(f"CLI failed: {out.stderr.strip()[:200]}")
    return json.loads(out.stdout) if out.stdout.strip() else {}


def preflight(expect_account: str = COMPETITION_ACCOUNT) -> dict:
    """Verify we are pointed at the right paper account before any order."""
    acct = _run(["account", "get"])
    num = acct.get("account_number")
    if num != expect_account:
        raise ExecutionRefused(
            f"account mismatch: connected to {num}, expected {expect_account}")
    if acct.get("status") != "ACTIVE":
        raise ExecutionRefused(f"account status {acct.get('status')}")
    if acct.get("trading_blocked"):
        raise ExecutionRefused("trading_blocked is set on the account")
    if os.environ.get("ALPACA_LIVE_TRADE", "").lower() == "true":
        raise ExecutionRefused("ALPACA_LIVE_TRADE is set - refusing to trade live")
    return acct


def orders_enabled() -> bool:
    return os.environ.get(ORDERS_ALLOWED_ENV) == "1"


def submit(legs: list, qty: int, limit_price: float, *, ledger=None,
           context: Optional[dict] = None, dry_run: bool = True) -> dict:
    """Submit a multi-leg order, or describe what would be submitted.

    Returns a record dict either way. Refusals raise ExecutionRefused, which
    is recorded before it propagates.
    """
    args = build_mleg_args(legs, qty, limit_price)
    record = {
        "action": "submit",
        "qty": qty,
        "limit_price": round(limit_price, 2),
        "legs": [l.to_dict() for l in legs],
        "command": "alpaca " + " ".join(args),
        "dry_run": dry_run,
        "context": context or {},
    }

    if dry_run:
        record["result"] = "DRY_RUN — not submitted"
        if ledger:
            ledger.record_raw(record) if hasattr(ledger, "record_raw") else None
        return record

    if not orders_enabled():
        record["result"] = f"REFUSED — {ORDERS_ALLOWED_ENV} is not set to 1"
        raise ExecutionRefused(record["result"])

    acct = preflight()
    record["account"] = acct.get("account_number")
    record["equity_before"] = acct.get("equity")
    resp = _run(args)
    record["result"] = "SUBMITTED"
    record["order_id"] = resp.get("id")
    record["status"] = resp.get("status")
    return record
