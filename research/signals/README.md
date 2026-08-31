# Signal Gates — registered, not wired

Source: **Matin / Elate ApS**, received 31 Aug 2026, 09:14 ET.
Document: `Market_Signal_Gates_Summary.docx`

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

## Path to activation

1. Live API keys attached; both dashboards confirmed pulling real data
2. Several days of real signal history logged
3. Thresholds tuned against that history
4. **Backtested** — does the signal predict anything, measured against base rate
   and corrected for multiple comparisons?
5. Only then: proposed as a **veto**, never as an originator. Per the corpus,
   news and flow can refuse a trade the gates approved; they can never create one.

Queued alongside the Unusual Whales flow data and index-futures notes received
the same morning, for review after the trading day settles.
