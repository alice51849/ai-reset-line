import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIX = os.path.join(HERE, "fixtures")
sys.path.insert(0, os.path.join(ROOT, "src"))

import ai_reset_line as arl  # noqa: E402

NOW = 1800000000  # 2027-01-15 08:00:00 UTC, a Friday


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


class UTCMixin:
    def setUp(self):
        self._tz = os.environ.get("TZ")
        os.environ["TZ"] = "UTC"
        if hasattr(time, "tzset"):
            time.tzset()

    def tearDown(self):
        if self._tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._tz
        if hasattr(time, "tzset"):
            time.tzset()


class ParseTests(UTCMixin, unittest.TestCase):
    def test_subscriber_plain(self):
        s = arl.parse_status(load("claude_subscriber.json"))
        self.assertEqual(
            arl.render(s, "plain", False, NOW),
            "Large · 5h 42% ↻1h18m · 7d 63% ↻Mon 08:00 · ctx 38%",
        )

    def test_subscriber_compact(self):
        s = arl.parse_status(load("claude_subscriber.json"))
        self.assertEqual(
            arl.render(s, "compact", False, NOW),
            "Large 5h:42%/1h18m 7d:63%/Mon08:00 ctx:38%",
        )

    def test_subscriber_bar(self):
        s = arl.parse_status(load("claude_subscriber.json"))
        out = arl.render(s, "bar", False, NOW)
        self.assertEqual(
            out,
            "Large · 5h ▓▓▓▓░░░░░░ 42% ↻1h18m"
            " · 7d ▓▓▓▓▓▓░░░░ 63% ↻Mon 08:00"
            " · ctx ▓▓░░░ 38%",
        )

    def test_no_rate_limits_degrades(self):
        s = arl.parse_status(load("claude_no_rate_limits.json"))
        self.assertEqual(arl.render(s, "plain", False, NOW), "Medium")

    def test_api_key_user(self):
        s = arl.parse_status(load("claude_api_key.json"))
        self.assertIsNone(s["five_hour"])
        self.assertEqual(arl.render(s, "plain", False, NOW), "Medium · ctx 13%")

    def test_partial_and_alternate_spellings(self):
        s = arl.parse_status(load("claude_partial.json"))
        self.assertEqual(s["five_hour"]["used_percentage"], 91.0)
        self.assertEqual(arl.render(s, "plain", False, NOW), "Small · 5h 91% ↻1h30m")

    def test_color_thresholds(self):
        s = arl.parse_status(load("claude_partial.json"))
        self.assertIn(arl.RED + "91%" + arl.RESET, arl.render(s, "plain", True, NOW))
        s = arl.parse_status(load("claude_subscriber.json"))
        out = arl.render(s, "plain", True, NOW)
        self.assertIn(arl.GREEN + "42%", out)
        self.assertIn(arl.YELLOW + "63%", out)

    def test_expired_window(self):
        s = {"model": "M", "five_hour": {"used_percentage": 99, "resets_at": NOW - 10},
             "seven_day": None, "context_used_percentage": None}
        self.assertEqual(arl.render(s, "plain", False, NOW), "M · 5h ↻reset")

    def test_garbage_input_never_raises(self):
        for bad in (None, [], "x", 3, {"model": "str"}, {"rate_limits": "x"},
                    {"rate_limits": {"five_hour": {"used_percentage": "nope"}}}):
            s = arl.parse_status(bad)
            self.assertIsInstance(arl.render(s, "plain", False, NOW), str)
        self.assertEqual(arl.render(arl.parse_status({}), "plain", False, NOW),
                         "ai-reset-line: waiting for data")

    def test_epoch_forms(self):
        self.assertEqual(arl._epoch(1800000000), 1800000000.0)
        self.assertEqual(arl._epoch(1800000000000), 1800000000.0)
        self.assertEqual(arl._epoch("2027-01-15T08:00:00Z"), 1800000000.0)
        self.assertIsNone(arl._epoch("soon"))
        self.assertIsNone(arl._epoch(True))

    def test_durations(self):
        self.assertEqual(arl.fmt_duration(30), "<1m")
        self.assertEqual(arl.fmt_duration(45 * 60), "45m")
        self.assertEqual(arl.fmt_duration(78 * 60), "1h18m")
        self.assertEqual(arl.fmt_duration(2 * 86400 + 4 * 3600), "2d4h")

    def test_weekly_within_a_day_uses_countdown(self):
        s = {"model": None, "five_hour": None,
             "seven_day": {"used_percentage": 10, "resets_at": NOW + 3600},
             "context_used_percentage": None}
        self.assertEqual(arl.render(s, "plain", False, NOW), "7d 10% ↻1h00m")


class ColorEnvTests(unittest.TestCase):
    def test_no_color_env(self):
        args = arl.build_parser().parse_args([])
        self.assertFalse(arl.use_color(args, {"NO_COLOR": "1"}))
        self.assertTrue(arl.use_color(args, {}))
        self.assertTrue(arl.use_color(args, {"NO_COLOR": ""}))
        args = arl.build_parser().parse_args(["--no-color"])
        self.assertFalse(arl.use_color(args, {}))


class CacheTests(UTCMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "ai-reset-line", "last.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def test_cache_written_without_session_data(self):
        s = arl.parse_status(load("claude_subscriber.json"))
        self.assertTrue(arl.write_cache(s, self.path, NOW))
        with open(self.path, encoding="utf-8") as fh:
            text = fh.read()
        for secret in ("session_id", "transcript_path", "/home/example"):
            self.assertNotIn(secret, text)
        data = json.loads(text)
        self.assertEqual(data["five_hour"]["used_percentage"], 42.3)

    def test_no_limits_does_not_overwrite(self):
        s = arl.parse_status(load("claude_subscriber.json"))
        arl.write_cache(s, self.path, NOW)
        self.assertFalse(arl.write_cache(arl.parse_status(load("claude_api_key.json")), self.path, NOW))
        self.assertEqual(arl.read_cache(self.path)["model"], "Large")

    def test_cache_path_env(self):
        self.assertEqual(arl.cache_path({"XDG_CACHE_HOME": "/x"}), "/x/ai-reset-line/last.json")
        self.assertEqual(arl.cache_path({"AI_RESET_LINE_CACHE": "/y.json"}), "/y.json")

    def test_unwritable_cache_is_silent(self):
        s = arl.parse_status(load("claude_subscriber.json"))
        blocker = os.path.join(self.tmp, "file")
        open(blocker, "w").close()
        self.assertFalse(arl.write_cache(s, os.path.join(blocker, "sub", "last.json"), NOW))


class CodexTests(UTCMixin, unittest.TestCase):
    def test_latest_snapshot(self):
        snap, note = arl.latest_codex_snapshot(os.path.join(FIX, "codex_home"))
        self.assertIsNone(note)
        self.assertEqual(snap["primary"]["used_percent"], 27.5)
        self.assertEqual(snap["secondary"]["window_minutes"], 10080)
        self.assertEqual(snap["limit_name"], "codex")
        self.assertEqual(snap["plan_type"], "plus")

    def test_legacy_relative_reset(self):
        with open(os.path.join(FIX, "codex_legacy_line.jsonl"), encoding="utf-8") as fh:
            snap = arl.parse_codex_line(fh.readline())
        self.assertEqual(snap["primary"]["resets_at"], NOW - 3600 + 3600)

    def test_ignores_other_lines(self):
        self.assertIsNone(arl.parse_codex_line("not json"))
        self.assertIsNone(arl.parse_codex_line('{"type":"event_msg","payload":{"type":"token_count","rate_limits":null}}'))
        self.assertIsNone(arl.parse_codex_line('{"type":"response_item","payload":{}}'))

    def test_missing_home(self):
        snap, note = arl.latest_codex_snapshot(os.path.join(FIX, "does-not-exist"))
        self.assertIsNone(snap)
        self.assertIn("no session files", note)

    def test_labels(self):
        self.assertEqual(arl.codex_label(300), "5h")
        self.assertEqual(arl.codex_label(10080), "7d")
        self.assertEqual(arl.codex_label(60), "1h")
        self.assertEqual(arl.codex_label(None), "window")

    def test_summary(self):
        tmp = tempfile.mkdtemp()
        try:
            cache = os.path.join(tmp, "last.json")
            arl.write_cache(arl.parse_status(load("claude_subscriber.json")), cache, NOW - 120)
            text = arl.summary(now=NOW, color=False, cache_file=cache,
                               home=os.path.join(FIX, "codex_home"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertIn("Claude Code", text)
        self.assertIn("last seen 2m ago, Large", text)
        self.assertIn("5h    42%  resets in 1h18m (09:18)", text)
        self.assertIn("Codex CLI", text)
        self.assertIn("28%", text)
        self.assertIn("not a live reading", text)


class CliTests(unittest.TestCase):
    def run_cli(self, fixture, *args):
        env = dict(os.environ, NO_COLOR="1", AI_RESET_LINE_CACHE=os.path.join(self.tmp, "c.json"))
        with open(os.path.join(FIX, fixture), "rb") as fh:
            return subprocess.run(
                ["sh", os.path.join(ROOT, "bin", "ai-reset-line")] + list(args),
                stdin=fh, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False,
            )

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_wrapper_runs(self):
        res = self.run_cli("claude_api_key.json")
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.decode("utf-8").strip(), "Medium · ctx 13%")
        self.assertEqual(res.stderr, b"")

    def test_main_with_empty_stdin(self):
        out = io.StringIO()
        old = os.environ.get("AI_RESET_LINE_CACHE")
        os.environ["AI_RESET_LINE_CACHE"] = os.path.join(self.tmp, "c.json")
        try:
            self.assertEqual(arl.main(["--no-color"], io.StringIO(""), out), 0)
        finally:
            if old is None:
                os.environ.pop("AI_RESET_LINE_CACHE", None)
            else:
                os.environ["AI_RESET_LINE_CACHE"] = old
        self.assertEqual(out.getvalue().strip(), "ai-reset-line: waiting for data")


class PackagingTests(unittest.TestCase):
    def test_plugin_copy_in_sync(self):
        with open(os.path.join(ROOT, "src", "ai_reset_line.py"), "rb") as a, \
                open(os.path.join(ROOT, "plugins", "ai-reset-line", "scripts", "ai_reset_line.py"), "rb") as b:
            self.assertEqual(a.read(), b.read(), "run: cp src/ai_reset_line.py plugins/ai-reset-line/scripts/")

    def test_json_manifests_parse(self):
        for rel in (".claude-plugin/marketplace.json",
                    "plugins/ai-reset-line/.claude-plugin/plugin.json",
                    "examples/settings.json"):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                self.assertIsInstance(json.load(fh), dict, rel)

    def test_no_network_imports(self):
        with open(os.path.join(ROOT, "src", "ai_reset_line.py"), encoding="utf-8") as fh:
            src = fh.read()
        for mod in ("urllib", "http.client", "socket", "requests", "ssl"):
            self.assertNotIn("import " + mod, src)


if __name__ == "__main__":
    unittest.main()
