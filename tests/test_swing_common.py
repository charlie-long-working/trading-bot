"""botdown.swing_common: weekly trend, resample, Signal format (HTML-safe), split, dedupe store, deliver."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from botdown import swing_common as S
from tests.helpers import trend_ohlc


class WeeklyTrendTests(unittest.TestCase):
    def test_too_few_bars_returns_none(self):
        d = trend_ohlc(40)
        self.assertIsNone(S.weekly_trend(d.high, d.low, d.close))

    def test_uptrend_is_bullish(self):
        d = trend_ohlc(120, step=0.01)
        t = S.weekly_trend(d.high, d.low, d.close)
        self.assertEqual(t["bias"], "Tăng")
        self.assertGreaterEqual(t["score"], 2)
        self.assertTrue(t["ema20_gt_ema50"])
        self.assertEqual(t["cloud"], "trên mây")

    def test_downtrend_is_bearish(self):
        d = trend_ohlc(120, step=-0.01)
        t = S.weekly_trend(d.high, d.low, d.close)
        self.assertEqual(t["bias"], "Giảm")
        self.assertLessEqual(t["score"], -2)
        self.assertEqual(t["cloud"], "dưới mây")

    def test_chg_4w_matches_closes(self):
        d = trend_ohlc(80)
        t = S.weekly_trend(d.high, d.low, d.close)
        c = d.close.to_numpy()
        self.assertAlmostEqual(t["chg_4w_pct"], round((c[-1] / c[-5] - 1) * 100, 1))

    def test_cloud_is_shifted_26_bars(self):
        d = trend_ohlc(100)
        top, bot = S.ichimoku_cloud(d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy())
        self.assertTrue(np.isnan(top[:26]).all())
        self.assertFalse(np.isnan(top[-1]))
        self.assertTrue((top[~np.isnan(top)] >= bot[~np.isnan(bot)]).all())


class ResampleTests(unittest.TestCase):
    def test_weekly_ohlc_aggregation(self):
        d = trend_ohlc(14, t0="2026-11-02")  # Mon 2 Nov → Sun 15 Nov = 2 full Mon–Sun weeks
        w = S.resample_ohlc(d, "W-SUN")
        self.assertEqual(len(w), 2)
        first = d.iloc[:7]
        self.assertAlmostEqual(w["open"].iloc[0], first["open"].iloc[0])
        self.assertAlmostEqual(w["high"].iloc[0], first["high"].max())
        self.assertAlmostEqual(w["low"].iloc[0], first["low"].min())
        self.assertAlmostEqual(w["close"].iloc[0], first["close"].iloc[-1])
        self.assertEqual(str(w["week_end"].iloc[0].date()), "2026-11-08")


def _sig(**kw):
    base = dict(asset="crypto", symbol="BTCUSDT", tf="1D", side="long", strategy="K_test",
                rule="z<-1 & Δ3d<-0.2", bar_time="2026-11-14", entry=100.0, stop=97.0, target=108.0)
    base.update(kw)
    return S.Signal(**base)


class SignalFormatTests(unittest.TestCase):
    def test_key_is_closed_bar_scoped(self):
        self.assertEqual(_sig().key, "BTCUSDT|1D|2026-11-14|K_test|long")

    def test_html_is_escaped(self):
        msg = S.format_signal(_sig(notes=["a<b & c>d"]))
        self.assertNotIn("z<-1", msg)
        self.assertIn("z&lt;-1", msg)
        self.assertIn("a&lt;b &amp; c&gt;d", msg)

    def test_levels_and_rr(self):
        msg = S.format_signal(_sig())
        self.assertIn("(-3.0%)", msg)
        self.assertIn("(+8.0%)", msg)
        self.assertIn("R:R 2.67", msg)

    def test_short_tag_and_weekly_line(self):
        t = {"bias": "Giảm", "score": -3, "ema20_gt_ema50": False, "cloud": "dưới mây",
             "macd_hist": -1.0, "macd_rising": False, "rsi": 40.0, "chg_4w_pct": -5.0}
        msg = S.format_signal(_sig(side="short", stop=103.0, target=92.0), t)
        self.assertIn("🔴 SHORT", msg)
        self.assertIn("Xu hướng tuần: Giảm (-3)", msg)

    def test_weekly_counts(self):
        up = {"bias": "Tăng", "score": 3, "ema20_gt_ema50": True, "cloud": None, "macd_hist": 1.0,
              "macd_rising": True, "rsi": 60.0, "chg_4w_pct": 4.0}
        msg = S.format_weekly("W", [("A", up, None), ("B", None, None)])
        self.assertIn("Tăng 1 · Giảm 0 · Trung tính/thiếu dữ liệu 1", msg)


class SplitAndStoreTests(unittest.TestCase):
    def test_split_respects_limit(self):
        blocks = ["x" * 1500] * 5
        msgs = S.split_messages(blocks)
        self.assertGreater(len(msgs), 1)
        self.assertTrue(all(len(m) <= S.TG_LIMIT for m in msgs))
        self.assertEqual(sum(m.count("x") for m in msgs), 7500)

    def test_oversized_single_block_split_by_lines(self):
        block = "\n".join(f"line {i} " + "y" * 200 for i in range(60))  # ~12.5k chars, one block
        msgs = S.split_messages([block])
        self.assertGreater(len(msgs), 1)
        self.assertTrue(all(len(m) <= S.TG_LIMIT for m in msgs))
        self.assertEqual(sum(m.count("line ") for m in msgs), 60)  # no line lost or cut

    def test_store_roundtrip_and_trim(self):
        p = Path(tempfile.mkdtemp()) / "sent.json"
        st = S.SentStore(p, max_keys=3)
        for k in "abcde":
            st.add(k)
        st.add("a")  # duplicate ignored
        st.save()
        self.assertEqual(json.loads(p.read_text()), ["c", "d", "e"])
        st2 = S.SentStore(p)
        self.assertIn("e", st2)
        self.assertNotIn("a", st2)

    def test_corrupt_store_starts_empty(self):
        p = Path(tempfile.mkdtemp()) / "sent.json"
        p.write_text("{not json")
        self.assertEqual(S.SentStore(p).keys, [])


class DeliverTests(unittest.TestCase):
    def test_dry_run_never_sends(self):
        send = mock.Mock(return_value=(True, None))
        with mock.patch("builtins.print"):
            self.assertTrue(S.deliver(["m1", "m2"], send, dry_run=True))
        send.assert_not_called()

    def test_failure_is_reported(self):
        send = mock.Mock(side_effect=[(True, None), (False, "400")])
        with mock.patch("builtins.print"):
            self.assertFalse(S.deliver(["m1", "m2"], send, dry_run=False))
        self.assertEqual(send.call_count, 2)


if __name__ == "__main__":
    unittest.main()
