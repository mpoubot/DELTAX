# Video 04 — Options Trading For Beginners: Complete Guide with Examples

**Source:** ClearValue Tax (Brian Kim, CPA) — https://youtu.be/NW1ziUDjB7w
**Length:** 50:23 · **Uploaded:** 2023-10-15 · **Views:** ~2,587,650
**Captions:** YouTube auto-generated (English), pulled 2026-08-29
**Status in corpus:** 4 of 10 — **third independent viewpoint**

---

## Why this one matters

This is the first source in the corpus with an **investor** frame rather than a
trader frame. Sky View (01/03) sells defined-risk spreads for time decay; Chart
Fanatics (02) buys leverage for directional moves. This video treats options as a
**yield overlay on a long stock portfolio** — covered calls and cash-secured puts,
both collateralized by something you already want to hold.

It's also the most honest of the four in one specific respect, and the most
misleading in another. Both are detailed below.

---

## Structure

| Time | Topic |
|---|---|
| 0:00 | Buying call options — YELP worked example, 4 outcome scenarios |
| 9:00 | Reading the chain; strike and duration effects on price |
| 12:00 | **Covered calls** — INTC worked example, 4 scenarios |
| 21:00 | Covered call variables: duration and strike |
| 25:26 | Downside and opportunity cost |
| 26:00 | Order mechanics for writing covered calls |
| 31:00 | Buying put options — Dave & Buster's (PLAY) example |
| 40:00 | **Cash-secured puts** — SIRI example, 3 scenarios |
| 47:00 | Nightmare scenario and honest comparison |
| 48:00 | Order entry mechanics |

Presented on Robinhood screenshots with live prices. Light promotion (own website
at the end), no third-party sponsors.

---

## Core thesis

Two income strategies, both framed as lowering risk relative to holding stock:

**Covered call** — own 100 shares, sell a call against them. You keep the premium
in all cases. The trade-off is a cap on upside: if the stock blows past the
strike, you're forced to sell there and forgo the rest.

**Cash-secured put** — sell a put on a stock you already want to own, holding
cash to cover assignment. Either the stock stays above the strike and you keep the
premium, or it falls and you buy the stock you wanted anyway, at a net cost
reduced by the premium.

His summary of the CSP: buy the stock at a discount, or get paid for failing to.

---

## Mechanics taught (agrees with all prior sources)

- 1 contract = 100 shares; ×100 multiplier on quoted premium.
- OTM at expiration = worthless.
- You can close a contract any time; exercising is optional and usually
  unnecessary — selling the contract captures remaining extrinsic value.
- Buy at the ask, sell at the bid.
- Pricing, stated as three rules: **more time = more premium; closer to the money
  = more premium; more volatile = more premium.** This is the same three-factor
  model as Videos 01 and 03, expressed operationally rather than theoretically.

**Strike/duration trade-off for covered calls** — the mirror of Video 01's
framing: nearer strike collects more premium but caps upside sooner; further
strike collects less but leaves room to run.

**Roll-vs-hold insight (original to this video):** selling a 6-month call once
locks in a known premium. Selling three 2-month calls in sequence *might* total
more, but only if the option still prices similarly at each renewal — and if the
stock has fallen by then, the next premium will be far smaller. Shorter duration
means recurring **reinvestment risk** on the premium stream. None of the other
sources raise this.

---

## Rules stated

1. **Never write a covered call on a stock you don't want to own.** "Don't buy a
   crappy stock" just to harvest premium — described as dropping quarters to pick
   up pennies.
2. **Only sell cash-secured puts on stocks you'd be happy to own at that strike.**
   Assignment is the expected outcome, not the failure case.
3. **If the risk isn't worth the reward, skip the trade.** Premium income is not
   a reason on its own.
4. **Shop the chain** — some weeks offer good premium, some don't. Not every
   period has a trade.
5. **Use limit orders, not market orders**, when opening option positions. The
   only source in the corpus so far to say this, and it matters most in the thin
   strikes Video 02 warns about.
6. You need 100 shares per covered call contract; you can write against part of a
   position rather than all of it.
7. Premium is credited immediately on sale; assignment and expiry are handled
   automatically by the broker.
8. Time-in-force: day orders self-cancel, GTC persists.

---

## The genuinely honest part

His cash-secured put "nightmare scenario" is the most intellectually honest
passage in the corpus so far. He works SIRI collapsing from $4.89 to $1 — the CSP
holder is down ~76%, and then he explicitly compares it to simply having bought
the shares outright, which would have been ~79%. His conclusion: the CSP does
**not** save you in a crash; it only softens it by the premium collected.

No other source in the corpus shows a losing scenario with real numbers and
declines to spin it.

---

## Flags before any of this trains an agent

- **"Guaranteed money" is the wrong frame.** He says repeatedly that you cannot
  lose money selling the call option. Narrowly true — the premium is yours — but
  a covered call is one position, not two, and the position absolutely can lose.
  He does caveat that you can lose on the stock, but the phrasing invites the
  error. Do not encode "premium is guaranteed" in any form.
- **The annualized returns are seriously misleading.** 4.6% in two months quoted
  as 28% annualized; 7.8% → 46.8%; 11% → 66%; SIRI's 7.1% in a month → 85%.
  Every one of these annualizes a **best-case single outcome** as if it repeated
  twelve times. It ignores the assignment scenarios, the periods where no decent
  premium exists (which he himself mentions), and the fat left tail. Same
  distortion as Video 01's POP framing and Video 02's outlier trade, dressed in
  CPA arithmetic.
- **The SIRI example inadvertently proves the point it skips.** A 32¢ premium on
  a $4.50 strike over 22 days is an enormous yield — which means enormous implied
  volatility, which means the market was pricing serious downside risk in that
  specific stock. He presents the rich premium as opportunity without noting that
  premium size *is* the market's risk estimate. **High premium is not free money;
  it is a priced warning.** This is the single most important correction the
  corpus needs.
- **No expectancy, win rate, or sample size**, consistent with every other source.
- 2023 vintage; Robinhood UI and prices are dated but mechanics are current.

**Candidate rules to carry forward for testing:**
assignment-willingness gate (never sell a put on a stock you won't own, never
call away shares you won't sell); limit orders only; no-trade periods are
acceptable; premium-yield-vs-IV sanity check (rich premium ⇒ investigate why);
roll cadence and reinvestment risk on premium streams.
