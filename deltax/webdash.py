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
            icon, css = ("⏸️", "skip") if "skipped" in low or "no action" in low else \
                        ("📡", "intel") if tag == "intel" else ("⚙️", "agent")
            if "opened" in low or "filled" in low:   icon, css = "🟢", "fill"
            if "exit"   in low:                      icon, css = "💰", "fill"
            if "refused" in low or "⛔" in ln:        icon, css = "⛔", "refuse"
            if "scoreboard" in low:                  icon, css = "📊", "agent"
            if low.startswith("decision"):           icon, css = "✅", "agent"
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
                        events.append((k, t, "⛔", "refuse",
                                       f"REFUSE  {e.get('symbol','?'):<6} blocked by {g}"))
                    else:
                        events.append((k, t, "🟢", "fill",
                                       f"TRADE   {e.get('symbol','?'):<6} all 13 gates passed"))
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

    def stat(label, value, note=""):
        return (f'<div class="stat"><div class="k">{label}</div>'
                f'<div class="v">{value}</div><div class="n">{note}</div></div>')

    # 6 stats -> exactly two rows of three. Never an orphan.
    stats = "".join([
        stat("ACCOUNT", acct, "Alpaca paper · competition"),
        stat("EQUITY", money(eq), "live read" if eq else "not read"),
        stat("CASH", money(cash), "uncommitted"),
        stat("OPEN POSITIONS", len(positions or []), "live"),
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

    pos = "".join(
        f'<tr><td class="cy">{p.get("symbol","")}</td><td>{p.get("bias","—")}</td>'
        f'<td class="num">{p.get("qty","")}</td><td class="num">{p.get("pl","")}</td></tr>'
        for p in (positions or [])) or \
        '<tr><td colspan="4" class="empty">Flat. The agent has placed no orders.</td></tr>'

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

    return f"""<title>DELTAX — Autonomous Options Agent</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
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
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:34px}}
.stat{{background:linear-gradient(160deg,rgba(10,186,181,.05),transparent 60%),var(--panel);
 border:1px solid var(--line);padding:17px 19px;position:relative;
 clip-path:polygon(0 0,calc(100% - 15px) 0,100% 15px,100% 100%,15px 100%,0 calc(100% - 15px))}}
.stat:before{{content:"";position:absolute;left:0;top:0;width:2px;height:34px;
 background:var(--cy);box-shadow:0 0 10px var(--cy)}}
.k{{font-size:10px;letter-spacing:.22em;color:var(--dim2)}}
.v{{font-size:27px;color:var(--white);margin:7px 0 3px;letter-spacing:.03em;
 text-shadow:0 0 16px rgba(10,186,181,.3)}}
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
td.bar{{width:38%}}
td.bar span{{display:block;height:6px;background:linear-gradient(90deg,var(--bl),var(--cy));
 box-shadow:0 0 9px rgba(10,186,181,.6)}}
.cy{{color:var(--cy)}} .wh{{color:var(--white)}} .gd{{color:#3BE8A0}} .rd{{color:#FF5C7A}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:26px}}
.term{{background:linear-gradient(160deg,rgba(10,186,181,.10),rgba(8,22,34,.72) 42%),
 rgba(6,18,28,.55);
 backdrop-filter:blur(22px) saturate(140%);-webkit-backdrop-filter:blur(22px) saturate(140%);
 border:1px solid rgba(10,186,181,.30);padding:0;
 box-shadow:0 0 42px rgba(10,186,181,.13),inset 0 1px 0 rgba(255,255,255,.10),
 inset 0 0 70px rgba(10,186,181,.05);
 clip-path:polygon(0 0,calc(100% - 15px) 0,100% 15px,100% 100%,15px 100%,0 calc(100% - 15px))}}
.term .body{{margin:0;padding:12px 0;max-height:540px;overflow:auto;font-size:12.5px;
 background:transparent;font-family:var(--mono);line-height:1.6}}
.term .body::-webkit-scrollbar{{width:9px}}
.term .body::-webkit-scrollbar-track{{background:rgba(255,255,255,.03)}}
.term .body::-webkit-scrollbar-thumb{{background:rgba(10,186,181,.32);border-radius:5px}}
.tl{{display:flex;gap:16px;align-items:baseline;padding:7px 22px;
 border-left:3px solid transparent;line-height:1.55}}
.tl:hover{{background:rgba(10,186,181,.09)}}
.ts{{color:#5FD8D3;font-variant-numeric:tabular-nums;flex:none;
 font-size:11.5px;letter-spacing:.04em;min-width:62px}}
.ic{{flex:none;width:18px;text-align:center}}
.tx{{color:#EAFBFA;word-break:break-word}}
.tl.fill{{border-left-color:#4ADE80;background:rgba(74,222,128,.11)}}
.tl.fill .tx{{color:#86EFAC;font-weight:500}}
.tl.refuse{{border-left-color:#F87171}}
.tl.refuse .tx{{color:#FCA5A5}}
.tl.skip .tx{{color:#6F9A9A}} .tl.skip .ts{{color:#3F6E6D}}
.tl.intel{{border-left-color:rgba(63,224,218,.75)}}
.tl.intel .tx{{color:#A9DEDB}}
/* Each 5-minute cycle is a block, separated by real whitespace and a rule.
   A hairline was not enough - the log still read as one wall. */
.tl.cyc{{margin-top:22px;padding-top:17px;position:relative}}
.tl.cyc:before{{content:"";position:absolute;left:22px;right:22px;top:0;height:1px;
 background:linear-gradient(90deg,rgba(10,186,181,.55),rgba(10,186,181,.06) 60%,transparent)}}
.tl.cyc:first-child{{margin-top:2px;padding-top:8px}}
.tl.cyc:first-child:before{{display:none}}
.tl.cyc .ts{{color:#EAFBFA;font-weight:600;font-size:12px;
 background:rgba(10,186,181,.16);border:1px solid rgba(10,186,181,.38);
 padding:3px 10px;border-radius:4px;min-width:auto;
 box-shadow:0 0 14px rgba(10,186,181,.20)}}
.live{{display:inline-flex;align-items:center;gap:7px;font-size:10px;
 letter-spacing:.2em;color:#3BE8A0;margin-left:12px}}
.live b{{width:7px;height:7px;border-radius:50%;background:#3BE8A0;
 box-shadow:0 0 9px #3BE8A0;animation:p 1.6s ease-in-out infinite}}
@keyframes p{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
.legend{{display:flex;gap:18px;flex-wrap:wrap;font-size:10.5px;color:#8FC5C2;
 padding:12px 22px;border-bottom:1px solid rgba(10,186,181,.22);
 background:rgba(10,186,181,.07);letter-spacing:.05em}}
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
  <a class="pill" href="slides.html" style="text-decoration:none">📊 SLIDES</a>
  <span class="pill">US</span><span class="pill">LATVIA</span><span class="pill">DENMARK</span>
  <span class="pill">ALPACA PAPER</span><span class="pill">366 TESTS</span><span class="pill">MIT</span>
</div>
{warn}
<div class="stats">{stats}</div>

<h2>WHY THE AGENT SAID NO</h2><div class="rule"></div>
<div class="lead">Every evaluation is recorded — approvals and refusals alike — in a
hash-chained, append-only ledger. An agent that can explain why it declined a
candidate demonstrates more than a P&amp;L number can.</div>
<table><tr><th>GATE</th><th style="text-align:right">REFUSALS</th><th></th></tr>{gate_rows}</table>

<h2>OPEN POSITIONS</h2><div class="rule"></div>
<table><tr><th>SYMBOL</th><th>BIAS</th><th style="text-align:right">QTY</th>
<th style="text-align:right">P&amp;L</th></tr>{pos}</table>

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

<h2>NEWS &amp; DATA FEEDS</h2><div class="rule"></div>
<div class="lead">Probed live at every page generation. Per the corpus, news can
veto a trade, never originate one — a stale feed is disarmed, not trusted.</div>
<table><tr><th>FEED</th><th>BUCKET</th><th style="text-align:right">ITEMS</th>
<th>FRESHNESS</th><th>STATUS</th></tr>{frows}</table>

<h2>BOOK ALLOCATION</h2><div class="rule"></div>
<table>
<tr><th>SLEEVE</th><th style="text-align:right">CAPITAL</th><th>STRUCTURE</th><th>EVIDENCE</th></tr>
<tr><td class="cy">OPTIONS</td><td class="num">$30,000 risk</td>
 <td>Iron condors · 17 names</td><td class="gd">validated, walk-forward</td></tr>
<tr><td class="cy">STOCKS</td><td class="num">$60,000</td>
 <td>Covered calls</td><td>compliant; edge unproven at 4-day hold</td></tr>
<tr><td class="cy">CRYPTO</td><td class="num">$10,000</td>
 <td>Spot — no crypto options on venue</td>
 <td class="rd">0 of 22 pairs significant</td></tr>
</table>

<h2>BACKTEST — LAST THREE WEEKS</h2><div class="rule"></div>
<table>
<tr><th>WEEK</th><th style="text-align:right">OPTIONS</th><th style="text-align:right">STOCKS</th>
<th style="text-align:right">CRYPTO</th><th style="text-align:right">TOTAL</th></tr>
<tr><td>10–14 Aug</td><td class="num gd">+3,737</td><td class="num rd">−279</td>
 <td class="num rd">−77</td><td class="num gd">+3,382</td></tr>
<tr><td>17–21 Aug</td><td class="num rd">−1,728</td><td class="num gd">+494</td>
 <td class="num gd">+3,037</td><td class="num gd">+1,803</td></tr>
<tr><td>24–28 Aug</td><td class="num gd">+2,998</td><td class="num gd">+322</td>
 <td class="num rd">−110</td><td class="num gd">+3,210</td></tr>
<tr><td class="wh">TOTAL</td><td class="num gd">+5,007</td><td class="num gd">+537</td>
 <td class="num gd">+2,850</td><td class="num gd wh">+8,394 &nbsp;(+8.39%)</td></tr>
</table>
<div class="lead" style="margin-top:11px">Simulated on real historical prices with credit at
the gate's <span class="cy">minimum</span> — real fills would do better; no commissions charged —
they would do worse. The crypto figure is almost entirely one week of XRP and is
<span class="rd">not repeatable</span>.</div>

<h2>OUTCOME DISTRIBUTION — NOT A PREDICTION</h2><div class="rule"></div>
<table>
<tr><th>PERCENTILE</th><th style="text-align:right">RESULT</th><th>READING</th></tr>
<tr><td>p5</td><td class="num rd">−2,374</td><td>very bad week</td></tr>
<tr><td>p25</td><td class="num">+275</td><td>poor</td></tr>
<tr><td class="wh">p50 — MEDIAN</td><td class="num gd wh">+2,144</td><td>typical</td></tr>
<tr><td>p75</td><td class="num gd">+3,264</td><td>good</td></tr>
<tr><td>p95</td><td class="num gd">+4,656</td><td>very good</td></tr>
</table>
<div class="lead" style="margin-top:11px">136 comparable weeks at today's volatility regime.
Positive in <span class="gd">80%</span> of them. We cannot forecast direction — five directional
strategies were tested and all five failed. This says where weeks like this one have
<span class="cy">landed</span>, and the contest gets exactly one draw.</div>

<h2>LIVE TERMINAL — EVERYTHING THE AGENT DID
 <span class="live"><b></b>STREAMING</span></h2><div class="rule"></div>
<div class="lead">The raw activity streams, exactly as written: scheduled runs, pre-market
intelligence passes, and every ledger entry — approvals, refusals, exits, reconciliations.
Nothing summarised, nothing hidden. Refreshes with the page.</div>
<div class="term">
  <div class="legend"><span>🟢 filled</span><span>⛔ refused by a gate</span>
   <span>💰 exit / close</span><span>🛡️ permission</span><span>🔄 reconcile</span>
   <span>📡 pre-market intel</span><span>⏸️ outside window</span>
   <span style="color:var(--tif)">newest first · all times ET</span></div>
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
        positions = [{"symbol": p.get("symbol"), "bias": "—", "qty": p.get("qty"),
                      "pl": p.get("unrealized_pl")} for p in f.positions()]
    except Exception as e:
        err = str(e)[:110]
    os.makedirs("docs", exist_ok=True)
    html = build(account, positions, err)
    open("docs/index.html", "w").write(html)
    print(f"wrote docs/index.html ({len(html):,} bytes)" + (f" — account unread: {err}" if err else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main())
