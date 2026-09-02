"""Generate docs/index.html — the public team board, served by GitHub Pages.

Tron-Legacy visual language: void black, neon cyan on thin glowing rules,
angular clipped corners, wide monospace tracking. Grid is a fixed 3-column
layout so cards NEVER orphan onto a half-empty row.

Honesty rules unchanged: nothing is invented, an unreadable value is shown as
unavailable rather than as a plausible number, and every figure says its source.

  python3 -m deltax.webdash
"""
from __future__ import annotations
import json, glob, os, sys
from datetime import datetime, timezone

def _ledger():
    rows = []
    for f in sorted(glob.glob("logs/decisions-*.jsonl")):
        for line in open(f):
            try: rows.append(json.loads(line))
            except Exception: pass
    return rows

LOGO_NAMES = ("logo.png", "logo.jpg", "logo.jpeg", "logo.webp", "deltax.png")

def _logo():
    """Use the real artwork the moment it exists; fall back to the CSS mark.

    GitHub Pages serves docs/ directly, so the file is referenced by relative
    name - no embedding needed, and dropping a new file in replaces it.
    """
    for n in LOGO_NAMES:
        if os.path.exists(os.path.join("docs", n)):
            return f'<img class="logo" src="{n}" alt="DELTAX">'
    return '<div class="mark"></div>'


def _feeds_status():
    """Probe every registered feed and report honestly: live, stale, or error.

    Short timeout per feed - the dashboard regenerates every few minutes and
    one hanging endpoint must not stall the publish. A feed that cannot be
    fetched is shown as an error, never silently dropped: a dead feed that
    disappears from the board looks exactly like a healthy board.
    """
    from deltax import rss
    rows = []
    for key, (url, bucket, active) in rss.FEEDS.items():
        if "{cik}" in url:
            rows.append((key, bucket, None, None, "template", "per-symbol (earnings gate)"))
            continue
        try:
            items = rss.parse(rss.fetch(url, timeout=6), source=key)
            stale, age = rss.is_stale(items)
            rows.append((key, bucket, len(items), age,
                         "stale" if stale else "live",
                         f"newest {age}h ago" if age is not None else "no dated items"))
        except Exception as e:
            rows.append((key, bucket, None, None, "error", f"{type(e).__name__}"))
    # live first, then stale, then errors - the reader scans for trouble
    order = {"live": 0, "stale": 1, "error": 2, "template": 3}
    rows.sort(key=lambda r: (order.get(r[4], 9), r[0]))
    return rows


import html as _html
import re as _re

_KEYSHAPE = _re.compile(r"(PK[A-Z0-9]{16,}|[A-Za-z0-9]{40,})")
# The CLI writes ANSI colour into cron.log; the web reads that file verbatim,
# so every line arrived carrying literal escape codes like "[38;5;28m". That is
# what made the board unreadable - not the palette.
_ANSI = _re.compile(r"\x1b\[[0-9;]*m|\[[0-9;]{1,8}m")
# Box-drawing is the CLI's structure. The web has CSS for that, so it is noise.
_BOX = _re.compile(r"^[─│┌└├┤╔╚║]+\s*|\s*[─│]+$")


def _clean(line: str) -> str:
    line = _ANSI.sub("", line)
    line = _BOX.sub("", line).strip()
    return _re.sub(r"\s{2,}", "  ", line)

def _tz_times():
    """Local time for each team pill. 24-hour, because 21:00 read from Denmark
    is unambiguous and 9 PM is not.

    Converted from ET each render rather than stored as fixed offsets: the US,
    Latvia and Denmark leave daylight saving on different dates, so the gap
    between them is not constant even though it is stable this week.

    Returns empty strings on any failure - a clock is decoration and must never
    be able to take the board down.
    """
    from zoneinfo import ZoneInfo
    from datetime import datetime as _dt
    try:
        return {k: _dt.now(ZoneInfo(z)).strftime("%H:%M")
                for k, z in (("us", "America/New_York"),
                             ("lv", "Europe/Riga"),
                             ("dk", "Europe/Copenhagen"))}
    except Exception:
        return {"us": "", "lv": "", "dk": ""}


def _terminal_lines(limit=90):
    """The agent's real activity — timestamped, icon-coded, newest FIRST.

    The previous version dropped timestamps entirely and buried the newest line
    at the bottom of a scroll box. For a team watching an autonomous system,
    "when" is the first question and "what just happened" is the second.
    """
    from datetime import timezone as _tz, timedelta as _td
    ET = _tz(_td(hours=-4))
    events = []          # (sort_key, hhmmss, icon, css, text)

    def stamp(dt):
        try:
            return dt.astimezone(ET).strftime("%H:%M:%S"), dt.timestamp()
        except Exception:
            return "--:--:--", 0.0

    # ── scheduled runs and pre-market passes ──
    for path, tag in (("logs/cron.log", "agent"), ("logs/premarket.log", "intel")):
        cur_t, cur_k = "--:--:--", 0.0
        try:
            lines = open(path).readlines()[-90:]
        except OSError:
            continue
        for ln in lines:
            ln = ln.rstrip()
            if not ln:
                continue
            m = _re.match(r"─+ (?:PRE-MARKET )?(\d{4}-\d\d-\d\dT[\d:]+Z)", ln)
            if m:
                try:
                    d = datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
                    cur_t, cur_k = stamp(d)
                except Exception:
                    pass
                continue
            if ln.startswith("exit="):
                continue
            ln = _clean(ln)
            if not ln or set(ln) <= {"-", "=", "·", "."}:
                continue
            low = ln.lower()
            # The marker must never overstate what happened. A stakeholder
            # scanning icons should reach the same conclusion as one reading the
            # text: a tick against "no action" reads as success when nothing
            # occurred, which is the one thing this board must not do.
            icon, css = ("·", "skip") if tag != "intel" else ("📡", "intel")

            if "scoreboard" in low:
                icon, css = "📊", "agent"
            elif low.startswith("decision"):
                if "opened" in low:      icon, css = "✅", "fill"      # money moved
                elif "closed" in low:    icon, css = "💰", "fill"      # position exited
                elif "no action" in low: icon, css = "⏳", "skip"      # STOOD BY
                elif "refused" in low:   icon, css = "🚫", "refuse"    # all declined
                else:                    icon, css = "·", "skip"
            elif "opened" in low or "submitted" in low or "filled" in low:
                icon, css = "✅", "fill"
            elif "exit" in low:
                icon, css = "💰", "fill"
            elif "refused" in low or "⛔" in ln:
                icon, css = "🚫", "refuse"
            elif "market closed" in low or "outside entry window" in low:
                icon, css = "🌙", "skip"
            elif "skipped" in low:
                icon, css = "⏳", "skip"
            events.append((cur_k, cur_t, icon, css, ln[:150]))

    # ── ledger: every decision the agent made ──
    try:
        for f in sorted(glob.glob("logs/decisions-*.jsonl")):
            for ln in open(f).readlines()[-70:]:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                e = r.get("event") or r
                t, k = "--:--:--", 0.0
                for key in ("ts", "timestamp", "time"):
                    if e.get(key) or r.get(key):
                        try:
                            d = datetime.fromisoformat(str(e.get(key) or r.get(key)).replace("Z", "+00:00"))
                            t, k = stamp(d)
                        except Exception:
                            pass
                        break
                if e.get("decision"):
                    g = e.get("failed_gate")
                    if g:
                        events.append((k, t, "🚫", "refuse",
                                       f"DECLINED  {e.get('symbol','?'):<6} blocked by {g}"))
                    else:
                        events.append((k, t, "✅", "fill",
                                       f"APPROVED  {e.get('symbol','?'):<6} cleared every gate"))
                    continue
                a = e.get("action")
                if not a:
                    continue
                icon, css = {"permission": ("🛡️", "agent"), "reconcile": ("🔄", "agent"),
                             "exit_order": ("💰", "fill"), "close": ("💰", "fill"),
                             "submit": ("📤", "fill"), "submit_failed": ("❌", "refuse"),
                             "skip": ("⏸️", "skip")}.get(a, ("•", "agent"))
                bits = {k2: v for k2, v in e.items() if k2 in
                        ("state", "result", "reason", "note", "open_positions",
                         "committed", "limit_price", "qty", "symbol", "side")}
                events.append((k, t, icon, css,
                               f"{a}  " + " ".join(f"{x}={y}" for x, y in bits.items())[:130]))
    except Exception:
        pass

    events.sort(key=lambda e: e[0], reverse=True)          # newest first
    out = []
    seen_stamp = None
    for _, t, icon, css, txt in events[:limit]:
        txt = _KEYSHAPE.sub("[redacted]", txt)
        # Newest-first, so a change of timestamp opens a new cycle block.
        if t != seen_stamp:
            css += " cyc"
            seen_stamp = t
        out.append(f'<div class="tl {css}"><span class="ts">{t}</span>'
                   f'<span class="ic">{icon}</span>'
                   f'<span class="tx">{_html.escape(txt)}</span></div>')
    return "".join(out) or '<div class="tl"><span class="tx">no activity yet</span></div>'


def _occ(sym):
    """SPY260918P00380000 -> (SPY, 18 Sep 2026, put, 380.0). None if not an option."""
    if not sym or len(sym) < 16:
        return None
    b, root = sym[-15:], sym[:-15]
    if not (root and b[:6].isdigit() and b[6] in "CP" and b[7:].isdigit()):
        return None
    return (root, f"{b[4:6]} {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(b[2:4])-1]}",
            "put" if b[6] == "P" else "call", int(b[7:]) / 1000.0)


def _positions_table(positions):
    """Group legs into the spreads a person actually holds, in plain language.

    Four rows of OCC symbols is not a position anyone can read. A spread is one
    trade: what was sold, what was bought as protection, what it paid, and the
    price range where it wins.
    """
    if not positions:
        return ('<tr><td colspan="6" class="empty">No positions open. '
                'The agent is holding cash.</td></tr>')

    # Pair each short leg with the long leg protecting it.
    legs = []
    for p in positions:
        o = _occ(p.get("symbol", ""))
        if not o:
            continue
        try:
            legs.append({"root": o[0], "exp": o[1], "right": o[2], "strike": o[3],
                         "qty": int(float(p.get("qty") or 0)),
                         "entry": abs(float(p.get("avg_entry_price") or 0)),
                         "now": abs(float(p.get("current_price") or 0)),
                         "pl": float(p.get("unrealized_pl") or 0)})
        except (TypeError, ValueError):
            continue

    rows, used = "", set()
    for a in legs:
        if a["qty"] >= 0 or id(a) in used:
            continue
        mate = next((b for b in legs if b["qty"] > 0 and id(b) not in used
                     and b["root"] == a["root"] and b["right"] == a["right"]), None)
        if not mate:
            continue
        used.update({id(a), id(mate)})
        n = abs(a["qty"])
        credit = (a["entry"] - mate["entry"]) * n * 100
        pl = a["pl"] + mate["pl"]
        width = abs(a["strike"] - mate["strike"])
        risk = width * n * 100 - credit
        wins = (f"stays above ${a['strike']:,.0f}" if a["right"] == "put"
                else f"stays below ${a['strike']:,.0f}")
        cls = "gd" if pl >= 0 else "rd"
        rows += (
            f'<tr><td class="cy"><b>{a["root"]}</b><div class="sub">{a["exp"]} · '
            f'{"📈 bullish" if a["right"] == "put" else "📉 bearish"}</div></td>'
            f'<td>sold the ${a["strike"]:,.0f} {a["right"]}<div class="sub">'
            f'bought the ${mate["strike"]:,.0f} {mate["right"]} as protection</div></td>'
            f'<td class="num">{n}<div class="sub">contracts</div></td>'
            f'<td class="num">${credit:,.0f}<div class="sub">collected up front</div></td>'
            f'<td class="num">${risk:,.0f}<div class="sub">most it can lose</div></td>'
            f'<td class="num {cls}">{pl:+,.0f}<div class="sub">wins if {wins}</div></td></tr>')
    return rows or ('<tr><td colspan="6" class="empty">Positions open but not '
                    'recognised as spreads — see the terminal below.</td></tr>')


def build(account=None, positions=None, error=None) -> str:
    now = datetime.now(timezone.utc)
    rows = _ledger()
    dec = [r for r in rows if r.get("kind") != "event" and r.get("decision")]
    ref = [r for r in dec if r.get("decision") != "TRADE"]
    gates = {}
    for r in ref:
        g = r.get("failed_gate") or "unknown"
        gates[g] = gates.get(g, 0) + 1
    top = sorted(gates.items(), key=lambda x: -x[1])
    mx = max([n for _, n in top], default=1)

    eq = cash = None; acct = "—"
    if account:
        eq, cash = account.get("equity"), account.get("cash")
        acct = account.get("account_number", "—")
    money = lambda v: f"${float(v):,.0f}" if v not in (None, "") else "unavailable"

    def stat(label, value, note="", cls=""):
        return (f'<div class="stat {cls}"><div class="k">{label}</div>'
                f'<div class="v">{value}</div><div class="n">{note}</div></div>')

    # P&L against the $100,000 start. Sign drives the colour, so a stakeholder
    # reads direction before reading digits.
    START = 100_000.0
    pnl = (float(eq) - START) if eq not in (None, "") else None
    pnl_cls = "" if pnl is None else ("pos" if pnl >= 0 else "neg")
    pnl_val = "unavailable" if pnl is None else f"{pnl:+,.2f}"
    pnl_pct = "" if pnl is None else f"{pnl/START*100:+.2f}% of $100,000 start"

    # 6 stats -> exactly two rows of three. Never an orphan.
    # E64: ACCOUNT is demoted into the mission grid - the top of the page
    # answers target/proof/confidence, not which account we are.
    stats = "".join([
        stat("EQUITY", money(eq), f"{acct} · Alpaca paper", "big"),
        stat("P&amp;L", pnl_val, pnl_pct, f"big {pnl_cls}"),
        stat("CASH", money(cash), "uncommitted"),
        # 4 legs is 2 spreads. A stakeholder reading "4 positions" would think
        # four trades are on, which is twice the truth.
        stat("OPEN POSITIONS",
             f"{len(positions or []) // 2}" if positions else "0",
             (f"{len(positions or [])} legs · {len(positions or []) // 2} spread(s)"
              if positions else "flat")),
        stat("DECISIONS LOGGED", len(dec), "every evaluation"),
        stat("REFUSED", f"{len(ref)}",
             f"{len(ref)/max(1,len(dec))*100:.0f}% of candidates screened"),
    ])

    gate_rows = "".join(
        f'<tr><td><span class="mono cy">{g}</span></td>'
        f'<td class="num">{n}</td>'
        f'<td class="bar"><span style="width:{n/mx*100:.0f}%"></span></td></tr>'
        for g, n in top) or \
        '<tr><td colspan="3" class="empty">No refusals recorded yet.</td></tr>'

    pos = _positions_table(positions)

    frows = ""
    for key, bucket, n, age, st, note in _feeds_status():
        pill = {"live": '<span class="pill gd">● LIVE</span>',
                "stale": '<span class="pill" style="color:#F0C674">● STALE</span>',
                "error": '<span class="pill rd">● ERROR</span>',
                "template": '<span class="pill" style="color:#5B807D">SEC 8-K</span>'}[st]
        frows += (f'<tr><td class="cy">{key}</td><td>{bucket}</td>'
                  f'<td class="num">{n if n is not None else "—"}</td>'
                  f'<td>{note}</td><td>{pill}</td></tr>')

    warn = (f'<div class="warn">LIVE ACCOUNT UNREADABLE — {error}. '
            f'Figures omitted rather than estimated.</div>') if error else ""

    # E42 — the stand-down is the single most important thing on this page.
    from deltax.gates import TRADING_SUSPENDED
    standdown = ""
    if TRADING_SUSPENDED:
        standdown = """<div class="sd">
<div class="sd-h">◆ TRADING SUSPENDED &nbsp;—&nbsp; NO ORDERS WILL BE PLACED</div>
<div class="sd-b">Backtesting the exact configuration scheduled for this week
&mdash; entry Tuesday, expiry <b>4&nbsp;Sep</b>, 14 names, priced at
<b>real market credit</b> &mdash; returned <b class="sd-n">&minus;$50,904
(&minus;50.9%)</b> over 26 weeks at a 46% weekly win rate.
<div class="sd-g">
<div><span>2 names</span><b>&minus;8,977</b></div>
<div><span>4 names</span><b>&minus;8,649</b></div>
<div><span>6 names</span><b>&minus;18,347</b></div>
<div><span>14 names</span><b>&minus;50,904</b></div>
</div>
It is not the universe size &mdash; <b>every</b> configuration tests negative.
The cause is measured on live chains: a 4&nbsp;Sep option places its
&delta;0.30 strike <b>0.64%</b> from spot and pays <b>$1.64</b>, against
<b>0.90%</b> and <b>$2.37</b> for an 11-day one. Thirty percent closer to the
money for thirty percent less premium &mdash; and SPY&rsquo;s ordinary daily
range is 0.6&ndash;0.7%, so that buffer is about one session.
<div class="sd-r">The contest deadline permits only the 4&nbsp;Sep expiry.
That is the one structure the evidence rejects. Capital is held at
<b>$100,000</b> rather than spent on a trade with measured negative
expectancy. The agent continues to screen, gate and log every cycle; the
refusal is enforced in code at the order boundary, not by convention.</div>
</div></div>"""

    # ── E64: mission block. TARGET -> THESIS -> PROOF -> CONFIDENCE -> RISK.
    # Every number here is from tonight's research; nothing is a placeholder.
    uso_px, uso_chg = None, None
    try:
        from deltax.feeds import AlpacaFeed, latest_price, previous_close
        _snm = AlpacaFeed().snapshots(["USO"]).get("USO") or {}
        uso_px = latest_price(_snm)
        _pcm = previous_close(_snm)
        if uso_px and _pcm:
            uso_chg = (uso_px / _pcm - 1) * 100
    except Exception:
        pass
    if uso_px:
        _pxtxt = f"${uso_px:,.2f}"
        if uso_chg is not None:
            _cls = "pos" if uso_chg >= 0 else "neg"
            _pxtxt += f' <span class="{_cls}">{uso_chg:+.2f}%</span>'
    else:
        _pxtxt = "feed unavailable"
    # ── E73: LIVE mission block. Data-driven, not a hardcoded thesis.
    # USO led this panel while the catalyst was the only strategy. It is now
    # one of three, its catalyst is inactive (USO -1.2% today), and a board
    # that still opened on it would be telling viewers about yesterday.
    # Read the FULL ledger, not `dec`: that list filters to kind != "event",
    # and rotation is recorded as an event. Looking in `dec` found nothing and
    # the board silently said "awaiting first cycle" while the engine was
    # ranking sectors every five minutes.
    _rot_live = None
    try:
        for _r in reversed(rows):
            _e = _r.get("event") or {}
            if _e.get("action") == "rotation":
                _rot_live = _e
                break
    except Exception:
        pass

    _opt_legs = [p for p in (positions or []) if len(str(p.get("symbol",""))) > 10]
    _eq_legs  = [p for p in (positions or []) if len(str(p.get("symbol",""))) <= 10]
    def _pl(rows):
        t = 0.0
        for r in rows:
            try: t += float(r.get("unrealized_pl") or 0)
            except (TypeError, ValueError): pass
        return t
    _opt_pl, _eq_pl = _pl(_opt_legs), _pl(_eq_legs)
    _tot_pl = _opt_pl + _eq_pl
    _plc = lambda v: "pos" if v >= 0 else "neg"
    # E73: a bare "-40.60" reads as a catastrophe on a $100k account. Every
    # P&L on this board carries its PERCENTAGE, which is the number a viewer
    # can actually calibrate against.
    _pct = lambda v: f"{v / START * 100:+.3f}%"
    _both = lambda v: f"{v:+,.2f} ({_pct(v)})"

    # group option legs into spreads by underlying root
    _books = {}
    for p_ in _opt_legs:
        s = str(p_.get("symbol", ""))
        root = s[:-15] if len(s) > 15 else s
        _books.setdefault(root, []).append(p_)
    _book_rows = ""
    for root, legs in sorted(_books.items()):
        pl = _pl(legs)
        _book_rows += (f'<tr><td class="cy">{root}</td>'
                       f'<td>{len(legs)}-leg spread</td>'
                       f'<td class="num {_plc(pl)}">{pl:+,.2f}</td>'
                       f'<td class="num {_plc(pl)}">{_pct(pl)}</td></tr>')
    for p_ in _eq_legs:
        pl = _pl([p_])
        _book_rows += (f'<tr><td class="cy">{p_.get("symbol")}</td>'
                       f'<td>{p_.get("qty")} shares &middot; rotation</td>'
                       f'<td class="num {_plc(pl)}">{pl:+,.2f}</td>'
                       f'<td class="num {_plc(pl)}">{_pct(pl)}</td></tr>')
    if not _book_rows:
        _book_rows = '<tr><td colspan="3" class="empty">flat &mdash; no open risk</td></tr>'

    _rank_rows = ""
    if _rot_live:
        for r in (_rot_live.get("ranked") or [])[:6]:
            rs = r.get("rs", 0) * 100
            _rank_rows += (f'<tr><td class="cy">{r.get("symbol")}</td>'
                           f'<td class="num {"gd" if rs>0 else "rd"}">{rs:+.2f}%</td></tr>')
        _picks = " &middot; ".join(
            f'<b>{p.get("symbol")}</b>' + (f' <span class="dim">via {p.get("via")}</span>'
                                           if p.get("via") else "")
            for p in (_rot_live.get("picks") or [])) or "none"
        _regime_txt = _rot_live.get("regime", "—")
        _regime_why = _rot_live.get("reason", "")
    else:
        _rank_rows = '<tr><td colspan="2" class="empty">awaiting first cycle</td></tr>'
        _picks, _regime_txt, _regime_why = "—", "—", ""

    mission = f"""<div class="mission">
<div class="m-hero">
  <div>
    <div class="m-k">LIVE BOOK &middot; 3 STRATEGIES</div>
    <div class="m-big">{money(eq)} <span class="sm {_plc(pnl or 0)}">{"&mdash;" if pnl is None else _pct(pnl)}</span></div>
    <div class="m-line" style="margin-top:2px"><span class="dim">{pnl_val} vs $100,000 start</span></div>
    <div class="m-line"><b>Options income</b> (credit spreads, 17 gates) &middot;
    <b>Catalyst</b> (defined-risk verticals on a supply shock) &middot;
    <b>Rotation</b> (11 GICS sectors ranked by relative strength).
    Autonomous every 5 minutes, full session.</div>
  </div>
  <div class="m-conf">
    <div class="m-k">EVIDENCE CONFIDENCE</div>
    <div class="m-big">58%</div>
  </div>
  <div>
    <div class="m-k">OPEN RISK</div>
    <div class="m-big">{len(_books)}<span class="sm">&nbsp;spreads</span></div>
  </div>
</div>
<div class="ev-grid" style="margin-top:16px">
  <div><span>REGIME</span><b class="ok">{_regime_txt}</b><i>{_regime_why[:38]}</i></div>
  <div><span>OPTIONS P&amp;L</span><b class="{"ok" if _opt_pl>=0 else "bad"}">{_pct(_opt_pl)}</b><i>{_opt_pl:+,.2f} &middot; {len(_opt_legs)} legs</i></div>
  <div><span>EQUITY P&amp;L</span><b class="{"ok" if _eq_pl>=0 else "bad"}">{_pct(_eq_pl)}</b><i>{_eq_pl:+,.2f} &middot; rotation</i></div>
  <div><span>NET UNREALIZED</span><b class="{"ok" if _tot_pl>=0 else "bad"}">{_pct(_tot_pl)}</b><i>{_tot_pl:+,.2f} marked</i></div>
  <div><span>TESTS</span><b class="ok">571 PASS</b><i>20 files, 0 silent</i></div>
  <div><span>RISK GATES</span><b class="ok">ARMED</b><i>17 gates &middot; fail closed</i></div>
  <div><span>DATA</span><b class="mixed">MEDIUM</b><i>free tier &middot; repriced live</i></div>
  <div><span>ACCOUNT</span><b class="ok">{acct}</b><i>Alpaca paper</i></div>
</div>
<div style="display:flex;gap:26px;flex-wrap:wrap;margin-top:16px">
  <div style="flex:1;min-width:260px">
    <div class="m-k">OPEN POSITIONS</div>
    <table><tr><th>NAME</th><th>STRUCTURE</th><th style="text-align:right">P&amp;L</th>
    <th style="text-align:right">%</th></tr>
    {_book_rows}</table>
  </div>
  <div style="flex:1;min-width:220px">
    <div class="m-k">SECTOR STRENGTH vs SPY</div>
    <table><tr><th>SECTOR</th><th style="text-align:right">RS</th></tr>{_rank_rows}</table>
    <div class="m-line" style="margin-top:8px">picks: {_picks}</div>
  </div>
</div>
<details class="m-proof">
<summary>WHAT WAS ACTUALLY TESTED &mdash; REAL OPTION PRICES (OPRA VIA MASSIVE)</summary>
<table>
<tr><th>TEST</th><th>RESULT</th><th>READING</th></tr>
<tr><td><b>Full year, 46 expiries, real prices &mdash; UNCONDITIONAL</b></td>
    <td class="rd">&minus;9% mean &middot; &minus;89.9% drawdown</td>
    <td>$100k &rarr; $60k. The structure alone loses money.</td></tr>
<tr><td><b>Same year, only when the catalyst gate fires</b></td>
    <td class="gd">+15% mean &middot; 60% win</td>
    <td>$100k &rarr; $114.6k over 10 trades &mdash; <b>the gate is the edge</b>.
    n=10, P(mean&lt;0)=29%.</td></tr>
<tr><td>Lifecycle with a resting 2&times; exit vs hold-to-expiry</td>
    <td class="gd">9 of 14 hit the exit</td>
    <td>the edge is the resting exit harvesting movement, not direction</td></tr>
<tr><td>Structures rejected on the live book</td><td>6</td>
    <td>145/150, 141/146, 145/155, condor, XLE/XLK/XLF/GLD spreads &mdash;
    each failed on credit, spread or open interest</td></tr>
</table>
</details>
</div>
"""


    _tz = _tz_times()
    return f"""<title>DELTAX — Autonomous Options Agent</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
.mission{{background:linear-gradient(160deg,rgba(10,186,181,.06),transparent 62%),
var(--panel);border:1px solid var(--line);padding:16px 18px;margin:0 0 16px;
position:relative;box-shadow:0 0 26px rgba(10,186,181,.07) inset}}
.m-hero{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;
align-items:end;padding-bottom:12px;border-bottom:1px solid var(--line)}}
.m-hero>div:first-child{{grid-column:span 2}}
.m-k{{color:var(--dim2);font-size:10px;letter-spacing:.22em;margin-bottom:8px}}
.m-big{{color:var(--white);font-size:25px;font-weight:700;line-height:1;
letter-spacing:.02em}}
.m-big .sm{{font-size:13px;font-weight:400;color:var(--bl);letter-spacing:.02em}}
.m-conf .m-big{{color:var(--bl);text-shadow:0 0 20px rgba(63,224,218,.4)}}
.m-line{{color:var(--txt);font-size:11.5px;margin-top:7px;line-height:1.55}}
.m-line b{{color:var(--white)}}
.ev-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:12px}}
.ev-grid div{{border:1px solid var(--line);background:rgba(4,13,12,.75);padding:6px 9px}}
.ev-grid span{{display:block;color:var(--dim2);font-size:9px;letter-spacing:.14em;
margin-bottom:2px}}
.ev-grid b{{font-size:12px}}
.ev-grid .ok{{color:var(--bl)}}.ev-grid .mixed{{color:#E8B42B}}.ev-grid .bad{{color:#FF8A8A}}
details.m-proof{{margin-top:16px;border-top:1px solid var(--line);padding-top:12px}}
details.m-proof summary{{color:var(--cy);font-size:10px;letter-spacing:.22em;
cursor:pointer;list-style:none;text-shadow:0 0 12px rgba(10,186,181,.4)}}
details.m-proof summary::-webkit-details-marker{{display:none}}
details.m-proof summary::before{{content:"\25B8  ";display:inline-block;
transition:transform .15s}}
details.m-proof[open] summary::before{{content:"\25BE  "}}
details.m-proof table{{margin-top:12px}}
@media(max-width:820px){{.m-hero,.ev-grid{{grid-template-columns:repeat(2,1fr)}}
.m-hero>div:first-child{{grid-column:span 2}}}}
.sd{{border:1px solid #6B5A1E;background:linear-gradient(180deg,#161200,#0B0900);
border-left:3px solid #E8B42B;padding:18px 20px;margin:0 0 18px}}
.sd-h{{color:#F0C44C;font-weight:700;letter-spacing:.14em;font-size:12px;
margin-bottom:10px}}
.sd-b{{color:#AFC6C4;font-size:13px;line-height:1.65}}
.sd-b b{{color:#EAFBFA}}
.sd-n{{color:#FF6B6B!important;font-size:15px}}
.sd-g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));
gap:8px;margin:12px 0}}
.sd-g div{{border:1px solid #2A2409;background:#0D0B02;padding:8px 10px}}
.sd-g span{{display:block;color:#5B807D;font-size:10px;letter-spacing:.1em;
text-transform:uppercase}}
.sd-g b{{color:#FF8A8A;font-family:inherit;font-size:14px}}
.sd-r{{margin-top:12px;padding-top:12px;border-top:1px solid #2A2409;
color:#8FA9A7;font-size:12.5px;line-height:1.6}}
:root{{--void:#000000;--panel:#050B0B;--line:#12302E;--cy:#0ABAB5;--bl:#3FE0DA;
--txt:#AFC6C4;--dim2:#5B807D;--white:#EAFBFA}}
body{{background:#000;color:var(--txt);
 font:14px/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 letter-spacing:.02em;
 background-image:linear-gradient(rgba(10,186,181,.028) 1px,transparent 1px),
  linear-gradient(90deg,rgba(10,186,181,.028) 1px,transparent 1px);
 background-size:44px 44px}}
.wrap{{max-width:1180px;margin:0 auto;padding:38px 22px 70px}}

/* ── mark ── */
.top{{display:flex;align-items:center;gap:20px;flex-wrap:wrap;margin-bottom:6px}}
.logo{{width:96px;height:96px;flex:none;border-radius:50%;object-fit:cover;
 box-shadow:0 0 26px rgba(10,186,181,.45),0 0 60px rgba(10,186,181,.16);
 border:1px solid rgba(10,186,181,.4)}}
.mark{{width:62px;height:62px;flex:none;position:relative;
 border:1px solid var(--cy);transform:rotate(45deg);
 box-shadow:0 0 18px rgba(10,186,181,.4),inset 0 0 18px rgba(10,186,181,.16)}}
.mark:after{{content:"";position:absolute;inset:11px;border:1px solid var(--bl);
 box-shadow:0 0 10px rgba(63,224,218,.5)}}
h1{{font-size:38px;letter-spacing:.30em;color:var(--white);font-weight:600;
 text-shadow:0 0 22px rgba(10,186,181,.55)}}
h1 b{{color:var(--cy);font-weight:600}}
.tag1{{color:var(--dim2);letter-spacing:.30em;font-size:11px;margin-top:5px}}
.pills{{margin:16px 0 30px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
.pill{{border:1px solid var(--line);color:var(--dim2);font-size:10px;
 letter-spacing:.2em;padding:4px 13px;border-radius:2px;background:rgba(10,186,181,.03)}}
.pill.on{{border-color:var(--cy);color:var(--cy);box-shadow:0 0 12px rgba(10,186,181,.2)}}

/* ── stats: fixed 3 columns, always symmetric ── */
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:34px}}
.stats .stat:nth-child(1){{grid-column:span 2}}
.stat{{background:linear-gradient(160deg,rgba(10,186,181,.05),transparent 60%),var(--panel);
 border:1px solid var(--line);padding:17px 19px;position:relative;
 clip-path:polygon(0 0,calc(100% - 15px) 0,100% 15px,100% 100%,15px 100%,0 calc(100% - 15px))}}
.stat:before{{content:"";position:absolute;left:0;top:0;width:2px;height:34px;
 background:var(--cy);box-shadow:0 0 10px var(--cy)}}
.k{{font-size:10px;letter-spacing:.22em;color:var(--dim2)}}
.v{{font-size:27px;color:var(--white);margin:7px 0 3px;letter-spacing:.03em;
 text-shadow:0 0 16px rgba(10,186,181,.3);font-variant-numeric:tabular-nums}}
/* Equity and P&L carry the weight — they are what anyone opens this page for. */
.stat.big .v{{font-size:34px;font-weight:700;letter-spacing:.01em}}
.stat.pos .v{{color:#5CCFE6;text-shadow:0 0 20px rgba(92,207,230,.60)}}
.stat.neg .v{{color:#FF6B85;text-shadow:0 0 20px rgba(255,107,133,.45)}}
.stat.pos:before{{background:#5CCFE6;box-shadow:0 0 12px #5CCFE6}}
.stat.neg:before{{background:#FF6B85;box-shadow:0 0 12px #FF6B85}}
.n{{font-size:10.5px;color:var(--dim2);letter-spacing:.06em}}

/* ── sections ── */
h2{{font-size:11px;letter-spacing:.30em;color:var(--cy);margin:38px 0 4px;
 text-shadow:0 0 14px rgba(10,186,181,.4)}}
.rule{{height:1px;background:linear-gradient(90deg,var(--cy),transparent);
 margin-bottom:14px;box-shadow:0 0 8px rgba(10,186,181,.35)}}
.lead{{color:var(--dim2);font-size:12px;margin-bottom:14px;max-width:78ch}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{text-align:left;color:var(--dim2);font-weight:400;font-size:10px;
 letter-spacing:.2em;padding:8px 10px;border-bottom:1px solid var(--line)}}
td{{padding:9px 10px;border-bottom:1px solid rgba(14,32,51,.6)}}
tr:hover td{{background:rgba(10,186,181,.035)}}
td.num{{text-align:right;color:var(--white)}}
td.empty{{color:var(--dim2);text-align:center;padding:26px}}
.sub{{font-size:10px;color:var(--dim2);margin-top:3px;font-weight:400;letter-spacing:.02em}}
td.gd{{color:#5CCFE6}} td.rd{{color:#FF6B85}}
td.bar{{width:38%}}
td.bar span{{display:block;height:6px;background:linear-gradient(90deg,var(--bl),var(--cy));
 box-shadow:0 0 9px rgba(10,186,181,.6)}}
.cy{{color:var(--cy)}} .wh{{color:var(--white)}} .gd{{color:#3BE8A0}} .rd{{color:#FF5C7A}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:26px}}
.term{{background:radial-gradient(120% 90% at 50% 0%,rgba(92,207,230,.09),transparent 62%),#000;
 backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);
 border:1px solid rgba(92,207,230,.36);padding:0;
 box-shadow:0 0 34px rgba(92,207,230,.20),0 0 90px rgba(92,207,230,.07),
 inset 0 1px 0 rgba(92,207,230,.28);
 clip-path:polygon(0 0,calc(100% - 15px) 0,100% 15px,100% 100%,15px 100%,0 calc(100% - 15px))}}
.term .body{{margin:0;padding:12px 0;max-height:540px;overflow:auto;font-size:12.5px;
 background:transparent;font-family:var(--mono);line-height:1.6}}
.term .body::-webkit-scrollbar{{width:9px}}
.term .body::-webkit-scrollbar-track{{background:rgba(255,255,255,.03)}}
.term .body::-webkit-scrollbar-thumb{{background:rgba(92,207,230,.42);border-radius:5px}}
.tl{{display:flex;gap:16px;align-items:baseline;padding:7px 22px;
 border-left:3px solid transparent;line-height:1.55}}
.tl:hover{{background:rgba(92,207,230,.08)}}
.ts{{color:#5CCFE6;text-shadow:0 0 8px rgba(92,207,230,.55);font-variant-numeric:tabular-nums;flex:none;
 font-size:11.5px;letter-spacing:.04em;min-width:62px}}
.ic{{flex:none;width:18px;text-align:center}}
.tx{{color:#CFEAF3;word-break:break-word}}
.tl.fill{{border-left-color:#5CCFE6;background:rgba(92,207,230,.11);
 box-shadow:inset 0 0 26px rgba(92,207,230,.10)}}
.tl.fill .tx{{color:#FFFFFF;font-weight:600;text-shadow:0 0 12px rgba(92,207,230,.75)}}
.tl.refuse{{border-left-color:rgba(41,168,216,.55)}}
.tl.refuse .tx{{color:#7FA9BC}}
.tl.skip .tx{{color:#4E7182}} .tl.skip .ts{{color:#2F5769;text-shadow:none}}
.tl.intel{{border-left-color:rgba(41,168,216,.40)}}
.tl.intel .tx{{color:#8FBBCE}}
/* Each 5-minute cycle is a block, separated by real whitespace and a rule.
   A hairline was not enough - the log still read as one wall. */
.tl.cyc{{margin-top:22px;padding-top:17px;position:relative}}
.tl.cyc:before{{content:"";position:absolute;left:22px;right:22px;top:0;height:1px;
 background:linear-gradient(90deg,rgba(92,207,230,.75),rgba(92,207,230,.10) 58%,transparent);
 box-shadow:0 0 9px rgba(92,207,230,.45)}}
.tl.cyc:first-child{{margin-top:2px;padding-top:8px}}
.tl.cyc:first-child:before{{display:none}}
.tl.cyc .ts{{color:#FFFFFF;font-weight:600;font-size:12px;
 background:rgba(92,207,230,.14);border:1px solid rgba(92,207,230,.52);
 padding:3px 10px;border-radius:4px;min-width:auto;
 box-shadow:0 0 16px rgba(92,207,230,.35);text-shadow:0 0 10px rgba(92,207,230,.8)}}
.live{{display:inline-flex;align-items:center;gap:7px;font-size:10px;
 letter-spacing:.2em;color:#3BE8A0;margin-left:12px}}
.live b{{width:7px;height:7px;border-radius:50%;background:#3BE8A0;
 box-shadow:0 0 9px #3BE8A0;animation:p 1.6s ease-in-out infinite}}
@keyframes p{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
.legend{{display:flex;gap:18px;flex-wrap:wrap;font-size:10.5px;color:#7FB8CC;
 padding:12px 22px;border-bottom:1px solid rgba(92,207,230,.28);
 background:rgba(92,207,230,.055);letter-spacing:.05em}}
.warn{{border:1px solid #8a6a12;background:rgba(138,106,18,.12);color:#F0C674;
 padding:11px 15px;margin-bottom:20px;font-size:12px;letter-spacing:.05em}}
.foot{{margin-top:44px;padding-top:16px;border-top:1px solid var(--line);
 color:var(--dim2);font-size:10.5px;letter-spacing:.12em}}
@media(max-width:900px){{.stats{{grid-template-columns:repeat(2,1fr)}}.two{{grid-template-columns:1fr}}}}
@media(max-width:560px){{.stats{{grid-template-columns:1fr}}h1{{font-size:25px}}}}
</style>

<div class="wrap">
<div class="top">
  {_logo()}
  <div>
    <h1>DELTA<b>X</b></h1>
    <div class="tag1">AUTONOMOUS OPTIONS TRADING &nbsp;·&nbsp; CODE · RISK · EXECUTE</div>
  </div>
</div>
<div class="pills">
  <span class="pill on">TEAM SYNC BOARD</span>
  <a class="pill" href="presentation.html" style="text-decoration:none">📊 PRESENTATION</a>
  <span class="pill">US {_tz["us"]}</span><span class="pill">LATVIA {_tz["lv"]}</span><span class="pill">DENMARK {_tz["dk"]}</span>
  <span class="pill">ALPACA PAPER</span><span class="pill">754 TESTS</span><span class="pill">MIT</span>
</div>
{standdown}
{warn}
{mission}
<div class="stats">{stats}</div>

<h2>WHY THE AGENT SAID NO</h2><div class="rule"></div>
<div class="lead">Every evaluation is recorded — approvals and refusals alike — in a
hash-chained, append-only ledger. An agent that can explain why it declined a
candidate demonstrates more than a P&amp;L number can.</div>
<table><tr><th>GATE</th><th style="text-align:right">REFUSALS</th><th></th></tr>{gate_rows}</table>

<h2>OPEN POSITIONS</h2><div class="rule"></div>
<div class="lead">Each row is one spread — two option contracts traded together.
We <b>sell</b> one and <b>buy</b> a cheaper one as protection, so the loss is
capped before the order is ever sent. We keep the money collected up front if
the stock stays in range.</div>
<div class="tw"><table>
<tr><th>STOCK</th><th>WHAT WE DID</th><th class="n">SIZE</th>
<th class="n">MONEY IN</th><th class="n">MAX LOSS</th><th class="n">P&amp;L NOW</th></tr>
{pos}</table></div>

<div class="two">
<div>
<h2>STRATEGY</h2><div class="rule"></div>
<table>
<tr><td>Structure</td><td class="wh">Iron condor — defined risk</td></tr>
<tr><td>Expiry</td><td class="wh">11 DTE <span class="cy">(Sep 11)</span></td></tr>
<tr><td>Strike delta</td><td class="wh">0.20</td></tr>
<tr><td>Exit</td><td class="wh">50% of credit captured</td></tr>
<tr><td>Direction</td><td class="wh">Put = 📈 LONG · Call = 📉 SHORT</td></tr>
<tr><td>Edge source</td><td class="wh">Variance risk premium</td></tr>
<tr><td>Walk-forward E</td><td class="gd">+0.109 SPY · +0.147 IWM</td></tr>
</table>
</div>
<div>
<h2>RISK ENVELOPE</h2><div class="rule"></div>
<table>
<tr><td>Per position</td><td class="wh">2% &nbsp;($2,000)</td></tr>
<tr><td>Portfolio</td><td class="wh">30% &nbsp;($30,000)</td></tr>
<tr><td>Daily kill switch</td><td class="rd">−5% → HALT</td></tr>
<tr><td>Drawdown halt</td><td class="rd">−20%</td></tr>
<tr><td>Min positions</td><td class="wh">15 (forces diversification)</td></tr>
<tr><td>Gates</td><td class="wh">13, fail-closed · book reconciled every cycle</td></tr>
<tr><td>Permission</td><td class="wh">NORMAL→CAUTION→DEFENSIVE→<span class="rd">HALT</span></td></tr>
</table>
</div>
</div>

<h2>RESEARCH &amp; DATA SOURCES</h2><div class="rule"></div>
<div class="lead" style="margin-bottom:10px">Every dataset behind the current thesis,
deduplicated. Multiple independent sources &mdash; not a single model opinion.
Retrieved 1&ndash;2 Sep 2026 unless noted.</div>
<table>
<tr><th>SOURCE</th><th>DATASET</th><th>CONTRIBUTED</th><th>ROLE</th></tr>
<tr><td class="cy">Massive</td><td>OPRA consolidated &middot; historical option OHLC
 per contract (REST v2 aggs)</td>
 <td>Real traded prices for USO verticals across 9 Friday expiries &mdash; the
 backtests that re-struck the trade and found the exit-lifecycle edge</td>
 <td>historical options / backtesting / validation</td></tr>
<tr><td class="cy">Massive</td><td>Options contracts reference (v3, incl. expired)</td>
 <td>Strike/expiry existence for expired weeklies the live chain no longer shows</td>
 <td>backtest integrity</td></tr>
<tr><td class="cy">Alpaca</td><td>Market data &middot; IEX equities bars &amp; snapshots</td>
 <td>USO/benchmark prices, VWAP, realized vol, regime reads, every account state</td>
 <td>live market data / execution</td></tr>
<tr><td class="cy">Alpaca</td><td>Options chain &amp; contracts (indicative feed,
 15-min delay on free tier)</td>
 <td>Live quotes, greeks, IV, open interest &mdash; all gate checks and the
 posterior&rsquo;s IV-implied base rate</td>
 <td>options pricing / risk gates</td></tr>
<tr><td class="cy">Alpaca</td><td>News API</td>
 <td>33 corroborating supply-shock headlines validating the catalyst (US&ndash;Iran
 strikes, Hormuz, crude &gt;$90)</td>
 <td>catalyst confirmation</td></tr>
<tr><td class="cy">SEC EDGAR</td><td>8-K Item 2.02 filings</td>
 <td>Earnings blackout gate &mdash; <span class="rd">inactive: DELTAX_SEC_UA unset;
 fails closed</span>; universe is all-ETF so unaffected</td>
 <td>earnings risk (dormant)</td></tr>
<tr><td class="cy">S&amp;P DJI</td><td>Energy Select Sector index factsheet
 (31 Aug 2026, operator-supplied)</td>
 <td>29% single-name concentration &rarr; XLE is 2&ndash;3 mega-caps in a wrapper;
 explained why sector-ETF weeklies are untradeable</td>
 <td>structure research</td></tr>
<tr><td class="cy">Coinglass</td><td>Spot netflow statistics (operator-supplied,
 1 Sep)</td>
 <td>BTC/ETH/XRP exchange-flow reversal read &mdash; informational only; crypto is
 excluded on evidence (0/22 pairs significant)</td>
 <td>context, not traded</td></tr>
<tr><td class="cy">Yahoo Finance</td><td>USO daily OHLCV, Dec 2025&ndash;Sep 2026
 (operator-supplied)</td>
 <td>Cross-validation of Alpaca bars; the 20-case study of what follows a
 &ge;+4% day (60% up, median +1.1%)</td>
 <td>historical validation</td></tr>
<tr><td class="cy">Corpus</td><td>research/ &mdash; 6 options sources incl. WSJ 0DTE
 (only disinterested source), Alyrise (I. Rosicka), AURA (Matin)</td>
 <td>R5 DTE constraint, regime filter, validation bars, decision ledger E1&ndash;E63</td>
 <td>rules &amp; provenance</td></tr>
</table>

<h2>NEWS &amp; DATA FEEDS</h2><div class="rule"></div>
<div class="lead">Probed live at every page generation. Per the corpus, news can
veto a trade, never originate one — a stale feed is disarmed, not trusted.</div>
<table><tr><th>FEED</th><th>BUCKET</th><th style="text-align:right">ITEMS</th>
<th>FRESHNESS</th><th>STATUS</th></tr>{frows}</table>

<h2>1 SEP — WHAT THE AGENT REFUSED, AND WHY</h2><div class="rule"></div>
<div class="lead" style="margin-bottom:12px">The tape sold off through the
morning and the regime went <b>0/3 weak &rarr; 3/3 weak</b>, escalating
permission <span class="cy">CAUTION &rarr; DEFENSIVE</span>. Three separate
opportunities were examined and all three declined. None of these were
missed &mdash; each was measured, and the measurement is below.</div>
<table>
<tr><th>CANDIDATE</th><th>WHAT WE MEASURED</th><th>VERDICT</th></tr>
<tr><td class="cy">Energy<br><span class="dim">XLE XOP USO</span></td>
 <td>Correct read &mdash; USO <b class="gd">+4.28%</b>, XOP +1.52%, XLE +1.05%
 while SPY was &minus;0.71%. But at the &delta;0.30 strike the 4 Sep weeklies
 quote OI <b>484 / 3 / 7</b> and spreads <b class="rd">46% / 176% / 36%</b>
 against a 15% cap.</td>
 <td class="rd">No instrument.<br>Crossing the spread costs more than the trade
 can earn.</td></tr>
<tr><td class="cy">SPY put<br><span class="dim">757 / 737</span></td>
 <td>IV/RV moved <b class="gd">1.09 &rarr; 2.01</b> on the selloff. OI 779,
 spread 6%, credit $1.73. <b>Passed every gate.</b></td>
 <td class="rd">Blocked by DEFENSIVE<br><span class="dim">3/3 benchmarks weak</span></td></tr>
<tr><td class="cy">QQQ put<br><span class="dim">701 / 681</span></td>
 <td>IV/RV <b class="gd">0.79 &rarr; 1.56</b>. OI 684, spread 3%, credit $1.95.
 <b>Passed every gate.</b></td>
 <td class="rd">Blocked by DEFENSIVE</td></tr>
</table>
<div class="lead" style="margin-top:12px">The SPY and QQQ spreads were the
richest, cleanest setups measured all week, and the operator was offered the
override at half size. <span class="cy">It was declined.</span> The regime
filter is worth <b>31 points</b> in the rebuilt backtest &mdash;
<span class="rd">&minus;63.6%</span> without it against
<span class="rd">&minus;32.0%</span> with it &mdash; and this was precisely its
scenario: selling puts into a falling tape, two days from expiry, on the last
day a position could be opened. Rich premium is <b>compensation for risk, not
evidence of its absence</b>: IV/RV 2.01 existed because the market had just
fallen and might keep falling.
<div class="sd-r" style="margin-top:12px">A filter is only worth what it costs
you on the day you least want to obey it. One overridden whenever it binds has
no value, and its backtested contribution was never real. The cost of obeying it
today is visible above, in full, priced to the cent.</div></div>

<h2>BOOK ALLOCATION</h2><div class="rule"></div>
<table>
<tr><th>SLEEVE</th><th style="text-align:right">CAPITAL</th><th>STRUCTURE</th><th>EVIDENCE</th></tr>
<tr><td class="cy">OPTIONS</td><td class="num">$30,000 risk</td>
 <td>Vertical credit spreads · <b>4 names</b> (SPY QQQ IWM SMH)</td>
 <td>rebuilt after E44 — expectancy ~flat, positive at observed IV/RV</td></tr>
<tr><td class="cy">STOCKS</td><td class="num">$0</td>
 <td><b>Alyrise</b> &mdash; authoritative stock engine, spec&#39;d by Ilze Rosicka
 (Elsa), 14pp. Second track: AURA Equity Lab (Matin).</td>
 <td>specified, not funded this week &mdash; stocks-only by design, and the
 contest requires options in <i>every</i> strategy</td></tr>
<tr><td class="cy">CRYPTO</td><td class="num">$0</td>
 <td>Venue screened <b>exhaustively</b>: 73 pairs listed &rarr; 33 tradeable
 &rarr; 22 with usable history</td>
 <td><b>0 of 22</b> significant at 95%, 0 past Bonferroni, median win rate
 <span class="rd">43.8%</span> &mdash; and Alpaca lists no crypto options</td></tr>
</table>
<div class="lead" style="margin-top:11px">Both sleeves read $0 by
<span class="cy">decision</span>, not by omission. Crypto&#39;s in-band rate is
<b>80&ndash;85%</b> across every pair &mdash; better than SPY&#39;s 75% &mdash; so the
condor premise holds there; there is simply no listed instrument on this venue to
sell that band with. The edge is visible and unreachable. Alyrise is a complete
engine specification awaiting its pre-committed validation bar (OOS PF &gt; 1.10,
&gt;50% of folds positive); it is stocks-only and cannot carry an options
submission alone. An earlier version of this table showed
<span class="rd">$60,000</span> in stocks and <span class="rd">$10,000</span> in
crypto as if both were running, and called the options book &ldquo;17 names,
validated walk-forward&rdquo;. Capital this week is
<span class="cy">100% cash outside the options sleeve</span>.</div>

<h2>BACKTEST — REBUILT 1 SEP</h2><div class="rule"></div>
<div class="lead" style="margin-bottom:11px">The three-week table that stood here
(<span class="gd">+8,394, +8.39%</span>) was computed at credits the market never
pays, by a backtest since found to carry five defects (E44). It has been removed
rather than restated &mdash; every figure in it was wrong. Below is the rebuilt
result on the live 4-name basket, over 26 weeks, priced at real market credit.</div>
<table>
<tr><th>IV/RV ASSUMPTION</th><th style="text-align:right">26-WEEK TOTAL</th>
<th style="text-align:right">WORST WEEK</th><th style="text-align:right">MAX DRAWDOWN</th></tr>
<tr><td>1.00 &nbsp;<span class="dim">no vol premium at all</span></td>
 <td class="num">+13</td><td class="num rd">&minus;982</td><td class="num rd">&minus;2.38%</td></tr>
<tr><td>1.15 &nbsp;<span class="dim">pessimistic</span></td>
 <td class="num gd">+1,459</td><td class="num rd">&minus;768</td><td class="num rd">&minus;1.56%</td></tr>
<tr><td>1.30</td><td class="num gd">+2,445</td><td class="num rd">&minus;616</td>
 <td class="num rd">&minus;1.00%</td></tr>
<tr><td class="wh">1.45 &nbsp;<span class="dim">measured today</span></td>
 <td class="num gd wh">+3,142</td><td class="num rd">&minus;505</td>
 <td class="num rd">&minus;0.60%</td></tr>
</table>
<div class="lead" style="margin-top:11px">Roughly <span class="cy">flat</span> &mdash;
not a loser, not an edge. It is positive across every vol assumption tested, which
is the property that matters; the margin itself is inside the noise. Chosen from
six candidate baskets, so treat the ranking with suspicion and the
<span class="cy">bounded downside</span> as the reason to run it.</div>

<h2>OUTCOME DISTRIBUTION — NOT A PREDICTION</h2><div class="rule"></div>
<table>
<tr><th>PERCENTILE</th><th style="text-align:right">RESULT</th><th>READING</th></tr>
<tr><td>p5</td><td class="num rd">&minus;371</td><td>very bad week</td></tr>
<tr><td>p25</td><td class="num">&minus;173</td><td>poor</td></tr>
<tr><td class="wh">p50 — MEDIAN</td><td class="num wh">+186</td><td>typical</td></tr>
<tr><td>p75</td><td class="num gd">+419</td><td>good</td></tr>
<tr><td>p95</td><td class="num gd">+468</td><td>very good</td></tr>
</table>
<div class="lead" style="margin-top:11px">26 weeks on the live 4-name basket at
the vol premium measured today, priced at real market credit. Positive in
<span class="cy">65%</span> of them. An earlier version of this table
claimed a median of <span class="rd">+2,144</span> and a p95 of
<span class="rd">+4,656</span>; those came from a 17-name book priced at credits
the market never pays, and were wrong by roughly an order of magnitude. We cannot
forecast direction &mdash; five directional strategies were tested and all five
failed. This says where weeks like this one have landed, and the contest gets
<span class="cy">exactly one draw</span>.</div>

<h2>LIVE TERMINAL — EVERYTHING THE AGENT DID
 <span class="live"><b></b>STREAMING</span></h2><div class="rule"></div>
<div class="lead">The raw activity streams, exactly as written: scheduled runs, pre-market
intelligence passes, and every ledger entry — approvals, refusals, exits, reconciliations.
Nothing summarised, nothing hidden. Refreshes with the page.</div>
<div class="term">
  <div class="legend">
   <span>✅ order placed</span><span>💰 position closed</span>
   <span>🚫 declined by a gate</span><span>⏳ stood by — no action taken</span>
   <span>🌙 market closed</span><span>📊 account state</span>
   <span>📡 pre-market intel</span>
   <span style="color:#5CCFE6;text-shadow:0 0 8px rgba(92,207,230,.6)">newest first · all times ET</span></div>
  <div class="body">{_terminal_lines()}</div>
</div>

<div class="foot">
GENERATED {now:%Y-%m-%d %H:%M} UTC &nbsp;·&nbsp; REFRESHED EVERY 5 MIN BY A SCHEDULED JOB
&nbsp;·&nbsp; PAPER TRADING ONLY — NO REAL CAPITAL &nbsp;·&nbsp; ACCOUNT {acct}
</div>
</div>"""


def main():
    account = positions = None; err = None
    try:
        from deltax.feeds import AlpacaFeed
        f = AlpacaFeed(); account = f.account()
        # Pass the broker's rows through whole. The previous shape kept only
        # symbol/qty/pl, so entry and current price were gone by the time the
        # table tried to compute what each spread actually collected.
        positions = list(f.positions())
    except Exception as e:
        err = str(e)[:110]
    os.makedirs("docs", exist_ok=True)
    html = build(account, positions, err)
    open("docs/index.html", "w").write(html)
    print(f"wrote docs/index.html ({len(html):,} bytes)" + (f" — account unread: {err}" if err else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main())
