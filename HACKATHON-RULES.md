# Alpaca AI Trading Agents Hackathon — binding constraints

**Source:** https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon
(retrieved 2026-08-29) · Run by lablab.ai × Alpaca · Prize pool $6,000–6,300
*(the page states both figures; prize terms say AlpacaDB pays $6,000)*

**These are the guidelines DELTAX is built to satisfy. Everything in
`research/` is subordinate to this file.**

---

## ⏱ Timeline — this is the binding constraint

| | |
|---|---|
| Kick-off | Fri **28 Aug 2026**, 11:00 AM EDT |
| **Submission deadline** | Fri **4 Sept 2026**, 11:00 AM EDT |
| Today | **29 Aug 2026** (Saturday — market closed) |

**Trading days available: Mon 31 Aug, Tue 1 Sep, Wed 2 Sep, Thu 3 Sep, plus a
partial Fri 4 Sep before the 11:00 AM cut-off.** Roughly **4.5 sessions.**

---

## ✅ Account status — compliant, verified 2026-08-29

| Requirement | Our account | Status |
|---|---|---|
| Brand-new account dedicated to the hackathon | `PA3ID1B9L6BP`, created **2026-08-29 05:23 UTC** (after the 28 Aug kickoff) | ✅ |
| Not existing or reused | **0 orders ever placed, 0 positions** | ✅ |
| Starting balance **$100,000** | $100,000 cash / $100,000 portfolio value | ✅ |
| Options capability | Level 3 approved | ✅ |

⚠️ **Protect this.** Any pre-hackathon or unrelated trading in this account
compromises the "fresh account" requirement. Use a different paper account for
throwaway experiments. Do not reset or recreate it — the creation timestamp is
the eligibility evidence.

---

## 🔴 Core requirements — mandatory, non-negotiable

| # | Requirement | Status |
|---|---|---|
| 1 | **Autonomous AI trading agent** using Alpaca's Trading API | ✅ live 31 Aug — screens, gates, opens, closes unattended |
| 2 | **Must use Alpaca's MCP server OR CLI** | ✅ CLI, every market-data and execution call |
| 3 | **All strategies must incorporate options trading** | ✅ iron condors only — no equity or crypto leg trades |
| 4 | Developed and tested in the **paper trading environment** | ✅ |
| 5 | Submission must include the **paper account ID** | ✅ have it |

---

## 📦 Deliverables checklist

- [ ] Project title, short description, long description, tech/category tags
- [x] **Cover image** — ✅ done (llama/chrome logo, "CODE · RISK · EXECUTE")
- [~] **Video presentation** — in progress (Pautax, separate session)
- [x] **Slide presentation** — ✅ live at /slides.html + PDF in repo (v3 rewrite pending)
- [x] **Public GitHub repository** — ✅ public, MIT licensed
- [x] Demo application platform + **application URL** — ✅ https://pautax007.github.io/DELTAX/ (live board, refreshes every 3 min)
- [x] **Alpaca paper trading account ID** → `PA3ID1B9L6BP`
- [ ] **One-page write-up: AI logic, risk gates, Alpaca infrastructure**

**Brand palette** (from the cover image, for slides and the demo page):
deep navy `#0A1428` · chrome `#C8D4E0` · electric blue `#1E90FF` · white text.
- [ ] Optional: up to **5 social posts** on X/LinkedIn tagging @lablabai and
      @AlpacaHQ (separate $500 × 2 prize)

---

## ⚖️ Judging criteria

1. **P&L Performance** — trading performance in the paper environment
2. **Technology Implementation** — effective use of Trading API, MCP server, CLI
3. **Creativity & Originality** — of concept, strategy, and agent behaviour
4. **Presentation & Execution** — clarity of the demo and the reasoning
5. **Social Engagement** — quality and reach of build-in-public posts

**P&L is one of five.** Four of five reward engineering and communication, which
are fully controllable. This matters — see red flag 3.

---

## 🚩 RED FLAGS

### 1. Research has drifted away from the mandatory requirement
**Options trading is compulsory.** Videos 01–06 covered options. Videos 07–10
covered stocks (and were mostly forex/crypto in practice), and a crypto module is
planned. **None of that satisfies core requirement 3 on its own.**

**Correction:** the stocks work isn't wasted — the expectancy framework (S0), the
sizing rules (S1/S2) and the selection discipline (S7) are exactly the risk-gate
layer the write-up must describe, and they apply to options positions unchanged.
But **the instrument the agent trades must be options.** Recommend pausing new
video intake and spending the remaining days building. A crypto module cannot
earn points in this competition.

### 2. Two hard technical requirements are unstarted
No agent exists, and neither the MCP server nor the CLI is wired up.
**Correction:** the Alpaca CLI is the cheaper path — it emits structured JSON and
is built for cron/agent loops, which fits an autonomous agent better than MCP.
This is the first build task.

### 3. P&L over 4.5 sessions is noise, and our own method says so
Our entire research method concludes that **win rate over a short window proves
nothing** and rules must be validated on expectancy across a full sample. The
hackathon judges P&L over **4.5 trading days**. These are in direct conflict.

**Correction — and this is the strategic call:** do not try to win on P&L by
taking concentrated directional risk. A blow-up is both a likely outcome and a
visible failure across the other four criteria. Instead make the *discipline*
the product: an agent that sizes from defined risk, refuses trades that don't
clear its gates, and can explain why it abstained. Document the expectancy gate
honestly in the write-up, including that the window is too short to validate an
edge. **That is a differentiator, not an excuse** — judges scoring Creativity and
Presentation will recognise a team that understands its own statistics.

### 4. Competitors are already occupying that exact position
Submissions visible on the page include agents built around out-of-sample
validation, risk gates, and refusal-to-trade behaviour — the same thesis our
research points to. **Correction:** assume the "disciplined agent" framing is
taken and differentiate on execution — the five-criteria scanner (S7) as a
concrete, data-driven options-candidate filter, and a transparent expectancy
ledger, are more specific than "we have risk gates."

### 5. Unconfirmed logistics
- Team registered on lablab.ai **and** Discord? Teams are 1–6 people.
- All members 18+, not in sanctioned countries, no Alpaca affiliation.
- Prizes pay to **one individual**, not a team — designate the payee in advance.
- W-9 (US) or W-8BEN (non-US) + photo ID + bank details needed before payment.
- Repository must be original and MIT-compliant.

### 6. Research provenance must stay clean
The corpus is distilled notes, not copied transcripts, so the repo is clear of
third-party content. **Keep it that way** — do not commit any raw caption files
or vendor PDFs to the public GitHub repo.

---

## Standing instruction

Before adding scope, ask whether it advances one of the five judging criteria
before 4 Sept, 11:00 AM EDT. If not, it waits until after the deadline.
