# DELTAX — news and data feeds

## You already have a news feed. Use it.

Alpaca ships a news API (Benzinga-sourced), available through the CLI we're
already required to use:

```bash
alpaca data news --symbols SPY,NVDA --limit 10
alpaca data news --symbols NVDA --start 2026-08-25 --include-content
alpaca data news --limit 50 --jq '.news[] | {t:.created_at, s:.symbols, h:.headline}'
```

Verified working on our account. Each article returns:
`headline · summary · content · source · symbols · author · url · created_at`

**Why this beats bolting on external vendors:**

- **It's graded.** "Technology Implementation" scores how well we use Alpaca's
  stack. A second news vendor scores nothing and adds a dependency.
- Symbols come pre-tagged, so no entity extraction step.
- Same auth, same CLI, same JSON shape as every other call in the agent.
- No extra key for teammates in Latvia and Denmark to obtain.

---

## 🔴 Before building anything on news: we already tested this and it failed

**The TSLA playbook was tested on exactly this premise and did not survive
validation — news direction was no better than a coin flip (p = 0.44).**

That is our own result, on our own data. Rebuilding "read the news → predict
direction" under a five-day deadline would be repeating a known failure with less
time to catch it.

This is also what the video corpus found independently. Video 02 covers options
flow and reaches the same wall: **you cannot distinguish a directional bet from a
hedge.** A large block print looks identical whether someone is speculating or
insuring. Its author's own rule is that flow never justifies a trade on its own.

**So: "whale flow" and news sentiment are not sources of edge for us.** Anyone
selling unusual-options-activity signals is selling the ambiguity, not resolving
it.

---

## What news is actually good for: risk gating

Reframe it from *predictive* to *defensive*. News doesn't tell us what to trade —
it tells us what **not** to trade. That fits the whole strategy: the discipline is
the product.

### Gate 1 — Earnings exclusion ⭐ highest value

Every source in our corpus agrees earnings are the dominant driver of implied
volatility. Selling premium into an earnings event looks wonderful right up to the
IV crush.

> **Rule:** no new position where an earnings announcement falls before expiry.

Detect via `alpaca data corporate-actions` plus a news scan for earnings-date
announcements. This single gate probably prevents more damage than any signal we
could build would generate.

### Gate 2 — Halt and corporate-action exclusion

> **Rule:** skip any underlying with a trading halt, pending M&A, split, or
> delisting notice.

An options position in a halted name cannot be closed. That's an unbounded-risk
scenario our 5% portfolio cap doesn't protect against, because the cap assumes we
can exit.

### Gate 3 — Anomalous-premium check

Our own inference from the ClearValue video's SIRI example: a premium that looks
too generous *is the market pricing risk we haven't found yet*. Rich yield is a
warning, not an opportunity.

> **Rule:** when a candidate's premium is unusually high for its strike distance,
> check the news feed for a catalyst. No explanation found → skip it.

This turns news into a **confirmation of ignorance** rather than a prediction —
epistemically honest and much harder to get wrong.

---

## Credible free sources, if we extend past Alpaca

Ranked by signal-to-noise. All free, all authoritative, none require a paid tier.

| Source | What it gives | Access |
|---|---|---|
| **SEC EDGAR** | 8-K material events, S-1, 13F institutional holdings | Free REST + RSS, no key. *The* primary source — everything else reports on this |
| **CBOE** | Put/call ratios, VIX and term structure, total options volume | Free daily CSV |
| **FRED** (St. Louis Fed) | Rates, macro series, recession indicators | Free API with key |
| **Treasury / BLS / BEA** | Economic release calendar — the scheduled IV events | Free |
| **Exchange halt feeds** | Nasdaq/NYSE real-time halts | Free |

**On 13F filings and "whale tracking":** they're real and authoritative, but filed
**45 days after quarter end.** By the time you read one, the position may be long
closed. Useful for research, useless for a five-day competition.

**Avoid:** scraped aggregators, sentiment-score vendors, "unusual options
activity" alert services, and anything advertising a win rate. Every one of those
patterns appears in our corpus flags.

---

## ⚠️ Security: an autonomous agent reading news is an injection target

This matters and it's worth putting in the write-up.

If the agent feeds article text to an LLM that then makes trading decisions,
**the article text is untrusted input.** A crafted headline or body could contain
text designed to steer the model. This isn't hypothetical — it's the standard
attack against any LLM pipeline consuming third-party content.

**Mitigations to build in:**

1. News may only ever **veto** a trade, never originate one. If the model is
   restricted to "block / don't block", injected text cannot open a position.
2. Deterministic risk gates run **after** any model output and cannot be
   overridden by it. Position sizing, the 1%/5% caps and the expectancy check are
   plain code, not model judgment.
3. Treat article content as data in the prompt, clearly delimited, never as
   instructions.
4. Log every article ID that influenced a decision, so any outcome is auditable.

Point 2 is the architecture that makes the whole thing safe: **the model proposes
and can abstain; the code disposes.** Worth saying out loud to the judges.

---

## Storage note

Store article **IDs, URLs, symbols, timestamps and our own derived flags.** Do not
archive full article text in the public repo — it's licensed third-party content
and we don't need it. The feed is queryable on demand.

---

## Recommendation for the five-day window

**Use the Alpaca news feed for gates 1 and 2 only. Ship nothing else.**

Earnings exclusion and halt exclusion are perhaps 40 lines of code, they measurably
reduce tail risk, they demonstrate Alpaca stack usage, and they cannot blow up.
A sentiment or flow model cannot be validated before Friday, and our own prior
result says it wouldn't work anyway.

If there's time after the agent is running end to end, gate 3 is the next
addition. Everything below that line is post-hackathon.


---

## Feed registry (`deltax/rss.py`)

Generic RSS/Atom ingestion, **metadata only** — title, link, timestamp,
categories. Article bodies are never stored: licensed third-party content the
agent does not need.

| Feed | Bucket | Active | Why |
|---|---|---|---|
| `coindesk` | crypto | ❌ | Registered for the crypto engine. Flag flip when that bucket ships — no new code |
| `oilprice` | macro | ❌ | Energy/macro context; informs no gate the agent runs today |
| `wsj_markets` | equities | ❌ | ⚠️ **Dead feed** — newest item 2025-01-27, ~19 months stale |
| `sec_8k` | equities | ⚙️ | The one targeting a real gap. Needs `DELTAX_SEC_UA` |

**`active` means: can this feed inform a gate the agent currently runs?** A feed
can be wired and registered without pretending it affects decisions.

### The freshness guard

`is_stale()` rejects any feed whose newest item is older than 48 hours.

This exists because of a live finding: the WSJ Markets feed in the team's n8n
"Market Notes to Telegram" workflow **parses perfectly and returns well-formed
items from January 2025.** A dead feed does not error — it quietly serves
19-month-old headlines forever. Parsing is not liveness, and any feed must pass
this check before informing a decision.

*(Worth fixing in the n8n workflow too — it has been publishing stale market
notes to Telegram.)*

### SEC EDGAR

8-K Item 2.02 filings are earnings releases — the authoritative source for the
earnings gate. SEC returns **403 to generic user agents**; their policy requires
a real name and contact email:

```bash
export DELTAX_SEC_UA="Your Name your@email.com"
```

Read from the environment, never hardcoded. Verified working against AVGO's CIK.

**Caveat:** 8-K is retrospective. It confirms when earnings *happened*, not when
the next one *will* be. It establishes cadence; a confirmed forward date still
comes from the company's IR page. Under E10 that inference is **empirical**, not
structural.


---

## Earnings dates — solved via SEC 8-K Item 2.02

`deltax/earnings.py`. Item 2.02 ("Results of Operations and Financial
Condition") is the filing a company makes when it releases earnings, so the
filing dates are an authoritative record of when earnings *happened*. Free,
public, no vendor, no licence.

**Fact vs inference (E10).** Past dates are the filing record — structural.
The *next* date is inferred from observed cadence — empirical. So the gate
consumes a **window**, never a point estimate, and any overlap with a
contract's life is a blackout. Being wrong that way costs a skipped trade;
being wrong the other way costs an earnings gap through an open position.

### Live result, expiry 2026-09-18

| Blocked | Why |
|---|---|
| AVGO | window 2026-08-25 .. 2026-09-09 |
| COST | window 2026-08-13 .. 2026-09-29 |
| TSLA | window 2026-08-07 .. 2026-10-06 |
| PDD | foreign private issuer — see below |

**Clear:** AAPL, MSFT, NVDA, AMZN, META, GOOGL, NFLX, AMD, JPM

AVGO is the vindication: the 350/340 spread that passed all twelve gates this
morning has an earnings release inside its life. Three independent signals now
agree — the news headline, IV at 52–54%, and the filing cadence.

### Two failure modes found and fixed

**Silent rate-limit failure.** SEC throttles. A batch run over thirteen symbols
returned empty for some, and `earnings_history` reported that as "no filings"
— indistinguishable from a genuine absence. Now throttled to 150 ms between
requests, and a failed fetch raises `SECFetchError` rather than returning `[]`.
*Parsing is not liveness; an empty result is not a negative answer.*

**Foreign private issuers.** PDD files **6-K and 20-F**, never 8-K, so Item
2.02 does not exist for it. This is structural, not a data gap — the method
simply does not apply to ADRs, and a different source is required. Detected
automatically and reported as the reason rather than as missing history.

### What this does not provide

- **Transcripts** — not available from any free authoritative source, and
  licensed where they exist.
- **Analyst estimates / consensus** — enterprise data (IBES and equivalents).
  Not obtainable in this timeframe.

Neither is needed. The gate's job is to **avoid** earnings, not to forecast
them — and forecasting from news already failed validation once (TSLA
playbook, p=0.44). Predicting an earnings reaction would be a fresh empirical
claim requiring the full validation bar.
