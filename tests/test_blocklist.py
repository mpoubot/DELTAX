"""E117: the earnings blocklist had zero tests. These pin the runner's only
entry point, check(), and the manual overlay that clears a name without SEC.

Every assertion here is a way a single name could be traded through an
earnings print, or refused forever, without anyone being told.
"""
import sys, os, unittest
from datetime import date, datetime, timezone, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from deltax import blocklist as B

H = date(2026, 9, 30)          # horizon the file is built to
TRADE = date(2026, 9, 18)      # expiry the runner checks


def _sec_file(expiry=date(2026, 9, 4), clear=("SPY", "DIA"), blocked=None):
    return {"built_at": datetime.now(timezone.utc).isoformat(),
            "expiry": str(expiry), "clear": sorted(clear),
            "blocked": dict(blocked or {}), "errors": {}, "n_checked": 3}


class CheckHorizon(unittest.TestCase):
    def test_file_built_short_of_trade_expiry_refuses_single_names(self):
        # The pre-existing defect: built to CONTEST_CLOSE, checked to today+MAX_DTE.
        data = _sec_file(expiry=date(2026, 9, 4), clear=("SPY", "UNH"))
        ok, why = B.check("UNH", TRADE, data)
        self.assertFalse(ok)
        self.assertIn("only covers to 2026-09-04", why)

    def test_etf_never_needs_the_file(self):
        self.assertTrue(B.check("SPY", TRADE, None)[0])

    def test_missing_or_stale_file_refuses(self):
        self.assertFalse(B.check("UNH", TRADE, None)[0])
        old = _sec_file(expiry=H, clear=("UNH",))
        old["built_at"] = (datetime.now(timezone.utc) - timedelta(hours=21)).isoformat()
        self.assertFalse(B.check("UNH", TRADE, old)[0])


class MergeManual(unittest.TestCase):
    def test_verified_entry_clears_name_and_check_passes(self):
        base = _sec_file(blocked={"UNH": "lookup failed - RuntimeError"})
        out = B.merge_manual(base, [{"symbol": "UNH", "next_earnings": "2026-10-09",
                                     "source": "company IR"}], H)
        self.assertIn("UNH", out["clear"])
        self.assertNotIn("UNH", out["blocked"])
        self.assertEqual(out["manual"]["UNH"]["next_earnings"], "2026-10-09")
        ok, why = B.check("UNH", TRADE, out)
        self.assertTrue(ok, why)

    def test_earnings_on_or_before_horizon_is_blocked(self):
        out = B.merge_manual(_sec_file(), [{"symbol": "C", "next_earnings": "2026-09-30",
                                            "source": "x"}], H)
        self.assertNotIn("C", out["clear"])
        self.assertIn("on or before", out["blocked"]["C"])
        self.assertFalse(B.check("C", TRADE, out)[0])

    def test_missing_source_or_bad_date_is_blocked_not_dropped(self):
        out = B.merge_manual(_sec_file(), [
            {"symbol": "QCOM", "next_earnings": "2026-11-11", "source": ""},
            {"symbol": "MA", "next_earnings": "soon", "source": "x"}], H)
        for s in ("QCOM", "MA"):
            self.assertIn(s, out["blocked"], s)
            self.assertNotIn(s, out["clear"])
            self.assertFalse(B.check(s, TRADE, out)[0])

    def test_widening_horizon_demotes_sec_cleared_single_names(self):
        # AAPL was cleared by SEC only to Sep 4; the overlay widens to Sep 30.
        base = _sec_file(expiry=date(2026, 9, 4), clear=("SPY", "AAPL"))
        out = B.merge_manual(base, [], H)
        self.assertIn("SPY", out["clear"])                 # ETF untouched
        self.assertNotIn("AAPL", out["clear"])
        self.assertIn("not checked to 2026-09-30", out["blocked"]["AAPL"])

    def test_etf_entry_is_ignored_and_empty_input_is_safe(self):
        out = B.merge_manual(None, [{"symbol": "SPY", "next_earnings": "2026-01-01",
                                     "source": "x"}, None], H)
        self.assertEqual(out["clear"], [])
        self.assertEqual(out["blocked"], {})
        self.assertEqual(out["expiry"], "2026-09-30")


if __name__ == "__main__":
    unittest.main()
