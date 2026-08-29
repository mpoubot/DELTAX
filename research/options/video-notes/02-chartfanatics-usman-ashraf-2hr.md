# Video 02 — Options Trading for Beginners: Super Simple (2 Hour FREE Course)

**Source:** Chart Fanatics — https://youtu.be/6Bdv-_YUQ0s
**Length:** 1:59:54 · **Uploaded:** 2025-11-02 · **Views:** ~375,065
**Guest:** Usman Ashraf, founder of Options Hub (billed as a "verified seven-figure trader")
**Format:** Podcast interview, whiteboard + screen share. No chapters.
**Captions:** YouTube auto-generated (English), pulled 2026-08-29
**Status in corpus:** 2 of 10

> Concept notes in my own words, not a verbatim transcript.

---

## Headline: this video contradicts Video 01

Video 01 (Sky View) argues you should **never buy options** and should sell
premium for time decay. This video is a **long-premium, directional, short-hold**
approach — buying calls and puts for leverage and flipping the premium before
expiration. The guest says outright that most traders he knows "don't really sell
options that aggressively."

They agree almost perfectly on **mechanics** and disagree almost completely on
**strategy**. That split is the most useful thing to come out of the corpus so
far, and it's tracked in `golden-rules.md`.

---

## Structure (derived — no chapter markers)

| Time | Topic |
|---|---|
| 0:00 | Intro, channel promo |
| 0:03 | What an option is; house and car analogies |
| 0:10 | Calls vs puts; buyer vs seller |
| 0:18 | AMD worked example; exercise vs flipping premium |
| 0:24 | Trading hours and exercise cutoffs |
| 0:30 | Reading the option chain; ITM / ATM / OTM |
| 0:36 | Intrinsic vs extrinsic value across expirations |
| 0:40 | Implied volatility and the expected-move range |
| 0:49 | The Greeks |
| 1:17 | Spreads and multi-leg strategies (named, not taught) |
| 1:19 | **Liquidity: volume vs open interest** |
| 1:25 | Options flow and reading order clusters |
| 1:27 | META LEAPS case study |
| 1:36 | **Scaling out, stops, position sizing** |
| 1:42 | 0DTE and weekly expiry mechanics |
| 1:49 | Options profit calculator |

Roughly 6–8 minutes are sponsor reads (Apex, Funded Next, TradeZella,
propfirmtrader.com). This is ad-supported entertainment content, not a course.

---

## Core thesis

Options are a **leverage instrument**. One contract controls 100 shares for a
fraction of the capital, so a small account can take positions it otherwise
couldn't. You profit by selling the contract back at a higher premium — not by
exercising. Exercising forfeits the remaining extrinsic value and requires the
full capital to take delivery.

His framing of the seller's edge (stated, then not pursued): a seller wins if the
stock goes their way *or* goes nowhere, so they have "two out of three odds."
**This reasoning is wrong** — see flags.

---

## Mechanics taught (agrees with Video 01)

- 1 contract = 100 shares; premium × 100 = cost.
- Calls = long bias, puts = short bias.
- ITM / ATM / OTM defined the same way.
- **Intrinsic + extrinsic = contract value.** Intrinsic stays constant across
  expirations for a given strike; the entire price difference between expiries is
  extrinsic. He demonstrates this on a chain: same strike at 2 days, 9 days and
  23 days out, with only the time component changing.
- Deeper ITM = more expensive, decays slower, safer. Further OTM = cheaper, more
  aggressive, decays faster.

**New in this video:** options premiums trade 9:30–16:00 only. Exercise is
possible until roughly 17:30 (broker-dependent; he cites thinkorswim). Shares
from an exercise can then be traded until 20:00. So there's a window where the
contract is dead but a resulting stock position is still live.

---

## Implied volatility

Same conclusion as Video 01, different derivation. IV expresses the market's
expected move as a one-standard-deviation range — a **68% probability** the stock
lands inside it by expiration.

Worked example: $50 stock at 20% IV → expected range $40–$60, 68% confidence.

- IV expands → all premiums get more expensive (seller demands more for wider risk).
- IV contracts → premiums cheapen.
- IV decays as expiration approaches; the expected range narrows.
- Biggest IV drivers: **earnings**, macro events, general uncertainty. He cites
  COVID, when Apple contracts that normally ran ~$1 priced around $12.
- IV is about *uncertainty*, not direction.

He is explicit that understanding IV is what changed his trading, and that a
position can profit from IV expansion **with no move in the stock at all** — the
Vega channel.

---

## Greeks

| Greek | Treatment |
|---|---|
| **Delta** | Premium change per $1 move. Negative on puts. Deeper ITM = higher delta. Used as a sensitivity gauge, **not** as a probability proxy — unlike Video 01. |
| **Gamma** | Mentioned, barely used. |
| **Theta** | The clock working against him. He accepts it as a cost of leverage rather than avoiding it. |
| **Vega** | Premium change per 1 point of IV. Example: Vega $0.50, IV +5 → premium +$2.50. |

Notable position: asked why not trade futures to escape theta, he argues theta is
manageable once you understand premium behavior — "theta is not the problem, it's
you." Directly opposite to Video 01's stance that fighting theta is a losing game.

---

## Liquidity — the strongest original content here

This section is the most operationally useful material in the video and has no
equivalent in Video 01.

**Volume** resets to zero at each open; it's contracts traded today. At the
morning open it's near-useless — it's still zero.

**Open interest** is contracts still open as of the previous close. It's the
real measure of how much is available to trade against.

His rule: **check open interest before choosing a strike.** If OI is 100 and you
want 70 contracts, you're trying to take 70% of the available pool — you may fill
slowly or not at all, and slippage will be worst exactly when the stock is
running in your favor. His analogy: drawing balls blind from a bucket of 100 vs a
bucket of 5.

Corollary rule: **trade the same tickers repeatedly** so their liquidity profile
is already known. SPY/SPX/QQQ are named as effectively unconstrained.

**Options flow:** clusters of large orders at adjacent strikes within a short
window are a signal worth noticing — but he stresses it's ambiguous, because you
cannot distinguish directional bets from hedges. His hard rule: **flow never
justifies a trade on its own; the chart has to agree.**

---

## Trade and risk management rules stated

1. **Scale out in thirds — roughly 30% / 20% / 30%**, holding a runner.
2. Day trading: once the strike goes ITM, aim to be **out of 50%**, then scale the
   remainder slowly.
3. **Don't set fixed price targets.** Targets make you rigid; read price instead.
   (Cites people who held Dogecoin to zero waiting for $1.)
4. **Always use a stop.** He rejects the "size for zero" approach — sizing so the
   whole premium is acceptable risk — as the wrong mentality.
5. **Set stops on the underlying's price level, not the premium.** A premium stop
   can trigger from time decay alone while the stock hasn't moved against you.
   Trade-off: price stops must be managed manually.
6. **Trail the stop** to each new support/resistance level as price advances;
   exit the final tranche when a level fails to hold.
7. **Cut position size later in the week.** Same stock move produces much larger
   premium swings near expiry. His numbers: Mon–Wed a stop costs ~10–15% of
   premium; Thu–Fri the same stop costs 20–30%. So a $1,000 Monday position
   becomes $500–750 by Friday to equalize risk.
8. **Size up by growing the base, not by holding longer.** If you want to hold a
   $10k runner after scaling out, your starting size needs to be ~$30k. Don't
   solve "I should have held" by holding more of a small position.
9. 0DTE exists daily on SPY/SPX/QQQ; everything else is effectively 0DTE only on
   its Friday expiry.

---

## Flags before any of this trains an agent

- **The "two out of three odds" claim is a logical error.** Up, down and flat are
  not equiprobable outcomes, and the payoffs are wildly asymmetric — the seller's
  rare loss is far larger than the frequent win. This is the *same* trap as Video
  01's high-POP framing, arrived at from the opposite direction. Do not encode it.
- **The headline numbers are a single outlier anecdote.** The META LEAPS trade
  ($2 premium → $110; ~$2,500 risk → ~$106,000) is one trade from roughly two
  years prior, reconstructed from memory without exact dates, and he confirms he
  did **not** hold the full position. The "$2,500 → $106,000" figure in the
  video's cold open is a hypothetical on size he didn't carry. Treat as marketing.
- **No win rate, sample size, or expectancy is given anywhere.** Unlike Video 01,
  which at least showed five live trades, this video shows only winners.
- **Heavy commercial conflict.** Multiple prop-firm sponsors plus the guest's own
  Options Hub. The content is selected to make options look accessible and
  lucrative.
- **"Standard deviation of 68%" is loose phrasing** — 68% is the confidence
  interval of one SD, not the SD itself. Harmless here, but don't propagate it.
- The IV → premium mechanism and the OI liquidity rules are **structural facts**
  and are the parts of this video most worth keeping.

**Candidate rules to carry forward for testing:**
open-interest floor relative to intended size; ticker whitelist for known
liquidity; price-level stops rather than premium stops; size reduction as DTE
falls; scale-out ladder; chart confirmation required before acting on flow or IV
signals.
