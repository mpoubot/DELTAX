"""Per-cycle narration — what the agent saw, held, did, and decided.

The prior output printed a refusal list and nothing else: no account state, no
running P&L, no per-position detail, no reason a position was still held. For a
team watching an autonomous system that is unreadable.

Every cycle now narrates itself: header, scoreboard, one line per open position
with its exit target and distance to it, one line per action taken, and a
closing decision summary. Options-native — a condor's story is credit captured
and distance to the short strike, not a trailing stop.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta

# Neon-green terminal on black, matching the team's reference screen. Green is
# the ground state; colour is reserved for things that need a second look.
C = {"g": "\033[38;5;46m",    # neon green — the default voice
     "gd": "\033[38;5;40m",   # dimmer green — structure and rules
     "r": "\033[38;5;196m",   # red — losses, breaches
     "y": "\033[38;5;226m",   # yellow — holds, take-profit
     "c": "\033[38;5;51m",    # cyan — headers and timestamps
     "d": "\033[38;5;28m",    # deep green — muted detail
     "w": "\033[38;5;231m",   # white — the numbers that matter
     "b": "\033[1m", "x": "\033[0m"}
ET = timezone(timedelta(hours=-4))
START_EQUITY = 100_000.0


def _pct(v, w=6):
    s = f"{v:+.1f}%"
    return f"{C['g'] if v >= 0 else C['r']}{s:>{w}}{C['x']}"


def _money(v):
    return f"{C['g'] if v >= 0 else C['r']}{v:+,.2f}{C['x']}"


def header(equity, cash, market_open, now=None):
    """Opens each 5-minute block. The rule above it is the visual break the
    team reads cycles by — without it the log is one undifferentiated wall."""
    now = now or datetime.now(ET)
    day = (equity / START_EQUITY - 1) * 100
    state = f"{C['g']}MARKET OPEN{C['x']}" if market_open else f"{C['d']}MARKET CLOSED{C['x']}"
    rule = f"{C['d']}{'─' * 96}{C['x']}"
    return (f"{rule}\n"
            f"{C['c']}┌── {now:%a %H:%M} ET{C['x']} │ {state} │ "
            f"account {C['w']}${equity:,.2f}{C['x']} ({_pct(day)} today) │ "
            f"cash {C['w']}${cash:,.0f}{C['x']}")


def scoreboard(equity, realized, unrealized):
    net = equity - START_EQUITY
    return (f"{C['gd']}│{C['x']} {C['b']}{C['g']}SCOREBOARD{C['x']}  "
            f"realized {_money(realized)} (banked)  │  "
            f"unrealized {_money(unrealized)} (open)  │  "
            f"net {_money(net)} vs ${START_EQUITY:,.0f} start")


def position_line(p):
    """One open condor leg: what it is, what it's worth, where it exits."""
    cap = p.get("captured")
    cur, cr = p.get("current"), p.get("credit", 0.0)
    tgt = round(cr * 0.5, 2)
    dist = p.get("strike_distance_pct")
    bits = [f"{C['gd']}│{C['x']} {C['w']}{p['symbol']:<5}{C['x']} ✋ {C['y']}HOLDING{C['x']} "
            f"{p['side']} {p['short']:g}/{p['long']:g}"]
    if cur is not None:
        bits.append(f"cr {cr:.2f} → {cur:.2f}")
    if cap is not None:
        bits.append(f"captured {_pct(cap * 100, 5)}")
    bits.append(f"exits at {C['g']}{tgt:.2f}{C['x']}")
    if dist is not None:
        bits.append(f"short strike {C['d']}{dist:+.1f}% away{C['x']}")
    bits.append(f"{p.get('dte','?')} DTE")
    return "  │  ".join(bits)


def event(kind, sym, text):
    icon, col = {"open": ("🟢", "g"), "exit": ("💰", "y"), "close": ("💰", "y"),
                 "refuse": ("⛔", "d"), "fail": ("❌", "r")}.get(kind, ("•", "d"))
    return f"{C['gd']}│{C['x']} {C[col]}[{sym}]{C['x']} {icon} {C[col]}{text}{C['x']}"


def refusal_summary(refused, limit=6):
    """Group refusals by gate — 38 individual lines tell nobody anything."""
    by = {}
    for sym, side, gate in refused:
        by.setdefault(gate, []).append(f"{sym}/{side}")
    out = []
    for gate, names in sorted(by.items(), key=lambda kv: -len(kv[1])):
        shown = ", ".join(names[:limit])
        more = f" +{len(names)-limit} more" if len(names) > limit else ""
        out.append(f"{C['gd']}│{C['x']} {C['d']}⛔ {len(names):>2} × {gate:<16}{C['x']} "
                   f"{C['d']}{shown}{more}{C['x']}")
    return out


def decision(held, opened, closed, refused, regime, permission):
    parts = []
    if opened: parts.append(f"{C['g']}opened {opened}{C['x']}")
    if closed: parts.append(f"{C['y']}closed {closed}{C['x']}")
    if held:   parts.append(f"{C['y']}holding {held}{C['x']}")
    if refused: parts.append(f"{C['d']}refused {refused}{C['x']}")
    if not parts: parts.append(f"{C['d']}no action{C['x']}")
    pc = {"NORMAL": "g", "CAUTION": "y", "DEFENSIVE": "y",
          "NO_NEW_POSITIONS": "r", "HALT": "r"}.get(permission, "d")
    return (f"{C['c']}└── DECISION:{C['x']} " + ", ".join(parts) +
            f"  {C['d']}│{C['x']} regime {regime}  "
            f"{C['d']}│{C['x']} permission {C[pc]}{permission}{C['x']}")


def render(*, equity, cash, market_open, realized=0.0, unrealized=0.0,
           positions=(), events=(), refused=(), regime="—", permission="—"):
    lines = [header(equity, cash, market_open), scoreboard(equity, realized, unrealized)]
    for p in positions:
        lines.append(position_line(p))
    for kind, sym, text in events:
        lines.append(event(kind, sym, text))
    if not positions and not events:
        lines.append(f"{C['gd']}│{C['x']} {C['d']}no open positions{C['x']}")
    lines += refusal_summary(list(refused))
    lines.append(decision(len(positions), sum(1 for e in events if e[0] == "open"),
                          sum(1 for e in events if e[0] == "close"),
                          len(refused), regime, permission))
    return "\n".join(lines)
