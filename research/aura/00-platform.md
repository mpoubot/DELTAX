# AURA — Matin's platform and methodology

**Source:** Matin's research pack, received 2026-08-29 — six dossiers (stocks /
crypto / options, evidence + review-brief pairs), platform overview (12pp),
v0.5.3 folder & script analysis, system-map deck. **Source M** in the ledger.

AURA is an AI-assisted quantitative research and execution platform:
*hypothesis → validation → controlled execution*. Not a trading bot — a research
platform with a deterministic execution boundary.

---

## The control plane (v0.5.3, built)

```
.12 Market State → .13 Signal Decision → .14 Risk Gate → .15 Position State
                → .16 Paper Execution → .17 Ledger
Controls: .18 Kill Switch · .19 Supervisor · .20 Dashboard (read-only)
```

Non-negotiables, quoted from the pack:

- **AI may research, analyze and propose — never authorize an order.**
- **SIGNAL → RISK PASS → POSITION → ORDER. Never SIGNAL → ORDER.**
- .13 consumes only .12's canonical state (with provenance hash) — downstream
  never reconstructs indicators.
- .14 is **fail-closed**: uncertainty blocks.
- Ledger is append-only; kill switch persists a safe state; supervisor and
  dashboard have zero execution authority.
- Current execution barriers: `ORDERS_ALLOWED=FALSE`, `PAPER_EXECUTION=FALSE`,
  `LIVE_EXECUTION=FALSE` — **nothing trades yet by design.**

Roadmap: v0.5.3.20 dashboard (current) → .21 end-to-end dry run → v0.5.4
independent validation → **v0.5.5 paper competition agent**.

## The research methodology — AURA's real contribution

1. Generate hypothesis → 2. formalize deterministic rule → 3. backtest →
4. stress costs/slippage/regimes → 5. walk-forward → 6. **permutation/noise
controls** → 7. holdout/prospective observation → 8. freeze survivor.

- TRAIN selects; TEST is unseen. **Do not tune after holdout.**
- **Pre-committed acceptance bar: OOS Profit Factor > 1.10 AND >50% of
  walk-forward folds positive.** Declared before looking.
- Failed branches are stopped, not tuned until they pass.
- Diagnostics are evidence for hypotheses, never automatic deployment rules.
- Walk-forward concept: 180d train → 60d test → 60d step.
- Script inventory: backtester, broad backtest, param sweep, walk-forward,
  permutation test, exit sensitivity, long/short-only decomposition, trade
  diagnostics, regime test, prospective holdout.

**Adopted for DELTAX** (all buckets): the pre-committed bar and no-post-holdout
tuning slot directly into our validation ladder (S3) and pre-registration plan —
they give the "backtest" rung numeric teeth we hadn't specified.

## Three-way team convergence

| Principle | DELTAX (ours) | Alyrise (Elsa) | AURA (Matin) |
|---|---|---|---|
| AI proposes, deterministic code disposes | `gates.py`, no model-overridable path | AI must not change thresholds / bypass risk / authorize | "AI never becomes an execution authority" |
| Auditable record before any order | `DecisionRecord` per evaluation | intent before every order | .17 append-only ledger, state hashes |
| Fail-closed | refusal is first-class | execution-safety checklist | .14 blocks on uncertainty |
| Kill switch | kill-switch thresholds from backtest (S5) | shared kill switch | .18 halt/recovery, safe state persists |

Three people, three codebases, no coordination — same boundary. This is the
spine of the hackathon write-up.

## Status per asset class

| | Status | Hackathon relevance |
|---|---|---|
| Crypto (MEXC perps) | Core .12–.20 built; frozen candidate; execution gaps listed | ❌ Out of scope — see crypto/golden-rules.md |
| Stocks (Equity Lab v0.4.8) | Created, paper-only, models **not validated** | Research track alongside Alyrise |
| Options (v0.6.0) | **NOT BUILT, NOT VALIDATED** — criteria + protocol only | ✅ Our engine is the de-facto implementation |

## Boundaries (his words, kept verbatim as rules)

Equity Lab ≠ Crypto Lab · Research ≠ execution · Signal ≠ order ·
AI proposal ≠ execution authorization · Holdout evidence ≠ permission to retune.
