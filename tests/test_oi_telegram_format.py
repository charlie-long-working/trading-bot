"""Regression: OI alert text must be HTML-safe (K rule text contains bare '<'; Telegram 400'd before 9da9903)."""

import re
import unittest

from botdown.oi_live_signal import SCENARIO_WHY, OiAlert, format_oi_telegram

ALLOWED = re.compile(r"<(?!/?(b|i|code)>)")


def _alert(**kw):
    base = dict(symbol="BTCUSDT", interval="1h", side="long", bar_time="2026-11-15 05:00", close=70000.0,
                scenarios=[{"scenario": "K_oi_usdtd_confluence", "side": "long", "desc": "OI <+> USDT.D"}],
                tp_pct=0.015, sl_pct=0.006, entry=70000.0, stop=None, target=None,
                features={"usdt_d": 7.5, "regime_ema": "bull<x>"}, liq=None, signal_at="now")
    base.update(kw)
    return OiAlert(**base)


class OiFormatTests(unittest.TestCase):
    def test_rule_text_has_raw_lt(self):
        self.assertIn("<", SCENARIO_WHY["K_oi_usdtd_confluence"])  # precondition of the regression

    def test_only_whitelisted_tags(self):
        msg = format_oi_telegram(_alert())
        self.assertIsNone(ALLOWED.search(msg), msg)
        self.assertIn("Δ3d&lt;-0.2", msg)
        self.assertIn("bull&lt;x&gt;", msg)

    def test_none_side_returns_none(self):
        self.assertIsNone(format_oi_telegram(_alert(side="none")))

    def test_short_levels(self):
        msg = format_oi_telegram(_alert(side="short"))
        self.assertIn("70,420.00", msg)  # SL = entry * (1 + 0.6%)
        self.assertIn("68,950.00", msg)  # TP = entry * (1 - 1.5%)


if __name__ == "__main__":
    unittest.main()
