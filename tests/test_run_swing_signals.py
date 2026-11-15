"""botdown.run_swing_signals: edge-triggered scenarios, levels, dedupe across runs, heartbeat (offline)."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from botdown import run_swing_signals as R
from tests.helpers import trend_ohlc


def _series(values):
    return lambda df: pd.Series(values[-len(df):] if len(values) >= len(df) else [0] * (len(df) - len(values)) + values,
                                index=df.index)


def _df(n=80):
    d = trend_ohlc(n)
    d["oi_chg_3"], d["oi_z_30"], d["fund_z_30"] = 0.02, 0.5, -1.6
    d["usdt_d"], d["usdt_d_chg_3"], d["usdt_d_z_30"] = 7.5, -0.3, -1.2
    d["bull"], d["bear"] = True, False
    return d


class ScanDailyTests(unittest.TestCase):
    def run_with(self, values, macd=None):
        scen = [("X_test", "rule", _series(values))]
        with mock.patch.object(R, "SCENARIOS_1D", scen), \
             mock.patch.object(R, "macd_rsi_entry_snapshot", return_value=macd):
            return R.scan_daily("BTCUSDT", _df())

    def test_fires_when_scenario_turns_on(self):
        out = self.run_with([0, 1])
        self.assertEqual([(s.strategy, s.side) for s in out], [("X_test", "long")])

    def test_persistent_state_does_not_repeat(self):
        self.assertEqual(self.run_with([1, 1]), [])

    def test_flip_long_to_short_fires(self):
        out = self.run_with([1, -1])
        self.assertEqual(out[0].side, "short")

    def test_levels_follow_tf_defaults(self):
        s = self.run_with([0, 1])[0]
        self.assertAlmostEqual(s.stop, s.entry * (1 - R.CFG_1D["sl"]))
        self.assertAlmostEqual(s.target, s.entry * (1 + R.CFG_1D["tp"]))
        self.assertEqual(s.bar_time, _df()["date"].iloc[-1].strftime("%Y-%m-%d"))

    def test_macd_snapshot_becomes_signal(self):
        snap = {"side": "short", "entry_ref": 100.0, "stop": 104.0, "tp": 90.0}
        out = self.run_with([0, 0], macd=snap)
        self.assertEqual([(s.strategy, s.side, s.stop) for s in out], [("macd_rsi_pct_ema", "short", 104.0)])

    def test_short_history_skipped(self):
        with mock.patch("builtins.print"):
            self.assertEqual(R.scan_daily("BTCUSDT", _df(30)), [])


class MainDedupeTests(unittest.TestCase):
    """Two consecutive runs: the second must send nothing (catch-up after sleep is idempotent)."""

    def setUp(self):
        self.store = Path(tempfile.mkdtemp()) / "swing_sent.json"
        self.week = {"bias": "Giảm", "score": -2, "ema20_gt_ema50": False, "cloud": "dưới mây",
                     "macd_hist": -1.0, "macd_rising": False, "rsi": 45.0, "chg_4w_pct": -3.0}

    def run_main(self, send, argv, scen_values):
        scen = [("X_test", "rule", _series(scen_values))]
        with mock.patch.object(R, "STORE", self.store), \
             mock.patch.object(R, "SCENARIOS_1D", scen), \
             mock.patch.object(R, "macd_rsi_entry_snapshot", return_value=None), \
             mock.patch.object(R, "weekly_for", return_value=(self.week, "2026-11-08")), \
             mock.patch.object(R, "_panel_1d", return_value=_df()), \
             mock.patch("notify.telegram.send_message", send), \
             mock.patch("sys.argv", ["x"] + argv), mock.patch("builtins.print"):
            return R.main()

    def test_signal_and_weekly_sent_once(self):
        send = mock.Mock(return_value=(True, None))
        self.assertEqual(self.run_main(send, ["--symbols", "BTCUSDT"], [0, 1]), 0)
        self.assertEqual(send.call_count, 1)
        text = send.call_args[0][0]
        self.assertIn("xu hướng tuần kết thúc 2026-11-08", text)
        self.assertIn("X_test", text)
        send.reset_mock()
        self.run_main(send, ["--symbols", "BTCUSDT"], [0, 1])
        send.assert_not_called()

    def test_heartbeat_when_no_signal(self):
        send = mock.Mock(return_value=(True, None))
        self.run_main(send, ["--symbols", "BTCUSDT", "--heartbeat", "--daily-only"], [0, 0])
        self.assertIn("không có tín hiệu", send.call_args[0][0])

    def test_failed_send_is_not_marked_sent(self):
        send = mock.Mock(return_value=(False, "429"))
        self.assertEqual(self.run_main(send, ["--symbols", "BTCUSDT"], [0, 1]), 1)
        self.assertFalse(self.store.exists())

    def test_dry_run_does_not_send_or_store(self):
        send = mock.Mock(return_value=(True, None))
        self.run_main(send, ["--symbols", "BTCUSDT", "--dry-run"], [0, 1])
        send.assert_not_called()
        self.assertFalse(self.store.exists())


if __name__ == "__main__":
    unittest.main()
