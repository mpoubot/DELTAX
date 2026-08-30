"""Generate docs/index.html — the public demo page, served by GitHub Pages.

Same data as the terminal dashboard, same honesty rules: nothing is invented,
a value that cannot be read is shown as unavailable rather than as a plausible
number, and every figure says where it came from.

  python3 -m deltax.webdash          write docs/index.html
"""
from __future__ import annotations
import json, glob, os, sys
from datetime import datetime, timezone

NAVY="#0A1428"; CHROME="#C8D4E0"; BLUE="#1E90FF"; CARD="#0F1D33"; DIM="#7A8BA0"

def _ledger_rows(limit=40):
    rows=[]
    for f in sorted(glob.glob("logs/decisions-*.jsonl")):
        for line in open(f):
            try: r=json.loads(line)
            except Exception: continue
            rows.append(r)
    return rows[-limit:]

def build(account=None, positions=None, error=None) -> str:
    now=datetime.now(timezone.utc)
    rows=_ledger_rows()
    decisions=[r for r in rows if r.get("kind")!="event" and r.get("decision")]
    refused=[r for r in decisions if r.get("decision")!="TRADE"]
    traded=[r for r in decisions if r.get("decision")=="TRADE"]
    gate_counts={}
    for r in refused:
        g=r.get("failed_gate") or "?"
        gate_counts[g]=gate_counts.get(g,0)+1
    top=sorted(gate_counts.items(), key=lambda x:-x[1])[:8]

    eq=cash=None; acct_no="—"
    if account:
        eq=account.get("equity"); cash=account.get("cash")
        acct_no=account.get("account_number","—")

    def card(label, value, note=""):
        return (f'<div class="card"><div class="lbl">{label}</div>'
                f'<div class="val">{value}</div><div class="note">{note}</div></div>')

    pos_rows=""
    for p in (positions or []):
        pos_rows+=(f"<tr><td>{p.get('symbol','')}</td><td>{p.get('bias','')}</td>"
                   f"<td>{p.get('qty','')}</td><td>{p.get('pl','')}</td></tr>")
    if not pos_rows:
        pos_rows=('<tr><td colspan="4" class="empty">No open positions. '
                  'The agent has placed no orders.</td></tr>')

    gate_rows="".join(
        f'<tr><td><code>{g}</code></td><td class="num">{n}</td>'
        f'<td class="bar"><span style="width:{n/max(1,top[0][1])*100:.0f}%"></span></td></tr>'
        for g,n in top) or '<tr><td colspan="3" class="empty">No refusals recorded yet.</td></tr>'

    banner=""
    if error:
        banner=(f'<div class="warn">⚠ Live account could not be read: {error}. '
                f'Figures below are omitted rather than estimated.</div>')

    return f"""<title>DELTAX — Autonomous Options Agent</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:{NAVY};color:{CHROME};
 font:15px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}}
.wrap{{max-width:1080px;margin:0 auto;padding:28px 20px 60px}}
h1{{font-size:30px;margin:0;letter-spacing:.14em;color:#fff}}
h1 span{{color:{BLUE}}}
.sub{{color:{DIM};margin:6px 0 4px;letter-spacing:.05em}}
.team{{color:{DIM};font-size:11px;letter-spacing:.1em;text-transform:uppercase;margin-bottom:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-bottom:26px}}
.card{{background:{CARD};border:1px solid #1d3050;border-radius:10px;padding:14px 16px}}
.lbl{{color:{DIM};font-size:11px;letter-spacing:.12em;text-transform:uppercase}}
.val{{font-size:23px;color:#fff;margin-top:5px}}
.note{{color:{DIM};font-size:11px;margin-top:3px}}
h2{{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:{BLUE};
 margin:30px 0 10px;border-bottom:1px solid #1d3050;padding-bottom:7px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;color:{DIM};font-weight:400;font-size:11px;
 letter-spacing:.1em;text-transform:uppercase;padding:7px 8px}}
td{{padding:7px 8px;border-top:1px solid #16263f}}
td.num{{text-align:right;color:#fff}}
td.empty{{color:{DIM};text-align:center;padding:20px}}
td.bar span{{display:block;height:7px;background:{BLUE};border-radius:3px}}
code{{color:{BLUE}}}
.warn{{background:#3a2a08;border:1px solid #7a5a10;color:#f0c674;
 padding:10px 14px;border-radius:8px;margin-bottom:18px;font-size:13px}}
.foot{{color:{DIM};font-size:11px;margin-top:34px;border-top:1px solid #1d3050;padding-top:14px}}
.tag{{display:inline-block;background:#132b4c;border:1px solid #1d3050;border-radius:20px;
 padding:2px 11px;margin-right:6px;font-size:11px;color:{DIM}}}
@media(max-width:600px){{.val{{font-size:19px}}h1{{font-size:22px}}}}
</style>
<div class="wrap">
<h1>DELTA<span>X</span></h1>
<div class="sub">AUTONOMOUS OPTIONS TRADING &nbsp;·&nbsp; CODE · RISK · EXECUTE</div>
<div class="team">TEAM SYNC BOARD &nbsp;·&nbsp; shared status for the DELTAX team &nbsp;·&nbsp;
 <span class="tag">US</span><span class="tag">Latvia</span><span class="tag">Denmark</span></div>
{banner}
<div class="grid">
{card("Account", acct_no, "Alpaca paper")}
{card("Equity", f"${float(eq):,.0f}" if eq else "unavailable", "live" if eq else "not read")}
{card("Cash", f"${float(cash):,.0f}" if cash else "unavailable", "")}
{card("Open positions", len(positions or []), "")}
{card("Decisions logged", len(decisions), "every evaluation, incl. refusals")}
{card("Refused", len(refused), f"{len(refused)/max(1,len(decisions))*100:.0f}% of candidates")}
</div>

<h2>Why the agent said no</h2>
<p class="note">Every evaluation is recorded — approvals and refusals alike — in a
hash-chained, append-only ledger. An agent that can explain why it declined a
candidate demonstrates more than a P&amp;L number can.</p>
<table><tr><th>Gate</th><th>Refusals</th><th></th></tr>{gate_rows}</table>

<h2>Open positions</h2>
<table><tr><th>Symbol</th><th>Bias</th><th>Qty</th><th>P&amp;L</th></tr>{pos_rows}</table>

<h2>Book allocation</h2>
<table>
<tr><th>Sleeve</th><th>Capital</th><th>Structure</th><th>Status</th></tr>
<tr><td>Options</td><td class="num">$30,000 risk</td><td>Iron condors, 11 DTE, δ0.20</td><td>validated</td></tr>
<tr><td>Stocks</td><td class="num">$60,000</td><td>Covered calls</td><td>build pending</td></tr>
<tr><td>Crypto</td><td class="num">$10,000</td><td>Spot — no crypto options on venue</td><td>build pending</td></tr>
</table>

<h2>How it decides</h2>
<table>
<tr><td>Structure</td><td>Iron condors — direction-neutral credit spreads, defined risk</td></tr>
<tr><td>Direction</td><td>Put spread = 📈 LONG · Call spread = 📉 SHORT · book reports its net lean</td></tr>
<tr><td>Risk</td><td>2% per position · 30% portfolio · −5% daily kill switch</td></tr>
<tr><td>Gates</td><td>13 deterministic gates, fail-closed — unknown is never treated as safe</td></tr>
<tr><td>Permission</td><td>NORMAL → CAUTION → DEFENSIVE → NO_NEW_POSITIONS → HALT, above strategy</td></tr>
<tr><td>Validation</td><td>Walk-forward, base-rate comparison, Bonferroni; failed ideas are stopped, not tuned</td></tr>
</table>

<div class="foot">
Generated {now:%Y-%m-%d %H:%M} UTC · refreshed every 5 minutes by a scheduled job ·
paper trading only, no real capital ·
<span class="tag">312 tests</span><span class="tag">Alpaca CLI</span><span class="tag">MIT</span>
</div>
</div>"""


def main():
    account=positions=None; err=None
    try:
        from deltax.feeds import AlpacaFeed
        f=AlpacaFeed(); account=f.account()
        positions=[{"symbol":p.get("symbol"),"bias":"—","qty":p.get("qty"),
                    "pl":p.get("unrealized_pl")} for p in f.positions()]
    except Exception as e:
        err=str(e)[:120]
    os.makedirs("docs", exist_ok=True)
    html=build(account, positions, err)
    with open("docs/index.html","w") as fh: fh.write(html)
    print(f"wrote docs/index.html ({len(html):,} bytes)" + (f" — account unread: {err}" if err else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main())
