"""Offline tests (no network, no API key needed, never prints a key).

Run with a Python that has server/requirements.txt installed:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
import gemini_tts as g  # noqa: E402

FAKE_KEY = "AQ.FAKE_test_key_0123456789abcdef"


class FakeResp:
    def __init__(self, headers):
        self.headers = headers


class FakeErr(Exception):
    def __init__(self, code, text, headers=None):
        super().__init__(text)
        self.status_code = code
        if headers is not None:
            self.response = FakeResp(headers)


class FriendlyMessages(unittest.TestCase):
    def test_daily_free(self):
        e = FakeErr(429, "Rate limit exceeded for model gemini-3.8-flash-tts (limit: 10 requests per day "
                         "on Free Tier). Please retry in 11h46m12s.", {"retry-after": "42372"})
        self.assertTrue(g._is_daily_quota(e))
        self.assertEqual(g._retry_after_s(e), 42372.0)
        msg = str(g._friendly(e))
        self.assertIn("免費額度已用完", msg)
        self.assertIn("每天上限 10 次", msg)

    def test_daily_paid(self):
        e = FakeErr(429, "Rate limit exceeded for model gemini-3.8-flash-tts (limit: 100 requests per day "
                         "on Tier 1). Please retry in 5h2m0s.")
        msg = str(g._friendly(e))
        self.assertIn("每日額度已用完", msg)
        self.assertIn("付費帳號", msg)

    def test_per_minute_is_not_daily(self):
        e = FakeErr(429, "Rate limit exceeded (limit: 3 requests per minute). Please retry in 7s")
        self.assertFalse(g._is_daily_quota(e))
        self.assertEqual(g._retry_after_s(e), 7.0)
        msg = str(g._friendly(e))
        self.assertIn("429", msg)
        self.assertNotIn("{reset}", msg)

    def test_402(self):
        self.assertIn("預付餘額", str(g._friendly(FakeErr(402, "prepayment credits are depleted"))))

    def test_verification(self):
        msg = str(g._friendly(FakeErr(403, "FREE_TIER_VERIFICATION_REQUIRED: verify your project")))
        self.assertIn("Verify device", msg)

    def test_leaked(self):
        msg = str(g._friendly(FakeErr(403, "Your API key was reported as leaked. Please use another API key.")))
        self.assertIn("外洩", msg)

    def test_invalid_key(self):
        self.assertIn("API Key 無效", str(g._friendly(FakeErr(400, "API key not valid. Please pass a valid API key."))))


class Deadline(unittest.TestCase):
    def test_stops_waiting(self):
        t = time.time()
        with self.assertRaises(g.TTSError) as cm:
            g._call_with_deadline(lambda: time.sleep(10), 1)
        self.assertLess(time.time() - t, 5)
        self.assertIn("不是額度錯誤", str(cm.exception))


class TierSettings(unittest.TestCase):
    def reload(self, env=None, settings=None):
        tmp = Path(tempfile.mkdtemp())
        try:
            src = ROOT / "server" / "gemini_tts.py"
            shutil.copy2(src, tmp / "gemini_tts.py")
            if settings is not None:
                (tmp / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
            spec = importlib.util.spec_from_file_location("gtts_copy", tmp / "gemini_tts.py")
            mod = importlib.util.module_from_spec(spec)
            with mock.patch.dict(os.environ, env or {}, clear=False):
                os.environ.pop("GEMINI_TTS_TIER", None) if env is None or "GEMINI_TTS_TIER" not in env else None
                spec.loader.exec_module(mod)
            return mod
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_default_free(self):
        m = self.reload()
        self.assertEqual(m.TIER, "free")
        self.assertEqual(m.FREE_DAILY_LIMITS, {"gemini-3.8-flash-tts": 10})

    def test_settings_paid(self):
        m = self.reload(settings={"tier": "paid"})
        self.assertEqual(m.TIER, "paid")
        self.assertEqual(m.FREE_DAILY_LIMITS, {})

    def test_env_overrides_settings(self):
        m = self.reload(env={"GEMINI_TTS_TIER": "free"}, settings={"tier": "paid"})
        self.assertEqual(m.TIER, "free")

    def test_bad_value_falls_back(self):
        m = self.reload(settings={"tier": "gold"})
        self.assertEqual(m.TIER, "free")


class Playback(unittest.TestCase):
    def test_mac_uses_afplay(self):
        real_exists = os.path.exists
        with mock.patch.object(g.sys, "platform", "darwin"), \
             mock.patch.object(g.os.path, "exists", lambda p: p == "/usr/bin/afplay" or real_exists(p)):
            cmd = g._player_cmd(Path("/tmp/x.wav"))
        self.assertEqual(cmd[0], "/usr/bin/afplay")

    def test_stop_without_player_is_safe(self):
        with mock.patch.object(g.sys, "platform", "darwin"):
            g._player = None
            g.stop_audio()


def _find_bash():
    for c in (shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe", "/bin/bash"):
        if c and os.path.exists(c):
            return c
    return None


@unittest.skipUnless(_find_bash(), "needs bash")
class LoginShellFallback(unittest.TestCase):
    """macOS path: key only in a shell startup file, not in the process environment."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        (self.home / ".bash_profile").write_text(f"export GEMINI_API_KEY='{FAKE_KEY}'\necho noisy banner\n",
                                                  encoding="utf-8")
        g._shell_key_cache.clear()

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)
        g._shell_key_cache.clear()

    def test_reads_key_from_shell(self):
        bash = _find_bash()
        env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
        env.update(SHELL=bash, HOME=str(self.home))
        real_basename = os.path.basename
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(g.os.path, "basename", lambda p: "bash" if p == bash else real_basename(p)):
            found = g._key_from_login_shell(timeout=20)
        self.assertIsNotNone(found)
        self.assertEqual(found[0], FAKE_KEY)
        self.assertIn("GEMINI_API_KEY", found[1])

    def test_gemini_in_interactive_rc_beats_google_in_login_rc(self):
        (self.home / ".bash_profile").write_text(
            "export GOOGLE_API_KEY='AQ.GOOGLE_only_in_login_files_000'\n"
            f"case $- in *i*) export GEMINI_API_KEY='{FAKE_KEY}';; esac\n", encoding="utf-8")
        bash = _find_bash()
        env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
        env.update(SHELL=bash, HOME=str(self.home))
        real_basename = os.path.basename
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(g.os.path, "basename", lambda p: "bash" if p == bash else real_basename(p)):
            found = g._key_from_login_shell(timeout=20, use_cache=False)
        self.assertEqual(found[0], FAKE_KEY)
        self.assertIn("-ilc", found[1])

    def test_mac_find_api_key_uses_fallback(self):
        env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(g.sys, "platform", "darwin"), \
             mock.patch.object(g, "_key_from_login_shell", return_value=(FAKE_KEY, "shell")):
            self.assertEqual(g.find_api_key(), (FAKE_KEY, "shell"))
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(g.sys, "platform", "darwin"), \
             mock.patch.object(g, "_key_from_login_shell", return_value=None):
            with self.assertRaises(g.TTSError):
                g.find_api_key()


class CheckSetupNeverLeaksKey(unittest.TestCase):
    def test_no_key_in_output(self):
        # never touch the real saved key: the registry / shell lookup is replaced by the fake one
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY}), \
             mock.patch.object(g, "_saved_keys", return_value=[]):
            info = g.check_setup()
        self.assertTrue(info["api_key_found"])
        dumped = json.dumps(info, ensure_ascii=False)
        self.assertFalse(FAKE_KEY in dumped, "key leaked into check_setup output")


class OutputPathSafety(unittest.TestCase):
    def test_secret_variable_rejected(self):
        for raw in ("%GEMINI_API_KEY%.wav", "${GEMINI_API_KEY}.wav", "$GOOGLE_API_KEY/x.wav", "%PATH%/a.wav"):
            with mock.patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY, "GOOGLE_API_KEY": FAKE_KEY}):
                with self.assertRaises(g.TTSError) as cm:
                    g._expand_path_vars(raw)
            self.assertNotIn(FAKE_KEY, str(cm.exception))

    def test_undefined_variable_kept(self):
        env = {k: v for k, v in os.environ.items() if k not in ("hiphop", "off", "HIPHOP", "OFF")}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(g._expand_path_vars("/Users/me/$hiphop/a.wav"), "/Users/me/$hiphop/a.wav")
            self.assertEqual(g._expand_path_vars(r"D:\audio\50%off%\a.wav"), r"D:\audio\50%off%\a.wav")

    def test_folder_variable_allowed(self):
        with mock.patch.dict(os.environ, {"TEMP": "/tmp/gtts"}):
            self.assertEqual(g._expand_path_vars("%TEMP%/a.wav"), "/tmp/gtts/a.wav")
            self.assertEqual(g._expand_path_vars("$TEMP/a.wav"), "/tmp/gtts/a.wav")

    def test_redact(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY}):
            self.assertEqual(g.redact(f"bad request for key {FAKE_KEY}!"), "bad request for key ***!")


class KeyPrecedence(unittest.TestCase):
    OLD = "AQ.OLD_key_from_claude_start_000000"
    NEW = "AQ.NEW_key_the_user_just_saved_1111"

    def env(self, **kw):
        base = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
        base.update(kw)
        return mock.patch.dict(os.environ, base, clear=True)

    def test_windows_saved_key_beats_stale_env(self):
        saved = [("GEMINI_API_KEY", self.NEW, "Windows 使用者環境變數 GEMINI_API_KEY")]
        with self.env(GEMINI_API_KEY=self.OLD), mock.patch.object(g.sys, "platform", "win32"), \
             mock.patch.object(g, "_saved_keys", return_value=saved):
            self.assertEqual(g.find_api_key()[0], self.NEW)

    def test_gemini_anywhere_beats_google(self):
        saved = [("GEMINI_API_KEY", self.NEW, "reg GEMINI")]
        with self.env(GOOGLE_API_KEY=self.OLD), mock.patch.object(g.sys, "platform", "win32"), \
             mock.patch.object(g, "_saved_keys", return_value=saved):
            self.assertEqual(g.find_api_key()[0], self.NEW)
        with self.env(GOOGLE_API_KEY=self.OLD), mock.patch.object(g.sys, "platform", "darwin"), \
             mock.patch.object(g, "_key_from_login_shell", return_value=(self.NEW, "shell 的 GEMINI_API_KEY")):
            self.assertEqual(g.find_api_key()[0], self.NEW)

    def test_mac_saved_key_beats_stale_env(self):
        with self.env(GEMINI_API_KEY=self.OLD), mock.patch.object(g.sys, "platform", "darwin"), \
             mock.patch.object(g, "_key_from_login_shell", return_value=(self.NEW, "shell 的 GEMINI_API_KEY")):
            self.assertEqual(g.find_api_key()[0], self.NEW)            # speech generation
            self.assertEqual(g.find_api_key(fresh=True)[0], self.NEW)  # check_setup / verify

    def test_mac_quick_lookup_when_env_has_key(self):
        calls = []
        def fake(**kw):
            calls.append(kw)
            return None
        with self.env(GEMINI_API_KEY=self.OLD), mock.patch.object(g.sys, "platform", "darwin"), \
             mock.patch.object(g, "_key_from_login_shell", side_effect=fake):
            g.find_api_key()
            g.find_api_key(fresh=True)
        self.assertEqual(calls[0], {"use_cache": True, "quick": True})
        self.assertEqual(calls[1], {"use_cache": False, "quick": False})

    def test_quick_probe_runs_login_shell_only(self):
        flags_seen = []
        def probe(cmd, env, timeout):
            flags_seen.append(cmd[1])
            return ""
        g._shell_key_cache.clear()
        with mock.patch.object(g, "_run_shell_probe", side_effect=probe), \
             mock.patch.object(g.os.path, "exists", return_value=True):
            g._key_from_login_shell(use_cache=False, quick=True)
            g._key_from_login_shell(use_cache=False)
        g._shell_key_cache.clear()
        self.assertEqual(flags_seen, ["-lc", "-lc", "-ilc"])

    def test_mac_env_used_when_nothing_saved(self):
        with self.env(GEMINI_API_KEY=self.OLD), mock.patch.object(g.sys, "platform", "darwin"), \
             mock.patch.object(g, "_key_from_login_shell", return_value=None):
            self.assertEqual(g.find_api_key(), (self.OLD, "環境變數 GEMINI_API_KEY"))

    def test_check_setup_notes_stale_env(self):
        saved = [("GEMINI_API_KEY", self.NEW, "Windows 使用者環境變數 GEMINI_API_KEY")]
        with self.env(GEMINI_API_KEY=self.OLD), mock.patch.object(g.sys, "platform", "win32"), \
             mock.patch.object(g, "_saved_keys", return_value=saved):
            info = g.check_setup()
        self.assertIn("key_note", info)
        self.assertNotIn(self.NEW, json.dumps(info, ensure_ascii=False))


class VerifyKey(unittest.TestCase):
    def client_raising(self, exc):
        models = mock.Mock()
        models.get.side_effect = exc
        return mock.Mock(models=models)

    def test_rejected_key_is_invalid(self):
        with mock.patch.object(g, "get_client", return_value=self.client_raising(FakeErr(403, "permission denied"))):
            self.assertIs(g.verify_key(FAKE_KEY)["key_valid"], False)

    def test_network_error_is_unknown(self):
        with mock.patch.object(g, "get_client", return_value=self.client_raising(ConnectionError("no route"))):
            r = g.verify_key(FAKE_KEY)
        self.assertIsNone(r["key_valid"])
        self.assertIn("不一定是金鑰", r["key_error"])

    def test_ok(self):
        models = mock.Mock()
        models.get.return_value = mock.Mock(name="m")
        with mock.patch.object(g, "get_client", return_value=mock.Mock(models=models)):
            self.assertIs(g.verify_key(FAKE_KEY)["key_valid"], True)

    def test_region_block_is_not_a_key_problem(self):
        err = FakeErr(400, "FAILED_PRECONDITION: User location is not supported for the API use.")
        with mock.patch.object(g, "get_client", return_value=self.client_raising(err)):
            r = g.verify_key(FAKE_KEY)
        self.assertIsNone(r["key_valid"])
        self.assertIn("不是金鑰的問題", r["key_error"])

    def test_other_400_is_not_invalid_key(self):
        with mock.patch.object(g, "get_client", return_value=self.client_raising(FakeErr(400, "bad request"))):
            self.assertIsNone(g.verify_key(FAKE_KEY)["key_valid"])

    def test_invalid_key_message(self):
        err = FakeErr(400, "API key not valid. Please pass a valid API key.")
        with mock.patch.object(g, "get_client", return_value=self.client_raising(err)):
            self.assertIs(g.verify_key(FAKE_KEY)["key_valid"], False)

    def test_limit_zero_message(self):
        e = FakeErr(429, "Rate limit exceeded for model gemini-3.8-flash-tts (limit: 0 requests per day on Free Tier)")
        self.assertIn("等待重置也不會改善", str(g._friendly(e)))


class Installer(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("installer", ROOT / "install.py")
        self.inst = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.inst)

    def test_finds_python_311_plus(self):
        found = self.inst.find_python(None)
        self.assertIsNotNone(found)
        self.assertGreaterEqual(found[1], (3, 11))

    def test_version_of(self):
        self.assertEqual(self.inst.version_of(ROOT / "server" / "gemini_tts.py"), g.__version__)

    def test_write_settings_merges(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "settings.json").write_text(json.dumps({"tier": "paid", "output_dir": "x"}), encoding="utf-8")
            self.assertEqual(self.inst.write_settings(tmp, None), {"tier": "paid", "output_dir": "x"})
            self.assertEqual(self.inst.write_settings(tmp, "free")["tier"], "free")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_backup_only_when_changed(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "srv").mkdir()
            new = tmp / "new.py"
            new.write_text('__version__ = "9.9"\n', encoding="utf-8")
            inst = tmp / "srv" / "gemini_tts.py"
            shutil.copy2(new, inst)
            self.assertIsNone(self.inst.backup_existing([(inst, new)], tmp / "srv", "s1"))
            inst.write_text('__version__ = "1.0"\n', encoding="utf-8")
            b = self.inst.backup_existing([(inst, new)], tmp / "srv", "s2")
            self.assertTrue((b / "gemini_tts.py").exists())
            self.assertIn("backup_v1.0_s2", str(b))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_bad_settings_are_kept(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "settings.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(self.inst.write_settings(tmp, None, "s")["tier"], "free")
            self.assertTrue((tmp / "settings.json.bad_s").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_manual_register_quotes_paths(self):
        exe = r"C:\Users\A B\claude.exe"
        cmd = self.inst.manual_register_cmd(exe, Path("C:/x y/py.exe"), Path("C:/x y/s.py"), "user")
        self.assertTrue(cmd.startswith(f'"{exe}" mcp remove gemini-tts -s user; "{exe}" mcp add --transport stdio '
                                       '--scope user gemini-tts -- "'))
        ps = self.inst.manual_register_cmd(exe, Path("C:/x y/py.exe"), Path("C:/x y/s.py"), "user", powershell=True)
        self.assertTrue(ps.startswith(f'& "{exe}" mcp remove gemini-tts -s user; & "{exe}" mcp add '))

    def test_prefers_tested_python(self):
        rank_input = [((3, 16), "a"), ((3, 13), "b"), ((3, 14), "c")]
        with mock.patch.object(self.inst, "python_candidates", return_value=[[x[1]] for x in rank_input]), \
             mock.patch.object(self.inst, "py_version", side_effect=lambda cmd: next(
                 (v[0], v[1], cmd[0]) for v, n in rank_input if n == cmd[0])):
            self.assertEqual(self.inst.find_python(None)[1], (3, 14))
        with mock.patch.object(self.inst, "python_candidates", return_value=[["a"]]), \
             mock.patch.object(self.inst, "py_version", return_value=(3, 16, "a")):
            self.assertEqual(self.inst.find_python(None)[1], (3, 16))

    def test_script_line_endings(self):
        cmd = (ROOT / "scripts" / "set-gemini-key.command").read_bytes()
        self.assertNotIn(b"\r", cmd, "macOS script must use LF line endings")
        self.assertTrue(cmd.startswith(b"#!/bin/bash\n"))
        ps1 = (ROOT / "scripts" / "set-gemini-key.ps1").read_bytes()
        self.assertTrue(ps1.startswith(b"\xef\xbb\xbf"), "PS1 needs a UTF-8 BOM for Windows PowerShell 5.1")
        self.assertIn(b"\r\n", ps1)

    def test_child_env_has_no_key(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY, "GOOGLE_API_KEY": FAKE_KEY}):
            env = self.inst.child_env()
        self.assertNotIn("GEMINI_API_KEY", env)
        self.assertNotIn("GOOGLE_API_KEY", env)

    def test_repo_has_no_secrets_or_state(self):
        bad = [p for p in ROOT.rglob("*") if p.name in ("usage.json", "settings.json", ".env")
               and ".venv" not in p.parts and ".git" not in p.parts]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
