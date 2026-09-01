# DELTAX — team operating guide

**Team of 3** · 🇺🇸 United States · 🇱🇻 Latvia · 🇩🇰 Denmark
Hackathon deadline: **Fri 4 Sept 2026, 11:00 AM EDT**

---

## 🔴 Do this first: the prize split

**This is the item that decides whether all three of you actually get paid, and it
has a deadline that is effectively "before you win."**

The hackathon rules state that prizes are paid **to individuals, not to teams or
companies**. If a team wins, you either designate one member to receive the full
amount, **or confirm a split with Alpaca Finance in advance.**

### Why "one person takes it and splits it later" is the wrong choice

If the US member is sole payee for, say, a $2,500 first prize:

- Any US winner receiving more than $600 gets a **1099-MISC** — issued for the
  **full** amount, not their third.
- That member is taxed in the US on money that was always destined for Latvia and
  Denmark, with no straightforward way to deduct the onward payments.
- They then have to wire funds internationally out of post-tax money, absorbing
  wire fees on top.

### The fix

**Contact Alpaca Finance now and request a three-way split**, before results are
announced. Each member then files their own paperwork for their own share:

| Member | Form | Notes |
|---|---|---|
| 🇺🇸 US | **W-9** | 1099-MISC issued on their share only |
| 🇱🇻 Latvia | **W-8BEN** | Treaty claim goes on this form |
| 🇩🇰 Denmark | **W-8BEN** | Treaty claim goes on this form |

The rules state that non-US payments are **generally subject to 30% US
withholding unless a valid treaty claim applies on the W-8BEN**. Latvia and
Denmark each have a US income tax treaty, but whether prize/contest income
qualifies — and under which article — is specific to each treaty and to each
person's circumstances. **Neither I nor anyone on the team should guess at this.**
Each non-US member should confirm their treaty position with a local tax
professional, and the team should confirm the split mechanics directly with
Alpaca Finance.

### Everyone should have ready, now

- Government photo ID
- Bank details capable of receiving an international USD payment (IBAN/SWIFT)
- Their completed W-9 or W-8BEN

⏳ Documentation must be completed **within 90 days of winner notification or the
prize may be forfeited.** Payment lands within 90 days of the event end, after
sanctions screening. Do not leave this to the week you win.

---

## Sharing the work

### Repository

The hackathon requires a **public GitHub repository** at submission. Recommended
sequence:

1. **Private repo now** — the whole team collaborates without publishing the
   strategy to competitors mid-competition.
2. **Flip to public before the deadline** — satisfies the requirement, and the
   commit history then shows the pre-registration timestamp (see `STRATEGY.md` §3),
   which is a genuine credibility asset.

Everyone gets push access. Work on branches, merge to `main`.

### ⚠️ Credentials: never shared, never committed

`.env.alpaca` is gitignored and **must stay that way**. Verified clean: the secret
appears nowhere in git history.

**Each teammate uses their own Alpaca paper account for development.** The rules
explicitly allow this — *"Use any paper account you like during development."*
Copy `.env.alpaca.example` to `.env.alpaca` and fill in your own keys.

**The competition account `PA397N6FXXIE` is locked.** Reasons this is not
negotiable:

- The rules require a **brand-new, dedicated** account. Ours was created
  2026-08-29 05:23 UTC with zero prior orders — that clean history *is* the
  eligibility evidence.
- P&L is judged from this account. Three people trading it experimentally
  corrupts the record with no way to undo it.

Only one designated member runs the agent against it, and only for the real
competition run. Everything else happens on personal dev accounts.

### Setup for each teammate

```bash
git clone <repo-url> && cd DELTAX
brew install alpacahq/tap/cli        # macOS; see repo for Linux/Windows
cp .env.alpaca.example .env.alpaca   # then add YOUR OWN paper keys
chmod 600 .env.alpaca
set -a; . ./.env.alpaca; set +a
alpaca doctor                        # should report profile: paper, all checks passed
```

---

## Time zones — this spread is an advantage

| | UTC offset | Market open 09:30 ET | Market close 16:00 ET | **Deadline** |
|---|---|---|---|---|
| 🇺🇸 US (Eastern) | −4 | 09:30 | 16:00 | **Fri 11:00** |
| 🇩🇰 Denmark | +2 | 15:30 | 22:00 | **Fri 17:00** |
| 🇱🇻 Latvia | +3 | 16:30 | 23:00 | **Fri 18:00** |

*(Adjust the US row if the US member is not on Eastern time.)*

**Both European members are awake for the entire US session** — it lands in their
afternoon and evening. That covers the full trading day without anyone keeping
unnatural hours, which is unusually lucky for a distributed team.

Latvia is 1 hour ahead of Denmark, so those two overlap almost completely.

**Suggested split**, playing to the overlap:

- **European morning / US night** — build and test: risk gates, backtest harness,
  decision logger. No market dependency, so time zone doesn't matter.
- **US session (Euro afternoon/evening)** — all three overlap. Live monitoring,
  decisions, review.
- **US evening** — daily wrap: commit, log, one build-in-public post.

Because the deadline is 11:00 AM EDT on Friday, the **final submission happens
during European evening**. Don't leave assembly to Friday morning US time — the
European members would be racing the clock at 17:00–18:00 local.

---

## Registration checklist

- [ ] All three registered on **lablab.ai** and joined the **lablab.ai Discord**
- [ ] Team created on the platform with all three members listed (teams are 1–6)
- [ ] All members 18+, not Alpaca employees/contractors or immediate family, not
      in sanctioned countries
- [ ] **Prize split confirmed with Alpaca Finance** ⬅ the critical one
- [ ] W-9 / W-8BEN forms prepared per member
- [x] Repo access: **IlzeTheGreat** (Elsa) accepted · **mpoubot** (Matin) invite pending — he must accept the email

---

## Division of the deliverables

Each of these is a required submission item. Assign an owner now.

| Deliverable | Owner |
|---|---|
| Public GitHub repository | |
| Agent implementation (risk gates, logger, execution) | |
| Backtest + pre-registration | |
| One-page write-up: AI logic, risk gates, Alpaca infrastructure | |
| Video presentation | |
| Slide presentation | |
| Cover image | |
| Demo application URL | |
| Social posts — up to 5, tagging @lablabai + @AlpacaHQ | |

The social posts are a **separate $500 × 2 prize** and reward consistency over
polish. Three people in three countries posting their own perspective on the build
is more visible than one person posting three times — and it costs almost nothing
alongside the work you're already doing.

---

## Team repositories

| Repo | Owner | Role |
|---|---|---|
| `pautax007/DELTAX` | Pautax | **Submission repo.** Research corpus, gates, docs. Private now → public before the Fri 11:00 deadline |
| `mpoubot/CAURAv0.5.2` | Matin | His AURA engine. Cloned at `../CAURAv0.5.2`. **Empty as of 2026-08-29** — pull when he pushes |
| `mpoubot/aura-autonomous-trading-agent` | Matin | Named as a hackathon agent repo. Cloned at `../aura-autonomous-trading-agent`. **README-only as of 2026-08-29** |

⚠️ **Open team decision — one submission repo, currently two candidates.**
The second repo's README says it is "for the Alpaca AI Trading Agents
Hackathon", which overlaps DELTAX's role. The hackathon accepts a single
public GitHub link. Decide together before Monday: either (a) DELTAX is the
submission and Matin's repos feed it via merges with attribution, or (b) the
team consolidates into one of his. Fact for the decision: DELTAX currently
holds the research corpus, the tested gate module and the timestamped commit
history the pre-registration strategy depends on; both of Matin's repos are
empty shells today. Whatever is chosen, everything merges into ONE repo well
before Friday — a split submission fails on Presentation.

**Policy — one submission repo.** The hackathon takes a single public GitHub
link, and DELTAX's commit history carries our pre-registration timestamps, so
DELTAX is the submission. CAURA stays Matin's dev repo; anything from it that
the submission needs gets merged into DELTAX **with attribution and a
license check first** — submissions must be original and MIT-compliant, so
CAURA needs a LICENSE file before any of its code crosses over. Never add it
as a submodule: a private-repo pointer breaks the moment DELTAX goes public.
