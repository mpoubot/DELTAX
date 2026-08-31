# Decision Gates — registered

Source: **Matin / Elate ApS**. Two documents, 31 Aug 2026:
- `Market_Signal_Gates_Summary.docx` (09:14 ET)
- `Trading_Decision_Gates_Summary.docx` (09:19 ET) — supersedes, adds the Earnings Gate

Three gates. Two are log-only and stay out of the trading path. **The third is a
hard constraint and converges with a gap we found in our own code hours earlier.**

Two standalone scanners surfacing "smart money" signals — unusual options flow
for equities, derivatives anomalies for crypto.

| | Stock Signal Gate | Crypto Signal Gate |
|---|---|---|
| Data source | Unusual Whales API | CoinGlass API |
| Universe | S&P 500 + Nasdaq 100 + Dow (~600) | BTC/ETH/SOL + majors |
| Signal | Options premium/volume anomalies, net flow | Funding extremes, OI divergence, large prints |
| Storage | Append-only CSV | Append-only CSV |
| Dashboard | `localhost:8788` | `localhost:8789` |

## Status: NOT wired into the trading path

This is the author's own position, not an imposition on it — the document
states **"log/alert only — no auto-trading action"** and that stands.

Three reasons it stays out of the gates for now, all from the document itself:

1. **Running in mock mode** — synthetic data, no paid API keys attached.
2. **Endpoints unverified** — paths come from public docs, never tested against
   a live key.
3. **Thresholds untuned** — "intentionally simple starting points; thresholds
   should be tuned after watching a few days of real data".

Under **E10** (classify before encoding), nothing gates a trade until it has
been backtested against real data. A scanner scoring synthetic flow cannot
satisfy that, and wiring it would mean the agent acting on numbers no one has
checked. Under **E28**, an unverified endpoint that fails silently is the exact
shape that produced the earnings fail-open.

---

## 3. Earnings Gate — IN PROGRESS, and it matters most

Unlike the other two, this one **actively blocks trading**. It is also the most
useful thing in either document, because it independently arrives at a
constraint we had already been forced to write.

**Convergence with E28.** At 03:40 this morning our own earnings gate was found
fail-OPEN: `earnings_date=None` meant both "this ETF genuinely has no earnings"
and "the SEC lookup raised", and both passed. Matin's design treats the earnings
window as a hard no-trade constraint from first principles. Two people, two
codebases, same conclusion within hours — the strongest kind of agreement.

**His blackout rule is more precise than ours.** We ask a single question: does
an earnings date fall on or before expiry? He distinguishes report timing:

| Timing | Blackout window |
|---|---|
| **AMC** (after close) | that day's close → next full session's close |
| **BMO** (before open) | prior day's close → report day's close |
| **Unconfirmed** | widest window (prior close → next close), flagged as unconfirmed |

The unconfirmed case is the same fail-closed instinct as E28, reached
independently: when the timing is unknown, widen the refusal rather than
narrow it.

**He also uses the real NYSE calendar** including holidays, rather than weekday
arithmetic. Ours does not, and should.

**Where the designs differ, and why both are right for their own book.** His
sources from Financial Modeling Prep (estimates, actuals, BMO/AMC flags; needs a
paid key). Ours reads SEC 8-K Item 2.02 — free and authoritative, but it returns
nothing for ETFs, which is what produced the `RuntimeError` noise in this
morning's brief. **FMP's BMO/AMC timing is a genuine improvement over what we
have and is the piece worth adopting.**

### Known limitation in OUR code, stated plainly

`deltax/run.py` does not pass earnings data into `evaluate()` at all — the gate
runs on defaults and passes vacuously. Today's exposure is nil: the universe is
11 ETFs plus MA, V, KO, PG, XOM, WMT, none reporting before 11 Sep. **This must
be wired before any individual-stock name is added to the universe**, and
Matin's blocklist-file design is the cleanest way to do it: he writes a live
blocklist, our runner reads it, no API key needed on our side.

---

## Path to activation

1. Live API keys attached; both dashboards confirmed pulling real data
2. Several days of real signal history logged
3. Thresholds tuned against that history
4. **Backtested** — does the signal predict anything, measured against base rate
   and corrected for multiple comparisons?
5. Only then: proposed as a **veto**, never as an originator. Per the corpus,
   news and flow can refuse a trade the gates approved; they can never create one.

**The Earnings Gate is exempt from that queue.** It is a hard constraint rather
than a signal, it converges with a gap already in our own corpus, and its
blocklist-file interface needs no validation of predictive power — it does not
predict, it refuses. It is the first of Matin's gates to integrate, once his
scan loop and bot-facing function are complete.

The two signal gates stay queued alongside the Unusual Whales flow data and
index-futures notes from the same morning, for review after the session
settles.
