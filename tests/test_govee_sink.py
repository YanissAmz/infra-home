import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ambilight_unified_sync.py"
SPEC = importlib.util.spec_from_file_location("ambilight_unified_sync", MODULE_PATH)
sync = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(sync)


class FakeSocket:
    def __init__(self):
        self.messages = []

    def sendto(self, payload: bytes, addr):
        self.messages.append((json.loads(payload.decode()), addr))


class GoveeSinkTests(unittest.TestCase):
    def setUp(self):
        self._runtime = {
            "night_start": sync.NIGHT_START,
            "night_end": sync.NIGHT_END,
            "night_hue_bri": sync.NIGHT_HUE_BRI,
            "night_govee_bri": sync.NIGHT_GOVEE_BRI,
            "night_led_scale": sync.NIGHT_LED_SCALE,
            "delta_day": sync.DELTA_THRESHOLD_DAY,
            "delta_night": sync.DELTA_THRESHOLD_NIGHT,
            "status_dir": sync.STATUS_DIR,
            "status_refresh": sync.STATUS_REFRESH_INTERVAL_S,
        }
        sync._night_cache = False
        sync._night_cache_ts = 0.0

    def tearDown(self):
        sync.NIGHT_START = self._runtime["night_start"]
        sync.NIGHT_END = self._runtime["night_end"]
        sync.NIGHT_HUE_BRI = self._runtime["night_hue_bri"]
        sync.NIGHT_GOVEE_BRI = self._runtime["night_govee_bri"]
        sync.NIGHT_LED_SCALE = self._runtime["night_led_scale"]
        sync.DELTA_THRESHOLD_DAY = self._runtime["delta_day"]
        sync.DELTA_THRESHOLD_NIGHT = self._runtime["delta_night"]
        sync.STATUS_DIR = self._runtime["status_dir"]
        sync.STATUS_REFRESH_INTERVAL_S = self._runtime["status_refresh"]
        sync._night_cache = False
        sync._night_cache_ts = 0.0

    def test_push_updates_brightness_even_when_color_delta_is_filtered(self):
        fake_socket = FakeSocket()
        with patch.object(sync.socket, "socket", return_value=fake_socket):
            sink = sync.GoveeSink("192.168.68.59", brightness=80)

        sink.last = (10, 20, 30)
        sink._night_state = False
        sink._last_bri_ts = 900.0

        with patch.object(sync, "is_night", return_value=True), patch.object(
            sync.time, "monotonic", return_value=1000.0
        ):
            sink.push({"avg": (10, 20, 30)})

        self.assertEqual(len(fake_socket.messages), 1)
        msg, addr = fake_socket.messages[0]
        self.assertEqual(addr, ("192.168.68.59", sync.GOVEE_LAN_PORT))
        self.assertEqual(msg["msg"]["cmd"], "brightness")
        self.assertEqual(msg["msg"]["data"]["value"], sync.NIGHT_GOVEE_BRI)

    def test_turn_on_uses_current_target_brightness(self):
        fake_socket = FakeSocket()
        with patch.object(sync.socket, "socket", return_value=fake_socket):
            sink = sync.GoveeSink("192.168.68.59", brightness=80)

        with patch.object(sync, "is_night", return_value=False), patch.object(
            sync.time, "monotonic", return_value=123.0
        ):
            sink.turn_on()

        self.assertEqual(fake_socket.messages[0][0]["msg"]["cmd"], "turn")
        self.assertEqual(fake_socket.messages[1][0]["msg"]["cmd"], "brightness")
        self.assertEqual(fake_socket.messages[1][0]["msg"]["data"]["value"], 80)
        self.assertFalse(sink._night_state)
        self.assertEqual(sink._last_bri_ts, 123.0)

    def test_apply_runtime_config_overrides_defaults(self):
        sync._apply_runtime_config(
            {
                "runtime": {
                    "night": {
                        "start_hour": 21,
                        "end_hour": 7,
                        "hue_brightness": 42,
                        "govee_brightness": 3,
                        "led_scale": 0.15,
                    },
                    "delta_threshold": {"day": 9, "night": 27},
                    "status": {"dir": "/tmp/ambilight-status", "refresh_interval_s": 11},
                }
            }
        )

        self.assertEqual(sync.NIGHT_START, 21)
        self.assertEqual(sync.NIGHT_END, 7)
        self.assertEqual(sync.NIGHT_HUE_BRI, 42)
        self.assertEqual(sync.NIGHT_GOVEE_BRI, 3)
        self.assertEqual(sync.NIGHT_LED_SCALE, 0.15)
        self.assertEqual(sync.DELTA_THRESHOLD_DAY, 9)
        self.assertEqual(sync.DELTA_THRESHOLD_NIGHT, 27)
        self.assertEqual(sync.STATUS_DIR, Path("/tmp/ambilight-status"))
        self.assertEqual(sync.STATUS_REFRESH_INTERVAL_S, 11.0)

    def test_force_night_takes_precedence_over_force_day(self):
        sync._night_cache_ts = -1.0
        def fake_exists(path):
            return path in {sync.FORCE_NIGHT_FLAG, sync.FORCE_DAY_FLAG}

        with patch("pathlib.Path.exists", autospec=True, side_effect=fake_exists):
            self.assertEqual(sync.resolve_mode(tv_online=True), "force_night")
            self.assertTrue(sync.is_night())


if __name__ == "__main__":
    unittest.main()
