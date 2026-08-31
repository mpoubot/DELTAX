# Deck Changelog

Every published version is kept. `docs/slides.html` is always the current one;
numbered copies in this folder are frozen and never edited, so any claim in an
older deck can be traced to what we believed when we made it.

| Version | Date | What changed | Why |
|---|---|---|---|
| **v1** | 30 Aug | First deck: 52 rules, 312 tests, 2 build days, 2-card tracker | Team review before going live |
| **v2** | 31 Aug (pre-live) | 56 rules, 366 tests, 3-card tracker with Day 03, autonomous execution, exits built | Agent went live; counts and story updated |
| **v3** | *pending* | See "planned for v3" below | Competitor review + Monday's findings |

---

## Planned for v3 — before Friday

Driven by reading eight competitor decks on 31 Aug and by what Monday's live
session actually taught us.

1. **Lead with the corpus, not the strategy.** Our strategies are comparable to
   Pin Desk's and Vetoed's. **39 dated rules, each traceable to the test that
   produced it, plus a live public board** is the thing nobody else showed. It
   belongs on slide 2, not slide 7.

2. **Name the 15-minute options-data delay.** Pin Desk builds their whole thesis
   on being immune to it via open interest. A deck that does not mention the
   constraint looks unaware of it.

3. **Tell the E34 story prominently.** Vetoed's strongest slide is "I caught my
   own agent lying." Ours is bigger: our backtest validated a credit the market
   never paid — $1.15 assumed against $0.54 real — found *during live trading*
   and rebuilt on measured prices. Currently buried.

4. **Add dealer gamma.** Built 31 Aug, advisory only because it cannot be
   backtested from this API. Saying so is itself the point: the mechanism is
   compelling and we still would not let it gate a trade.

5. **Correct the performance claims.** v2 quotes the three-week backtest at
   +8.39% and the distribution at +2.14% median. **Both were computed at the
   assumed credit** and do not survive E34. They must be restated at real prices
   or removed.

6. **Show the real result.** One live condor, −$429 at the time of writing, and
   the expiry-window error that caused it. See `DECISIONS.md` D-07.

---

## Rules for this folder

- **Never edit a numbered version.** Frozen means frozen.
- Snapshot before any rewrite, not after.
- A version is only cut when the deck is *published*, not on every save.
- Performance numbers must state the pricing assumption behind them.
