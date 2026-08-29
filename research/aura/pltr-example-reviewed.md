# PLTR Options Example — DELTAX Review

**Reviews:** `Palantir exemple.pdf` (Matin, uploaded 2026-08-29)
**Method:** every quoted price re-pulled from Alpaca; every proposal run through
`deltax/gates.py` at competition settings (2% / 10% caps).
**Verified:** 2026-08-29 · chain data as of the 2026-08-28 close.

> The original document is source material and is unchanged. This is the
> reviewed version, per the repo's rule that a trigger only nominates and the
> gates decide.

---

## Verdict

| Proposal | Gate result | Binding reason |
|---|---|---|
| Sep 4 · $185/$190 call debit | **REFUSE** | 4 DTE (outside 7–21 band); R:R 1.13 |
| Sep 11 · $185/$195 call debit — *at the document's prices* | PASS | R:R 2.64 |
| Sep 11 · $185/$195 call debit — **at real prices** | **REFUSE** | R:R 1.35 vs 2.0 floor |
| Covered call on 1,000 shares | **REFUSE** | Position cost ~$186,290 vs $100,000 account |
| *Any* PLTR put credit spread, Sep 18 | **REFUSE** | Credit 18–29% of width vs 30% floor |

**Net: PLTR is not a Monday candidate for either book.** That is a legitimate
output, not a failure — it is the gates doing their job on a name that looks
attractive in prose.

---

## 1. One price is wrong, and it decides the trade

| Leg | Document | Alpaca (live) | Delta |
|---|---|---|---|
| Sep 11 $185 call — **buy** | ask $7.00 | ask **$7.02** | ✅ accurate |
| Sep 11 $195 call — **sell** | bid $4.25 | bid **$2.76** | ❌ **overstated by $1.49** |

The buy leg is right; the sell leg is not. Consequences:

|  | Document | Actual |
|---|---|---|
| Net debit | $2.75 | **$4.26** |
| Max profit | $7.25 | **$5.74** |
| Reward : risk | 2.64 : 1 | **1.35 : 1** |
| Gate | would pass | **REFUSED** |

A $1.49 quote error is the entire difference between a compliant trade and a
rejected one. Even priced at mid-market the spread reaches only 1.51:1 — still
short of the 2:1 floor. **This is the case for pulling every quote from the
execution venue rather than a data website.**

## 2. The skew premise doesn't survive measurement

The document infers "massive downside skew" and "expensive" puts from **open
interest** at the $100 and $130 strikes. Open interest is not skew. Skew is the
implied-volatility differential across strikes; large OI far out of the money is
just as consistent with legacy positioning or cheap tail hedges, and says
nothing about whether premium is currently rich.

Measured directly — credit as a share of width, Sep 18 expiry, live quotes:

| Put spread | Credit | % of width | Gate |
|---|---|---|---|
| $180 / $175 (w 5) | $1.45 | 29% | REFUSE |
| $180 / $170 (w 10) | $2.65 | 26% | REFUSE |
| $175 / $165 (w 10) | $1.85 | 18% | REFUSE |

Every liquid strike sits below the 30% floor. **PLTR's downside premium is not
unusually rich** — the opposite of the document's central claim, and the reason
no income-book trade exists here.

## 3. The covered call is not available to this account

The recommended structure requires owning 1,000 PLTR shares:

- Cost at $186.29 ≈ **$186,290**
- Account: **$100,000** cash · $200,000 RegT buying power
- It would consume ~93% of buying power, leaving nothing for either book
- Downside on the share leg is undefined by our standard; a routine 10% move is
  ~$18,600 against a **$2,000** per-position cap — roughly **9× over**

Rule R2 (own the collateral) is satisfied in principle, but E7 and the position
caps are not. The structure is sound; the account is the wrong size for it.

## 4. The competition premise is incorrect

The recommendation rests on this being *"a Sharpe-ratio-optimized AI
competition, where deep or volatile drawdowns severely penalize your score."*

The published criteria are **P&L Performance · Technology Implementation ·
Creativity & Originality · Presentation & Execution · Social Engagement**
(`HACKATHON-RULES.md`). There is no Sharpe ratio, no volatility term, and no
drawdown penalty anywhere in the judging.

The conclusion may still be defensible on other grounds — we cap drawdown
ourselves because a busted account scores badly on *everything* — but it cannot
be justified by a scoring rule that does not exist.

## 5. Smaller corrections

- **"+263% return on options capital"** is the maximum payoff at expiry with
  PLTR at or above $195, not an expected return. Report expectancy, not the
  best cell in the payoff table (S0).
- **"Sep 4"** is 4 DTE from Monday — inside the zone R5 exists to keep us out
  of, independent of pricing.
- The source PDF is a chat-export: pages 3–7 repeat pages 3–4. Worth
  regenerating before it goes anywhere near the submission.

---

## What we take forward

**Adopted.** The document's *structural* instinct is right and matches the
playbook already committed: defined-risk verticals, direction chosen by regime,
credit structures when premium is rich and debit structures when it isn't. The
two-branch decision tree on its page 2 is the same shape as our two-book design.

**Rejected for Monday.** PLTR itself. Both books refuse it on measured data.

**Kept as method.** This review is the template for evaluating any nominated
name: pull quotes from Alpaca, run `evaluate()`, publish the gate output. It
took minutes and caught a live pricing error, an unsupported volatility claim,
an unaffordable position, and a false premise about the competition — none of
which were visible in the prose.
