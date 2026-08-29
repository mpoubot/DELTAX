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
