# Video 01 — Options Trading For Beginners (Complete 4 Hour Course)

**Source:** Sky View Trading — https://youtu.be/u847cbKEWu0
**Length:** 3:56:17 · **Uploaded:** 2025-09-27 · **Views:** ~520,700
**Captions:** YouTube auto-generated (English), pulled 2026-08-29
**Status in corpus:** 1 of 10

> These are concept notes in my own words, not a verbatim transcript. See
> "Why not a raw transcript" at the bottom.

---

## Chapter map

| Time | Chapter |
|---|---|
| 0:00 | Why options exist |
| 13:26 | Reading an option chain |
| 24:24 | Option pricing |
| 59:26 | Option Greeks |
| 1:13:38 | Buying options (long option) |
| 1:39:31 | Selling options (short option) |
| 2:20:05 | Covered stock |
| 2:32:29 | Long vertical |
| 2:42:47 | Short vertical |
| 2:53:04 | Iron condor |
| 3:04:02 | Butterfly |
| 3:23:16 | Strangle |
| 3:32:17 | Straddle |
| 3:41:43 | Back ratio |

---

## The channel's core thesis

The whole course argues one position: **do not buy options to bet on direction.
Sell premium and collect time decay instead.**

Their reasoning chain:

1. Direction is not predictable with enough edge to overcome cost. They assert
   most retail traders lose because they spend their effort forecasting price.
2. A long option fights theta every day. To profit you need the stock to move
   *far enough, fast enough* to beat the premium paid — not merely to move the
   right way.
3. They claim a long option **never** has better than ~50% probability of
   profit, because the break-even sits beyond the strike by the premium paid.
4. Therefore: take the other side. Sell the option, be paid the premium, and
   win whenever the stock does *not* do a specific thing.

Framing they use throughout: **options are insurance.** The seller is the
insurer collecting a recurring premium; the buyer is paying for protection.
This drives every other explanation in the course.

Key reframe worth encoding: selling is a bet on **where the stock won't go**,
not where it will. That converts a directional forecast into a range forecast,
which they claim is a far easier problem.

---

## Pricing model taught

Three inputs move an option's price day to day:

1. **Underlying price** — calls gain as the stock rises, puts as it falls.
2. **Time to expiration** — more days, more premium (the insurance-term analogy).
3. **Implied volatility** — higher expected movement, more expensive options.

Decomposition:

- **Intrinsic value** = the in-the-money amount. At expiration this is *all*
  an option is worth.
- **Extrinsic value** = everything above intrinsic; pure time/volatility value.
  Decays to zero at expiration.

Consequences they stress:
- Every OTM option expires worthless. That is the seller's entire business model.
- An ITM option at expiry is worth exactly strike-vs-spot difference.
- Long break-even at expiry = strike ± premium paid. The stock must clear that,
  not just the strike.
- IV is derived *from* option prices, not the reverse. Prices are set by supply
  and demand; IV is the number those prices imply. They describe it as a fear
  gauge — demand for protection spikes when investors are scared, which raises
  premium.
- They claim **IV is more predictable than price** (mean-reverting), and that
  this, not direction, is the exploitable edge. Detail deferred to their "part two."

Mechanics: 1 contract = 100 shares; quoted prices carry a ×100 multiplier
(a 2.33 quote costs $233). Buy at ask, sell at bid.

---

## Greeks, as they use them

| Greek | Definition given | How they actually use it |
|---|---|---|
| **Delta** | Price change per $1 move in the underlying | Doubles as **approximate probability the option finishes ITM** — this is their strike-selection tool. Also read as share-equivalent directional exposure at position level. |
| **Gamma** | Rate of change of delta per $1 move | Explicitly de-emphasized. "We don't look at it much." Only concept: delta is not fixed. |
| **Theta** | Price change per day elapsed | The profit engine. Position theta must be **positive**. |
| **Vega** | Price change per 1 point of IV | Short-premium positions are short vega; they want IV to fall after entry. |

Position-level Greeks are treated as the real risk dashboard: delta = directional
exposure, theta = daily income, vega = volatility exposure. Their example iron
condor ran delta ≈ −9 on 10 contracts (near-neutral by design), theta ≈ +$72/day.

---

## Explicit rules stated for selling premium

These are the only hard numbers the course commits to:

1. **Sell when IV is high.** Rich premium lets you move further OTM for the same
   credit. (Their "part two" covers ranking IV; not quantified here.)
2. **Open 30–60 DTE.** Called the sweet spot for premium selling, attributed to
   unspecified internal research.
3. **Strike at ~65–85% probability OTM** (i.e. ~15–35 delta), balancing win rate
   against credit size.
4. **Minimum credit ~$0.75 per contract.** Below that, fees eat the trade and
   there's no room to take profit early.
5. **Take profits early** — stated as a reason for rule 4, but no target
   percentage is given in this video.
6. **Widen strikes to raise probability of profit**, accepting worse
   risk/reward. On back ratios: widen as far as possible *while still
   collecting a credit*.

Directional bias: short call = bearish/neutral; short put = bullish/neutral.

Break-evens: short call = strike + credit. Short put = strike − credit
(also the true max loss, since a stock floors at zero).

Risk framing: they concede a naked short call is undefined-risk and argue
"theoretical risk far exceeds actual risk," with position sizing as the real
control. They still **do not** recommend naked options as a first trade —
their recommended starting strategy is the **vertical spread**, which keeps the
premium-selling win rate but caps loss.

Early assignment is dismissed as a non-event operationally — the broker alert
sounds alarming but resolves into a stock position you close.

---

## Strategy inventory

Defined-risk, short-premium (their preferred zone): short vertical, iron condor,
butterfly, back ratio. Undefined-risk short premium: naked short call/put,
strangle, straddle. Long premium (they discourage): long call/put, long vertical.
Stock-overlay: covered stock/covered call, framed as improving break-even and
POP on shares you already hold at the cost of capped upside.

The consistent trade-off axis across every strategy: **wider strikes → higher
probability of profit → worse risk/reward.** Every choice in the course sits
somewhere on that line.

---

## Flags before any of this trains an agent

**Treat these as claims, not validated rules.**

- **The recording is old.** The screen examples show Twitter near $18 with
  Nov 2016 expirations, and the platform is thinkorswim under TD Ameritrade —
  a broker that no longer exists as such. The 2025 upload date is a re-publish.
  Concepts hold; platform specifics and any market-regime claims do not.
- **This is marketing for a paid service.** There's a mid-video pitch for
  their trading program. The 30–60 DTE and 65–85% POP numbers are asserted from
  "a lot of research" that is never shown.
- **POP is not expectancy — and their own demo proves it.** They ran five live
  short-option trades, won four, lost one, and state the basket **lost money
  overall**. That is the central caution for us: an 85% win rate with a fat left
  tail can still be negative EV. Any rule we encode from this video must be
  validated on expectancy, not hit rate. This is the same failure mode that
  killed the TSLA playbook.
- **The IV-is-predictable claim is the load-bearing one and it is not supported
  in this video.** It's deferred to a paid "part two." If the edge is real it
  lives there, and we have not seen it.

**Candidate rules to carry forward for testing** (not to adopt):
positive position theta as an entry filter; 30–60 DTE window; 15–35 delta short
strike; IV-rank-high entry gate; defined-risk structures only. Each needs its own
backtest before it touches the agent.

---

## Why not a raw transcript

I read the full auto-caption track to build these notes, but I haven't saved the
verbatim text. This is a commercial course a company sells access to, and
stashing ten of them word-for-word would be republishing their material. The
distillation above is what the agent actually needs — the rules, parameters and
reasoning are facts and aren't theirs to own — and it's a fraction of the tokens
to feed in later. If you want a specific passage quoted exactly for a citation,
say which and I'll pull it.
