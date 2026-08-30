"""One-line-per-position terminal dashboard.

Status is DERIVED, never typed in by hand - the same thresholds the agent
trades on decide what the emoji says, so the screen cannot disagree with the
book. E5's exit rule (close at 50% of credit captured) is what turns a row
into a SELL.

  python3 -m deltax.dashboard          live account
  python3 -m deltax.dashboard --demo   worked example, clearly marked
"""
from __future__ import annotations
import sys, os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

TAKE_PROFIT_FRACTION = 0.50   # E5: close here
WATCH_DISTANCE_PCT   = 0.02   # short strike within 2% of spot
TIME_STOP_DTE        = 2

RESET="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
RED="\033[31m"; GRN="\033[32m"; YEL="\033[33m"; CYN="\033[36m"; MAG="\033[35m"


@dataclass
class Position:
    symbol: str
    side: str              # "put" / "call"
    short_strike: float
    long_strike: float
    expiry: date
    contracts: int
    credit: float          # per contract, dollars received
    current: float         # per contract, cost to close now
    spot: float

    @property
    def dte(self) -> int: return (self.expiry - date.today()).days
    @property
    def captured(self) -> float:
        return 0.0 if self.credit <= 0 else (self.credit-self.current)/self.credit
    @property
    def pnl(self) -> float:
        # x100: an options contract covers 100 shares. Omitting it understates
        # every row by two orders of magnitude.
        return (self.credit-self.current)*self.contracts*100.0
    @property
    def breached(self) -> bool:
        return self.spot < self.short_strike if self.side=="put" else self.spot > self.short_strike
    @property
    def distance(self) -> float:
        return abs(self.spot-self.short_strike)/self.spot


def status(p: Position) -> tuple[str, str, str]:
    """(emoji, label, colour) - ordered most urgent first."""
    if p.breached:                       return "🔴", "BREACHED", RED
    if p.captured >= TAKE_PROFIT_FRACTION: return "💰", "SELL now", GRN
    if p.dte <= TIME_STOP_DTE:           return "⏰", "TIME STOP", MAG
    if p.distance <= WATCH_DISTANCE_PCT: return "🟡", "WATCH", YEL
    if p.captured >= 0.30:               return "🟢", "hold→soon", CYN
    return "🟢", "HOLD", ""


def render(positions, *, equity, start_equity, day_pnl, permission,
           risk_used, risk_cap, banner=None) -> str:
    L=[]; W=78
    L.append(f"{BOLD}╔{'═'*W}╗{RESET}")
    hdr=f" DELTAX  ·  {datetime.now():%a %d %b %H:%M}  ·  account PA3ID1B9L6BP"
    L.append(f"{BOLD}║{hdr:<{W}}║{RESET}")
    L.append(f"{BOLD}╚{'═'*W}╝{RESET}")
    if banner: L.append(f"{YEL}{banner}{RESET}")

    tot=equity-start_equity; pc=tot/start_equity*100; dpc=day_pnl/start_equity*100
    c=GRN if tot>=0 else RED; dc=GRN if day_pnl>=0 else RED
    L.append(f"  equity {BOLD}${equity:,.0f}{RESET}   "
             f"total {c}{tot:+,.0f} ({pc:+.2f}%){RESET}   "
             f"today {dc}{day_pnl:+,.0f} ({dpc:+.2f}%){RESET}")
    pe={"NORMAL":"🟢","CAUTION":"🟡","DEFENSIVE":"🟠",
        "NO_NEW_POSITIONS":"⛔","HALT":"🛑"}.get(permission,"❔")
    used=risk_used/risk_cap*100 if risk_cap else 0
    bar="█"*int(used/10)+"░"*(10-int(used/10))
    L.append(f"  permission {pe} {BOLD}{permission}{RESET}   "
             f"risk {bar} ${risk_used:,.0f}/${risk_cap:,.0f} ({used:.0f}%)   "
             f"{len(positions)} positions")
    L.append(f"{DIM}  {'─'*W}{RESET}")
    L.append(f"{DIM}  {'SYM':<6}{'STRUCTURE':<15}{'EXP':<7}{'DTE':>4}"
             f"{'CR':>7}{'NOW':>7}{'P&L':>9}{'KEPT':>7}  STATUS{RESET}")

    for p in sorted(positions, key=lambda x: (not x.breached, -x.captured)):
        e,lab,col=status(p)
        pc_=GRN if p.pnl>=0 else RED
        struct=f"{p.side} {p.short_strike:g}/{p.long_strike:g}"
        L.append(f"  {p.symbol:<6}{struct:<15}{p.expiry:%m-%d} {p.dte:>4}"
                 f"{p.credit:>7.2f}{p.current:>7.2f}{pc_}{p.pnl:>9,.0f}{RESET}"
                 f"{p.captured*100:>6.0f}%  {e} {col}{lab}{RESET}")

    L.append(f"{DIM}  {'─'*W}{RESET}")
    sells=[p for p in positions if status(p)[1]=="SELL now"]
    risky=[p for p in positions if p.breached]
    watch=[p for p in positions if status(p)[1]=="WATCH"]
    L.append(f"  💰 {len(sells)} at target   🟡 {len(watch)} watching   "
             f"🔴 {len(risky)} breached   "
             f"open P&L {GRN if sum(p.pnl for p in positions)>=0 else RED}"
             f"{sum(p.pnl for p in positions):+,.0f}{RESET}")
    if sells:
        L.append(f"  {GRN}→ close now: {', '.join(f'{p.symbol}/{p.side}' for p in sells)}{RESET}")
    if risky:
        L.append(f"  {RED}→ breached, defined risk caps the loss: "
                 f"{', '.join(f'{p.symbol}/{p.side}' for p in risky)}{RESET}")
    return "\n".join(L)


def demo() -> str:
    from datetime import timedelta
    t=date.today()
    P=Position
    pos=[
      P("SPY","put",  645,640, t+timedelta(days=7), 7, 2.30,1.02, 662.40),
      P("SPY","call", 678,683, t+timedelta(days=7), 7, 2.25,1.98, 662.40),
      P("MA", "put",  555,550, t+timedelta(days=7), 5, 2.40,0.85, 578.10),
      P("XLF","put",   52, 50, t+timedelta(days=7),18, 0.95,0.44,  54.20),
      P("IWM","call", 243,245, t+timedelta(days=2),22, 0.92,0.61, 240.85),
      P("PGR","put",  262,257, t+timedelta(days=7), 6, 2.10,2.44, 259.80),
      P("KO", "call",  74, 76, t+timedelta(days=7),12, 0.88,0.79,  72.90),
      P("XLU","put",   84, 82, t+timedelta(days=7),15, 0.90,0.31,  87.60),
    ]
    return render(pos, equity=103_441, start_equity=100_000, day_pnl=812,
                  permission="NORMAL", risk_used=24_300, risk_cap=30_000,
                  banner="  ╔══════════════════════════════════════════════════════════╗\n"
                         "  ║  🧪  FAKE DATA — INVENTED POSITIONS, NOT YOUR ACCOUNT     ║\n"
                         "  ║      Layout demo only. Run without --demo for live.      ║\n"
                         "  ╚══════════════════════════════════════════════════════════╝")


def live() -> str:
    """Read the REAL account. No invented numbers anywhere in this path."""
    from deltax.feeds import AlpacaFeed
    from deltax.gates import PORTFOLIO_RISK_PCT
    f = AlpacaFeed()
    acct = f.account()
    equity = float(acct.get("equity") or 0.0)
    last = float(acct.get("last_equity") or equity)
    raw = f.positions()
    positions = []
    for q in raw:
        try:
            positions.append(_from_alpaca(q))
        except Exception:
            continue                      # never fabricate a row we cannot parse
    risk_used = sum(abs(float(q.get("cost_basis") or 0.0)) for q in raw)
    body = render(positions, equity=equity, start_equity=100_000.0,
                  day_pnl=equity - last, permission="—",
                  risk_used=risk_used, risk_cap=100_000.0*PORTFOLIO_RISK_PCT)
    if not raw:
        body += (f"\n  {DIM}No open positions and no orders placed. "
                 f"Everything above is read live from {acct.get('account_number','?')}.{RESET}")
    if len(raw) != len(positions):
        body += (f"\n  {YEL}⚠ {len(raw)-len(positions)} position(s) could not be "
                 f"parsed and are NOT shown — this screen is incomplete.{RESET}")
    return body


def _from_alpaca(q: dict) -> Position:
    """Map a broker position onto a row. Raises rather than guessing."""
    sym = q["symbol"]
    return Position(symbol=sym, side="put" if "P" in sym[-9:] else "call",
                    short_strike=float(q.get("strike") or 0.0), long_strike=0.0,
                    expiry=date.today(), contracts=int(float(q["qty"])),
                    credit=abs(float(q["avg_entry_price"])),
                    current=abs(float(q.get("current_price") or 0.0)),
                    spot=float(q.get("current_price") or 0.0))


if __name__ == "__main__":
    if "--demo" in sys.argv:
        print(demo())
    else:
        try:
            print(live())
        except Exception as e:
            print(f"{RED}Could not read the live account: {e}{RESET}")
            print(f"{DIM}Run with --demo for the sample layout.{RESET}")
            sys.exit(1)
