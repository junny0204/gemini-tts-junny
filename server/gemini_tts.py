"""Gemini 3.8 Flash TTS - core library and command-line tool.

Imported by mcp_server.py (MCP tools for Claude Code); also runnable directly:

    python gemini_tts.py "要念的文字" --voice Kore --style "warm and calm" -o out.wav --play
    python gemini_tts.py --file script.txt -o narration.wav
    python gemini_tts.py --dialogue dialogue.json -o talk.wav
    python gemini_tts.py --list-voices --search Mandarin
    python gemini_tts.py --check

API reference: https://aistudio.google.com/docs/speech-generation.md
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import threading
import time
import wave
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path
from typing import Any

__version__ = "1.2.0"

DEFAULT_MODEL = "gemini-3.8-flash-tts"
LITE_MODEL = "gemini-3.8-flash-lite-tts"
SUPPORTED_MODELS = (DEFAULT_MODEL, LITE_MODEL)
DEFAULT_VOICE = "Kore"
HERE = Path(__file__).resolve().parent
SETTINGS_FILE = HERE / "settings.json"   # written by install.py; never contains the API key


def _load_settings() -> dict[str, Any]:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


SETTINGS = _load_settings()
# "free" or "paid": which Gemini API tier the key's Google project is on. Env var wins over settings.json.
TIER = (os.environ.get("GEMINI_TTS_TIER") or str(SETTINGS.get("tier") or "free")).strip().lower()
if TIER not in ("free", "paid"):
    TIER = "free"
DEFAULT_OUTPUT_DIR = Path(
    os.environ.get("GEMINI_TTS_OUTPUT_DIR") or SETTINGS.get("output_dir") or Path.home() / "Music" / "GeminiTTS"
).expanduser()
# Mention the local IndexTTS2 tool in error advice only where it is installed.
HAS_INDEXTTS2 = (Path.home() / ".claude" / "skills" / "indextts2").is_dir()
_ALT = "／本機 IndexTTS2" if HAS_INDEXTTS2 else ""

# A single request returns at most 16,384 audio tokens (25 tokens/s, about 10.9 min).
# Long scripts are split at paragraph/sentence boundaries into chunks of at most
# CHUNK_UNITS (1 CJK character = 1 unit, any other character = 1/3 unit), which is
# roughly 7-8 minutes of Mandarin. If a chunk still overruns, the SDK continues the
# generation automatically and every returned audio block is kept.
CHUNK_UNITS = 2000
GAP_MS = 250  # silence inserted between separately generated chunks / turns
# v1.1.0: hard limits so a call can never hang. Before, the SDK honoured the server's
# Retry-After on a daily-quota 429 (about 12 hours) and slept, so the tool sat silent
# until Claude Code gave up after 30 minutes. Now the SDK never retries a 429 itself:
# per-minute 429s are retried here with short waits, a daily 429 fails at once with
# the reset time, and every request is cut off after HARD_DEADLINE_S.
REQUEST_TIMEOUT_S = 120          # one HTTP request
HARD_DEADLINE_S = 150            # wall clock for one request, whatever the SDK does
RETRY_DELAYS_S = (20, 40)        # waits before retrying a per-minute 429 or a 5xx
MAX_RETRY_WAIT_S = 60            # never sleep longer than this on a server Retry-After
# Free-tier requests per day as shown in AI Studio (https://aistudio.google.com/rate-limit) in 2026-11.
# Only used for the "used today" hint; Google enforces the real limit. Not used on the paid tier.
# settings.json may override it with "free_daily_limits".
_DEFAULT_FREE_LIMITS = {DEFAULT_MODEL: 10}
FREE_DAILY_LIMITS: dict[str, int] = (
    {} if TIER == "paid" else dict(SETTINGS.get("free_daily_limits") or _DEFAULT_FREE_LIMITS)
)
USAGE_FILE = HERE / "usage.json"

PREBUILT_VOICES = {
    "Zephyr": "Bright 明亮",
    "Puck": "Upbeat 活潑",
    "Charon": "Informative 知性",
    "Kore": "Firm 沉穩",
    "Fenrir": "Excitable 興奮",
    "Leda": "Youthful 年輕",
    "Orus": "Firm 堅定",
    "Aoede": "Breezy 輕快",
    "Callirrhoe": "Easy-going 隨和",
    "Autonoe": "Bright 明亮",
    "Enceladus": "Breathy 氣聲",
    "Iapetus": "Clear 清晰",
    "Umbriel": "Easy-going 隨和",
    "Algieba": "Smooth 滑順",
    "Despina": "Smooth 滑順",
    "Erinome": "Clear 清晰",
    "Algenib": "Gravelly 沙啞",
    "Rasalgethi": "Informative 知性",
    "Laomedeia": "Upbeat 活潑",
    "Achernar": "Soft 柔和",
    "Alnilam": "Firm 堅定",
    "Schedar": "Even 平穩",
    "Gacrux": "Mature 成熟",
    "Pulcherrima": "Forward 直率",
    "Achird": "Friendly 友善",
    "Zubenelgenubi": "Casual 輕鬆",
    "Vindemiatrix": "Gentle 溫柔",
    "Sadachbia": "Lively 生動",
    "Sadaltager": "Knowledgeable 博學",
    "Sulafat": "Warm 溫暖",
}

_NO_KEY_COMMON = (
    "找不到 Gemini API Key（環境變數 GEMINI_API_KEY）。"
    "取得金鑰：https://aistudio.google.com/apikey（步驟見安裝包 docs/01_取得Gemini_API金鑰.md）。"
    "金鑰請你自己輸入，不要貼到對話裡。"
)
NO_KEY_MSG_WIN = _NO_KEY_COMMON + (
    "Windows 設定方式：執行安裝包的 scripts/set-gemini-key.ps1（會開視窗讓你貼上，畫面只顯示 *），"
    "或搜尋「環境變數」→「編輯您的帳戶的環境變數」→ 使用者變數「新增」→ 變數名稱 GEMINI_API_KEY → 兩次「確定」。"
    "設定後這個工具不用重開就讀得到；Claude 本身建議完全結束再開啟。"
)
NO_KEY_MSG_MAC = _NO_KEY_COMMON + (
    "macOS 設定方式：在「終端機」執行安裝包的 scripts/set-gemini-key.command（畫面不會顯示輸入的字），"
    "它會把 export GEMINI_API_KEY='…' 寫進 ~/.zshenv。設定後這個工具會自動讀到；Claude 本身建議 Cmd+Q 結束再開啟。"
)
NO_KEY_MSG_OTHER = _NO_KEY_COMMON + "請在 shell 設定檔（例如 ~/.zshenv 或 ~/.bashrc）加入 export GEMINI_API_KEY='…'。"
NO_KEY_MSG = (
    NO_KEY_MSG_WIN if sys.platform == "win32" else NO_KEY_MSG_MAC if sys.platform == "darwin" else NO_KEY_MSG_OTHER
)
QUOTA_MSG = (
    "已達 Gemini API 使用上限（429）。若是每分鐘上限，等一分鐘再試；"
    "若是每日上限，會在美國太平洋時間午夜重置（本機時間 {reset}）。"
    "目前額度可在 https://aistudio.google.com/rate-limit 查看；"
    "急用可改用 gemini-3.8-flash-lite-tts（額度分開計算）。"
)
DAILY_QUOTA_MSG = (
    "今天 {model} 的{kind}已用完（Google 回報：每天上限 {limit} 次）。"
    "額度會在 {reset}（約 {wait} 後）重置。{advice}"
)
DAILY_ADVICE_FREE = (
    "可以等重置、在 AI Studio 開通付費（https://aistudio.google.com/projects 的 Billing Tier 欄按 Set up billing），"
    f"或改用 gemini-3.8-flash-lite-tts（額度分開、音色略有差異）{_ALT}。"
)
DAILY_ADVICE_PAID = (
    "這是付費帳號的每日上限，可以等重置，或到 https://aistudio.google.com/rate-limit 查看上限；"
    f"急用可改用 gemini-3.8-flash-lite-tts（額度分開、音色略有差異）{_ALT}。"
)
PREPAID_EMPTY_MSG = (
    "Gemini 拒絕請求（402）：這把 API Key 所屬專案的預付餘額已用完（或帳單有問題），儲值前所有請求都會失敗。"
    "請到 https://aistudio.google.com/billing 儲值或檢查帳單，再重試。"
    + ("急用可改用本機 IndexTTS2（不需額度，但聲音不同）。" if HAS_INDEXTTS2 else "")
)
TIMEOUT_MSG = (
    "Gemini 超過 {seconds} 秒沒有回應，已停止等待（這不是額度錯誤）。"
    f"可能是 Google 伺服器暫時異常，請稍後再試，或改用 gemini-3.8-flash-lite-tts{_ALT}。"
)


class TTSError(Exception):
    """Failure whose message is meant for the end user (Traditional Chinese)."""


# ---------------------------------------------------------------- API key / client

_KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
_clients: dict[str, Any] = {}


def _clean_key(value: Any) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


_shell_key_cache: dict[str, Any] = {}
_SHELL_HIT_S = 60     # reuse a key found in the shell files for 1 min
_SHELL_MISS_S = 30    # and a "not found" for 30 s (each lookup may start the shell twice)
_SHELL_QUICK_MISS_S = 600   # quick check (login files only) when Claude already has a key: 10 min
_last_keys: set[str] = set()   # every key value this process has handled, for redact()


def _run_shell_probe(cmd: list[str], env: dict[str, str], timeout: float) -> str:
    """Run a shell with no stdin, capture stdout; on timeout kill its whole process group."""
    import subprocess

    posix = os.name == "posix"
    proc = subprocess.Popen(
        cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        start_new_session=posix,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            if posix:
                import signal

                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except OSError:
            pass
        try:
            out, _ = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:  # a detached helper still holds the pipe: give up
            if proc.stdout:
                proc.stdout.close()
            return ""
    return (out or b"").decode("utf-8", "replace")


def _key_from_login_shell(timeout: float = 10.0, use_cache: bool = True,
                          quick: bool = False) -> tuple[str, str] | None:
    """macOS/Linux: read the key the user saved in the shell startup files.

    Apps started from the Dock/Finder do not run a shell, so an MCP server launched by the
    Claude app may not have the key exported in ~/.zshenv. Like VS Code's shell-env resolver,
    ask the shell itself (first `-lc`, then `-ilc` for keys kept in ~/.zshrc) and read the
    values between random markers. The key variables are removed from the child's environment,
    so only what the startup files set is seen. stdin/stdout never touch the MCP JSON-RPC pipe.
    quick=True (used when Claude already has a key in its environment) only runs `-lc`, which
    reads the files the set-key script writes, and remembers a miss for 10 minutes.
    """
    now = time.time()
    hit = _shell_key_cache.get("hit")
    if use_cache and hit and now - hit[2] < _SHELL_HIT_S:
        return hit[0], hit[1]
    if use_cache:
        miss = _shell_key_cache.get("miss")
        if miss and now - miss < _SHELL_MISS_S:
            return None
        miss_quick = _shell_key_cache.get("miss_quick")
        if quick and miss_quick and now - miss_quick < _SHELL_QUICK_MISS_S:
            return None
    import secrets

    shell = os.environ.get("SHELL") or "/bin/zsh"
    if os.path.basename(shell) not in ("zsh", "bash", "sh", "ksh") or not os.path.exists(shell):
        shell = "/bin/zsh" if os.path.exists("/bin/zsh") else "/bin/bash"
    if not os.path.exists(shell):
        return None
    mark = "GTTS" + secrets.token_hex(8)
    script = f'printf "\n{mark}\n%s\n%s\n{mark}\n" "${{GEMINI_API_KEY-}}" "${{GOOGLE_API_KEY-}}"'
    env = {k: v for k, v in os.environ.items() if k not in _KEY_NAMES}
    env.update(DISABLE_AUTO_UPDATE="true", ZSH_TMUX_AUTOSTART="false",
               GEMINI_TTS_RESOLVING_ENV="1", TERM="dumb")
    google_only = None
    for flags in (("-lc",) if quick else ("-lc", "-ilc")):
        try:
            out = _run_shell_probe([shell, flags, script], env, timeout)
        except OSError:
            continue
        found = re.search(rf"\n{mark}\n(.*)\n(.*)\n{mark}\n", out)
        if not found:
            continue
        gemini, google = (_clean_key(v) for v in found.groups())
        if gemini:
            where = f"shell 設定檔（{os.path.basename(shell)} {flags}）的 GEMINI_API_KEY"
            _shell_key_cache["hit"] = (gemini, where, time.time())
            _shell_key_cache.pop("miss", None)
            _shell_key_cache.pop("miss_quick", None)
            return gemini, where
        if google and not google_only:
            google_only = (google, f"shell 設定檔（{os.path.basename(shell)} {flags}）的 GOOGLE_API_KEY")
    if google_only:
        _shell_key_cache["hit"] = (google_only[0], google_only[1], time.time())
        _shell_key_cache.pop("miss", None)
        _shell_key_cache.pop("miss_quick", None)
        return google_only
    _shell_key_cache["miss_quick" if quick else "miss"] = time.time()
    _shell_key_cache.pop("hit", None)
    return None


def _registry_key(name: str) -> tuple[str, str] | None:
    """Windows: the user (then system) environment variable as saved in the registry."""
    import winreg

    locations = (
        (winreg.HKEY_CURRENT_USER, r"Environment", "使用者"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", "系統"),
    )
    for hive, subkey, label in locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                raw, kind = winreg.QueryValueEx(key, name)
        except OSError:
            continue
        if kind == winreg.REG_EXPAND_SZ:
            raw = winreg.ExpandEnvironmentStrings(raw)
        value = _clean_key(raw)
        if value:
            return value, f"Windows {label}環境變數 {name}"
    return None


def _saved_keys(fresh: bool = False, quick: bool = False) -> list[tuple[str, str, str]]:
    """Keys the user saved for future programs: [(name, value, where)], GEMINI_API_KEY first."""
    out = []
    if sys.platform == "win32":
        for name in _KEY_NAMES:
            found = _registry_key(name)
            if found:
                out.append((name, found[0], found[1]))
    else:
        found = _key_from_login_shell(use_cache=not fresh, quick=quick and not fresh)
        if found:
            out.append(("GOOGLE_API_KEY" if found[1].endswith("GOOGLE_API_KEY") else "GEMINI_API_KEY",
                        found[0], found[1]))
    return out


def find_api_key(fresh: bool = False) -> tuple[str, str]:
    """Return (key, where it was found). Never returns or logs the key anywhere else.

    The Claude app copies the environment once, when it starts, so a key the user saves
    afterwards (or replaces) only reaches Claude after a full restart. To make a newly saved
    key work at once, the saved value wins over the process environment:
      * Windows: GEMINI_API_KEY from the registry (user, then system), then the environment.
      * macOS/Linux: GEMINI_API_KEY from the user's shell startup files (looked up at most once
        a minute; fresh=True forces a new lookup), then the environment.
    GOOGLE_API_KEY is only a fallback when GEMINI_API_KEY is set nowhere.
    """
    env_vals = {n: _clean_key(os.environ.get(n)) for n in _KEY_NAMES}
    saved: dict[str, str] = {}
    where_saved: dict[str, str] = {}
    if sys.platform == "win32":
        for n, v, w in _saved_keys():
            saved[n], where_saved[n] = v, w
        order = [("GEMINI_API_KEY", "saved"), ("GEMINI_API_KEY", "env"),
                 ("GOOGLE_API_KEY", "saved"), ("GOOGLE_API_KEY", "env")]
    else:
        for n, v, w in _saved_keys(fresh=fresh, quick=bool(env_vals["GEMINI_API_KEY"])):
            saved[n], where_saved[n] = v, w
        order = [("GEMINI_API_KEY", "saved"), ("GEMINI_API_KEY", "env"),
                 ("GOOGLE_API_KEY", "env"), ("GOOGLE_API_KEY", "saved")]
    for name, src in order:
        value = saved.get(name) if src == "saved" else env_vals.get(name)
        if value:
            _last_keys.add(value)
            return value, (where_saved[name] if src == "saved" else f"環境變數 {name}")
    raise TTSError(NO_KEY_MSG)


def redact(text: str) -> str:
    """Hide any API key value that might have slipped into a message."""
    text = str(text)
    for value in list(_last_keys) + [_clean_key(os.environ.get(n)) for n in _KEY_NAMES]:
        if value and len(value) >= 8:
            text = text.replace(value, "***")
    return text


def get_client(key: str | None = None) -> Any:
    if key is None:
        key, _ = find_api_key()
    client = _clients.get(key)
    if client is None:
        from google import genai
        from google.genai import types

        # The SDK must not retry 429s: it would sleep for the server's Retry-After
        # (hours on a daily quota). 5xx errors may still get one quick SDK retry.
        http_options = types.HttpOptions(
            timeout=REQUEST_TIMEOUT_S * 1000,
            retry_options=types.HttpRetryOptions(attempts=1, http_status_codes=[500, 502, 503, 504]),
        )
        client = genai.Client(api_key=key, http_options=http_options)
        _clients[key] = client
    return client


# ---------------------------------------------------------------- usage ledger


def _pacific_now() -> datetime:
    """Current US Pacific time (quota day); DST rule computed by hand, no tz database needed."""
    now = datetime.now(timezone.utc)
    year = now.year

    def nth_sunday(month: int, n: int) -> datetime:
        first = datetime(year, month, 1, tzinfo=timezone.utc)
        return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))

    dst_start = nth_sunday(3, 2) + timedelta(hours=10)  # 02:00 PST
    dst_end = nth_sunday(11, 1) + timedelta(hours=9)    # 02:00 PDT
    offset = -7 if dst_start <= now < dst_end else -8
    return now + timedelta(hours=offset)


def _next_reset_local() -> datetime:
    """Local wall-clock time of the next Pacific midnight (daily quota reset)."""
    pt = _pacific_now()
    midnight = datetime(pt.year, pt.month, pt.day) + timedelta(days=1)
    return datetime.now() + (midnight - pt.replace(tzinfo=None))


def _load_usage() -> dict[str, Any]:
    try:
        return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _key_tag() -> str:
    """Short fingerprint of the API key in use (sha256, first 8 hex) - counts are kept per key, the key is never stored."""
    import hashlib
    try:
        key, _ = find_api_key()
    except TTSError:
        return "nokey"
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def usage_today(model: str) -> int:
    day = _load_usage().get(_pacific_now().strftime("%Y-%m-%d"), {})
    return int(day.get(_key_tag(), {}).get(model, 0))


def _record_usage(model: str) -> None:
    day = _pacific_now().strftime("%Y-%m-%d")
    data = _load_usage()
    data = {d: v for d, v in data.items() if d >= (_pacific_now() - timedelta(days=30)).strftime("%Y-%m-%d")}
    per_key = data.setdefault(day, {}).setdefault(_key_tag(), {})
    per_key[model] = int(per_key.get(model, 0)) + 1
    try:
        USAGE_FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")
    except OSError:
        pass


def _usage_fields(model: str) -> dict[str, Any]:
    used = usage_today(model)
    limit = FREE_DAILY_LIMITS.get(model)
    out: dict[str, Any] = {"used_today": used}
    if limit:
        out["free_daily_limit"] = limit
        if used >= limit - 2:
            out["quota_note"] = (
                f"今天已用 {used}/{limit} 次免費額度（本機紀錄），"
                f"將在 {_next_reset_local():%m/%d %H:%M} 重置。"
            )
    return out


# ---------------------------------------------------------------- errors / retries


def _status_code(exc: BaseException) -> int | None:
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    value = getattr(getattr(exc, "response", None), "status_code", None)
    return value if isinstance(value, int) else None


def _friendly(exc: BaseException) -> TTSError:
    code = _status_code(exc)
    msg = redact(str(exc))
    low = msg.lower()
    if "api key not valid" in low or "api_key_invalid" in low or "invalid api key" in low:
        return TTSError(
            "API Key 無效：請確認 GEMINI_API_KEY 的值沒有貼錯（前後不要有空白或引號），"
            "或到 https://aistudio.google.com/apikey 重新建立。"
        )
    if code == 429 or "resource_exhausted" in low:
        if _is_daily_quota(exc):
            wait_s = _retry_after_s(exc)
            reset = datetime.now() + timedelta(seconds=wait_s) if wait_s else _next_reset_local()
            left = max(0, int((reset - datetime.now()).total_seconds()))
            limit = re.search(r"limit:\s*(\d+)", msg)
            free = "free" in low
            if limit and limit.group(1) == "0":
                return TTSError(
                    f"這個專案目前沒有 {_model_in(msg) or '這個模型'} 的{'免費' if free else ''}額度（Google 回報上限 0 次），"
                    "等待重置也不會改善。請到 https://aistudio.google.com/projects 確認專案是否需要驗證、"
                    "或開通付費；也可以改用 gemini-3.8-flash-lite-tts。"
                    f"\n原始訊息：{msg[:300]}"
                )
            return TTSError(DAILY_QUOTA_MSG.format(
                kind="免費額度" if free else "每日額度",
                advice=DAILY_ADVICE_FREE if free else DAILY_ADVICE_PAID,
                model=_model_in(msg) or "這個模型",
                limit=limit.group(1) if limit else "?",
                reset=f"{reset:%m/%d %H:%M}（本機時間）",
                wait=f"{left // 3600} 小時 {left % 3600 // 60} 分",
            ))
        reset_at = f"{_next_reset_local():%m/%d %H:%M}"
        return TTSError(f"{QUOTA_MSG.format(reset=reset_at)}\n原始訊息：{msg[:300]}")
    if code == 402:
        return TTSError(f"{PREPAID_EMPTY_MSG}\n原始訊息：{msg[:300]}")
    if "location is not supported" in low or "user location" in low:
        return TTSError(
            "Google 目前不在你所在的地區提供 Gemini API（400，location is not supported）。"
            "這不是金鑰的問題，換新金鑰也沒有用；請改在 Gemini API 支援的地區使用。"
            f"\n原始訊息：{msg[:300]}"
        )
    if "free_tier_verification_required" in low or ("verification" in low and code == 403):
        return TTSError(
            "Google 要求先驗證這個專案才能使用免費額度（403）：到 https://aistudio.google.com/projects "
            "按「Verify project」→「Verify device」，用手機掃 QR code 完成（不需要電話號碼）。"
            f"\n原始訊息：{msg[:300]}"
        )
    if "reported as leaked" in low:
        return TTSError(
            "這把 API Key 已被 Google 判定外洩並停用（403）。請到 https://aistudio.google.com/apikey "
            "建立新金鑰、重新設定環境變數，並刪除舊金鑰。"
            f"\n原始訊息：{msg[:300]}"
        )
    if code in (401, 403):
        return TTSError(
            f"API Key 沒有權限使用這個模型（{code}）。可能原因：金鑰被停用或封鎖、帳單逾期、"
            "或不是在 AI Studio 建立的 Gemini API Key。請到 https://aistudio.google.com/apikey 檢查，"
            "必要時建立新金鑰。"
            f"\n原始訊息：{msg[:300]}"
        )
    if code == 404:
        return TTSError(
            f"找不到模型或 API（404），請確認模型名稱，以及 google-genai 版本為 2.34 以上、3.0 以下。"
            f"\n原始訊息：{msg[:300]}"
        )
    return TTSError(f"Gemini API 錯誤（{code or type(exc).__name__}）：{msg[:500]}")


def _retry_after_s(exc: BaseException) -> float | None:
    """Seconds the server asks us to wait (Retry-After header, else 'retry in 11h43m30s')."""
    for attr in ("response", "raw_response"):
        headers = getattr(getattr(exc, attr, None), "headers", None)
        value = headers.get("retry-after") if headers is not None else None
        if value:
            try:
                return float(value)
            except ValueError:
                pass
    m = re.search(r"retry in\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:([\d.]+)s)?", str(exc), re.I)
    if m and any(m.groups()):
        h, mi, s = (float(g) if g else 0.0 for g in m.groups())
        return h * 3600 + mi * 60 + s
    return None


def _is_daily_quota(exc: BaseException) -> bool:
    squashed = re.sub(r"[\s_-]", "", str(exc).lower())
    wait = _retry_after_s(exc)
    return "perday" in squashed or (wait is not None and wait > 600)


def _model_in(msg: str) -> str | None:
    m = re.search(r"(gemini-[\w.-]*tts)", msg)
    return m.group(1) if m else None


def _call_with_deadline(fn: Any, seconds: float) -> Any:
    """Run fn in a daemon thread; give up after `seconds` no matter what the SDK is doing."""
    box: dict[str, Any] = {}

    def run() -> None:
        try:
            box["ok"] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised in the caller's thread
            box["err"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        raise TTSError(TIMEOUT_MSG.format(seconds=int(seconds)))
    if "err" in box:
        raise box["err"]
    return box.get("ok")


def _create(**body: Any) -> Any:
    client = get_client()
    for attempt in range(len(RETRY_DELAYS_S) + 1):
        try:
            return _call_with_deadline(
                lambda: client.interactions.create(timeout=REQUEST_TIMEOUT_S, **body), HARD_DEADLINE_S
            )
        except TTSError:
            raise
        except Exception as exc:  # SDK raises several error types
            code = _status_code(exc)
            if code == 429 and _is_daily_quota(exc):
                raise _friendly(exc) from exc  # daily quota: fail at once, with the reset time
            retryable = code == 429 or code in (500, 502, 503, 504)
            if retryable and attempt < len(RETRY_DELAYS_S):
                wait = _retry_after_s(exc)
                time.sleep(min(wait, MAX_RETRY_WAIT_S) if wait else RETRY_DELAYS_S[attempt])
                continue
            raise _friendly(exc) from exc
    raise AssertionError("unreachable")


# ---------------------------------------------------------------- text splitting

_CJK_RE = re.compile(
    "[　-ヿ㐀-䶿一-鿿가-힯豈-﫿＀-￯"
    "\U00020000-\U0003134f]"
)
_SENT_END = set("。！？!?；;…\n")
_CLOSERS = set("。！？!?…」』”’）)】》\"'")


def _units(s: str) -> float:
    cjk = len(_CJK_RE.findall(s))
    return cjk + (len(s) - cjk) / 3


def _split_sentences(text: str) -> list[str]:
    out: list[str] = []
    start = i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in _SENT_END or (ch == "." and (i + 1 == n or text[i + 1].isspace())):
            j = i + 1
            while j < n and text[j] in _CLOSERS:
                j += 1
            out.append(text[start:j])
            start = i = j
            continue
        i += 1
    if start < n:
        out.append(text[start:])
    return [s for s in out if s.strip()]


def _cut_index(s: str, limit: float) -> int:
    units, idx = 0.0, 0
    for i, ch in enumerate(s):
        units += 1.0 if _CJK_RE.match(ch) else 1 / 3
        if units > limit:
            break
        idx = i + 1
    lt, gt = s.rfind("<", 0, idx), s.rfind(">", 0, idx)
    if lt > gt and lt > 0:  # never cut inside an <inline tag>
        idx = lt
    return max(idx, 1)


def _hard_split(sentence: str, limit: float) -> list[str]:
    out: list[str] = []
    cur = ""
    for part in re.split(r"(?<=[，,、：:])", sentence):
        if not part:
            continue
        if _units(cur + part) <= limit:
            cur += part
            continue
        if cur:
            out.append(cur)
            cur = ""
        while _units(part) > limit:
            cut = _cut_index(part, limit)
            out.append(part[:cut])
            part = part[cut:]
        cur = part
    if cur:
        out.append(cur)
    return out


def split_text(text: str, limit: float = CHUNK_UNITS) -> list[str]:
    """Split a long script into request-sized chunks at natural boundaries."""
    text = text.strip()
    if _units(text) <= limit:
        return [text]
    pieces: list[tuple[int, str]] = []  # (paragraph index, piece)
    for p_idx, para in enumerate(re.split(r"\n\s*\n", text)):
        if not para.strip():
            continue
        if _units(para) <= limit:
            pieces.append((p_idx, para.strip()))
            continue
        for sentence in _split_sentences(para):
            if _units(sentence) <= limit:
                pieces.append((p_idx, sentence))
            else:
                pieces.extend((p_idx, part) for part in _hard_split(sentence, limit))
    chunks: list[str] = []
    cur, cur_units, cur_para = "", 0.0, None
    for p_idx, piece in pieces:
        units = _units(piece)
        if cur and cur_units + units > limit:
            chunks.append(cur.strip())
            cur, cur_units = "", 0.0
        if cur:
            cur += "" if p_idx == cur_para else "\n\n"
        cur += piece
        cur_units += units
        cur_para = p_idx
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


# ---------------------------------------------------------------- audio helpers


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _audio_blocks(interaction: Any) -> list[Any]:
    """All audio blocks in order.

    interaction.output_audio holds only the LAST block, which drops audio when the
    SDK stitches several continuation hops together, so walk every step instead.
    """
    blocks = []
    for step in _get(interaction, "steps") or []:
        if _get(step, "type") != "model_output":
            continue
        for item in _get(step, "content") or []:
            if _get(item, "type") == "audio" and _get(item, "data"):
                blocks.append(item)
    if not blocks:
        fallback = _get(interaction, "output_audio")
        if fallback is not None and _get(fallback, "data"):
            blocks.append(fallback)
    return blocks


def _decode_pcm(block: Any) -> tuple[bytes, int, int]:
    """Return (16-bit little-endian PCM, sample rate, channels) for one audio block."""
    raw = base64.b64decode(_get(block, "data"))
    if raw[:4] == b"RIFF":
        with wave.open(io.BytesIO(raw), "rb") as w:
            if w.getsampwidth() != 2:
                raise TTSError(f"不支援的音訊位元深度：{w.getsampwidth() * 8}-bit")
            return w.readframes(w.getnframes()), w.getframerate(), w.getnchannels()
    mime = _get(block, "mime_type")
    mime = str(getattr(mime, "value", mime) or "").lower()
    if mime and not any(t in mime for t in ("l16", "pcm", "wav")):
        raise TTSError(f"不支援的音訊格式：{mime}")
    return raw, int(_get(block, "sample_rate") or 24000), int(_get(block, "channels") or 1)


def _text_part(text: str, style: str = "", speaker: str | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {"type": "speech_metadata", "style": style or ""}
    if speaker:
        meta["speaker"] = speaker
    return {"type": "text", "text": text, "annotations": [meta]}


def _request_pcm(model: str, content: list[dict], speech_config: Any) -> tuple[bytes, int, int]:
    interaction = _create(
        model=model,
        input=[{"type": "user_input", "content": content}],
        response_format={"type": "audio"},
        generation_config={"speech_config": speech_config},
    )
    _record_usage(model)
    blocks = _audio_blocks(interaction)
    if not blocks:
        status = _get(interaction, "status")
        raise TTSError(f"API 沒有回傳音訊（status={status}），可能被安全機制擋下，請修改文字後再試。")
    pcm = bytearray()
    fmt: tuple[int, int] | None = None
    for block in blocks:
        data, rate, channels = _decode_pcm(block)
        if fmt is None:
            fmt = (rate, channels)
        elif fmt != (rate, channels):
            raise TTSError("回傳的音訊片段格式不一致，無法合併。")
        pcm += data
    assert fmt is not None
    return bytes(pcm), fmt[0], fmt[1]


def _render(model: str, jobs: list[tuple[list[dict], Any]]) -> tuple[list[bytes], int, int]:
    parts: list[bytes] = []
    fmt: tuple[int, int] | None = None
    for content, speech_config in jobs:
        pcm, rate, channels = _request_pcm(model, content, speech_config)
        if fmt is None:
            fmt = (rate, channels)
        elif fmt != (rate, channels):
            raise TTSError("各段音訊格式不一致，無法合併。")
        parts.append(pcm)
    assert fmt is not None
    return parts, fmt[0], fmt[1]


# Only folder-like variables may be used in output paths. Expanding arbitrary variables would
# let a path such as "%GEMINI_API_KEY%.wav" copy a secret into a file name returned to the model.
_PATH_VARS = {"USERPROFILE", "HOMEDRIVE", "HOMEPATH", "HOME", "ONEDRIVE", "LOCALAPPDATA", "APPDATA",
              "TEMP", "TMP", "PUBLIC", "USERNAME", "USER"}
_VAR_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)%|\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _expand_path_vars(raw: str) -> str:
    def sub(m: re.Match) -> str:
        name = m.group(1) or m.group(2) or m.group(3)
        value = os.environ.get(name) or os.environ.get(name.upper())
        if value is None:
            return m.group(0)          # not a variable here: keep the text as typed
        if name.upper() in _PATH_VARS:
            return value
        raise TTSError(f"輸出路徑不能使用環境變數 {m.group(0)}，請改用完整的絕對路徑。")
    return _VAR_RE.sub(sub, raw)


def _resolve_output(output_path: str, overwrite: bool) -> Path:
    stamp = f"tts_{datetime.now():%Y%m%d_%H%M%S}.wav"
    raw = (output_path or "").strip().strip('"')
    if raw:
        path = Path(_expand_path_vars(raw)).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        if raw.endswith(("/", "\\")) or path.is_dir():
            path = path / stamp
    else:
        path = DEFAULT_OUTPUT_DIR / stamp
    if path.suffix.lower() != ".wav":
        audio_exts = {".mp3", ".m4a", ".aac", ".ogg", ".flac", ".opus", ".pcm", ".wave"}
        if path.suffix.lower() in audio_exts:
            path = path.with_suffix(".wav")
        else:
            path = path.with_name(path.name + ".wav")
    if path.exists() and not overwrite:
        i = 1
        while (candidate := path.with_name(f"{path.stem}_{i}{path.suffix}")).exists():
            i += 1
        path = candidate
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise TTSError(f"無法建立資料夾 {path.parent}：{exc}") from exc
    return path


def _write_wav(path: Path, parts: list[bytes], rate: int, channels: int) -> float:
    gap = b"\x00\x00" * channels * int(rate * GAP_MS / 1000)
    pcm = gap.join(parts)
    tmp = path.with_name(path.name + ".part")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    os.replace(tmp, path)
    return len(pcm) / (2 * channels * rate)


def _check_model(model: str) -> str:
    model = (model or DEFAULT_MODEL).strip()
    if model.lower() in ("lite", "flash-lite"):
        return LITE_MODEL
    if model not in SUPPORTED_MODELS:
        raise TTSError(f"不支援的模型「{model}」，可用：{', '.join(SUPPORTED_MODELS)}")
    return model


def normalize_voice(voice: str) -> str:
    voice = (voice or "").strip() or DEFAULT_VOICE
    for name in PREBUILT_VOICES:
        if name.lower() == voice.lower():
            return name
    return voice


def _is_custom_voice(voice: str) -> bool:
    return voice.startswith(("voice_", "voicekey_"))


# ---------------------------------------------------------------- public API


def synthesize(
    text: str,
    voice: str = DEFAULT_VOICE,
    style: str = "",
    model: str = DEFAULT_MODEL,
    output_path: str = "",
    overwrite: bool = False,
    play: bool = False,
    wait: bool = False,
) -> dict[str, Any]:
    """Single-speaker speech -> WAV file. Long text is split and joined automatically."""
    text = (text or "").strip()
    if not text:
        raise TTSError("text 是空的，沒有可以念的內容。")
    model = _check_model(model)
    voice = normalize_voice(voice)
    style = (style or "").strip()
    path = _resolve_output(output_path, overwrite)
    chunks = split_text(text)
    jobs = [([_text_part(chunk, style)], [{"voice": voice}]) for chunk in chunks]
    parts, rate, channels = _render(model, jobs)
    duration = _write_wav(path, parts, rate, channels)
    if play:
        play_audio(path, wait=wait)
    return {
        "path": str(path),
        "duration_seconds": round(duration, 2),
        "requests": len(jobs),
        "model": model,
        "voice": voice,
        "style": style,
        "characters": len(text),
        "played": play,
        **_usage_fields(model),
    }


def synthesize_dialogue(
    turns: list[Any],
    speaker_voices: dict[str, str],
    model: str = DEFAULT_MODEL,
    output_path: str = "",
    overwrite: bool = False,
    play: bool = False,
    wait: bool = False,
) -> dict[str, Any]:
    """Multi-speaker dialogue -> one WAV file.

    Two speakers with non-custom voices are rendered natively (one request per
    ~CHUNK_UNITS of script). Otherwise each run of turns by the same speaker is
    rendered separately and the pieces are joined.
    """
    if not turns:
        raise TTSError("turns 是空的，沒有對話內容。")
    model = _check_model(model)
    voices = {str(k).strip(): normalize_voice(v) for k, v in (speaker_voices or {}).items()}
    lines: list[tuple[str, str, str]] = []
    for i, turn in enumerate(turns, 1):
        speaker = str(_get(turn, "speaker") or "").strip()
        text = str(_get(turn, "text") or "").strip()
        style = str(_get(turn, "style") or "").strip()
        if not speaker or not text:
            raise TTSError(f"第 {i} 句缺少 speaker 或 text。")
        if speaker not in voices:
            raise TTSError(f"第 {i} 句的說話者「{speaker}」沒有在 speaker_voices 指定聲音。")
        lines.extend((speaker, piece, style) for piece in split_text(text))
    used = list(dict.fromkeys(speaker for speaker, _, _ in lines))
    native = len(used) == 2 and not any(_is_custom_voice(voices[s]) for s in used)

    jobs: list[tuple[list[dict], Any]] = []
    if native:
        config = {"speakers": [{"speaker": s, "voice": voices[s]} for s in used]}
        group: list[tuple[str, str, str]] = []
        group_units = 0.0
        for line in lines:
            units = _units(line[1])
            if group and group_units + units > CHUNK_UNITS:
                jobs.append(([_text_part(t, st, sp) for sp, t, st in group], config))
                group, group_units = [], 0.0
            group.append(line)
            group_units += units
        if group:
            jobs.append(([_text_part(t, st, sp) for sp, t, st in group], config))
    else:
        merged: list[list[str]] = []  # consecutive lines with same speaker+style share a request
        for speaker, text, style in lines:
            last = merged[-1] if merged else None
            if last and last[0] == speaker and last[2] == style and _units(last[1] + text) <= CHUNK_UNITS:
                last[1] += "\n" + text
            else:
                merged.append([speaker, text, style])
        jobs = [([_text_part(t, st)], [{"voice": voices[sp]}]) for sp, t, st in merged]

    path = _resolve_output(output_path, overwrite)
    parts, rate, channels = _render(model, jobs)
    duration = _write_wav(path, parts, rate, channels)
    if play:
        play_audio(path, wait=wait)
    return {
        "path": str(path),
        "duration_seconds": round(duration, 2),
        "requests": len(jobs),
        "mode": "native_two_speaker" if native else "per_speaker_turn",
        "model": model,
        "speakers": {s: voices[s] for s in used},
        "turns": len(turns),
        "played": play,
        **_usage_fields(model),
    }


def _plain(value: Any) -> Any:
    value = getattr(value, "value", value)
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def list_voices(
    search: str = "",
    language_code: list[str] | str | None = None,
    gender: list[str] | str | None = None,
    accent: list[str] | str | None = None,
    voice_type: list[str] | str | None = None,
    page_size: int = 30,
) -> dict[str, Any]:
    """Search the voice catalog (prebuilt, Extended Voice Library and custom voices)."""

    def as_list(v: Any) -> list[str]:
        return [v] if isinstance(v, str) else list(v)

    page_size = max(1, min(int(page_size or 30), 200))
    kwargs: dict[str, Any] = {"page_size": page_size}
    if search:
        kwargs["search"] = search
    if language_code:
        kwargs["language_code"] = as_list(language_code)
    if gender:
        kwargs["gender"] = as_list(gender)
    if accent:
        kwargs["accent"] = as_list(accent)
    if voice_type:
        kwargs["type_"] = as_list(voice_type)
    client = get_client()
    try:
        response = client.voices.list(**kwargs)
    except Exception as exc:
        raise _friendly(exc) from exc
    items = _get(response, "voices")
    # A pydantic response is itself iterable (field/value pairs), so only fall back
    # to iterating when the SDK hands back a plain list.
    if items is None and isinstance(response, list):
        items = list(islice(response, page_size))
    fields = ("id", "display_name", "language_code", "region_code", "accent", "gender",
              "pitch", "persona", "context", "type", "description")
    voices = []
    for voice in items or []:
        entry = {f: _plain(_get(voice, f)) for f in fields}
        voices.append({k: v for k, v in entry.items() if v not in (None, "", [])})
    return {"voices": voices, "count": len(voices), "next_page_token": _get(response, "next_page_token")}


def play_audio(path: str | Path, wait: bool = False) -> None:
    """Play a WAV file on the default output device."""
    global _player
    p = Path(path).expanduser()
    if not p.is_file():
        raise TTSError(f"找不到音檔：{p}")
    if sys.platform == "win32":
        import winsound

        flags = winsound.SND_FILENAME | (0 if wait else winsound.SND_ASYNC)
        winsound.PlaySound(str(p), flags)
        return
    import subprocess

    stop_audio()  # one sound at a time, like winsound
    cmd = _player_cmd(p)
    _player = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if wait:
        _player.wait()


_player: Any = None


def _player_cmd(p: Path) -> list[str]:
    """Command line that plays a WAV file (macOS: built-in afplay; else ffplay / paplay / aplay)."""
    import shutil

    if sys.platform == "darwin" and os.path.exists("/usr/bin/afplay"):
        return ["/usr/bin/afplay", str(p)]
    ffplay = shutil.which("ffplay") or next(
        (c for c in ("/opt/homebrew/bin/ffplay", "/usr/local/bin/ffplay") if os.path.exists(c)), None
    )
    if ffplay:
        return [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet", str(p)]
    for alt in ("paplay", "aplay"):
        found = shutil.which(alt)
        if found:
            return [found, str(p)]
    raise TTSError("找不到播放程式：macOS 內建 afplay；其他系統請安裝 ffmpeg（含 ffplay）。")


def _player_name() -> str:
    if sys.platform == "win32":
        return "winsound（Windows 內建）"
    try:
        return Path(_player_cmd(Path("x.wav"))[0]).name
    except TTSError:
        return "找不到（無法播放，但仍可產生 WAV 檔）"


def stop_audio() -> None:
    if sys.platform == "win32":
        import winsound

        winsound.PlaySound(None, 0)
        return
    global _player
    if _player is not None and _player.poll() is None:
        _player.terminate()
        try:
            _player.wait(timeout=3)
        except Exception:
            _player.kill()
    _player = None


def verify_key(key: str | None = None) -> dict[str, Any]:
    """Make one cheap metadata call (models.get, not speech generation) to prove the key works.

    Uses no text-to-speech quota and never returns the key. key_valid is True (works),
    False (Google rejected the key) or None (could not tell: network trouble, timeout, 5xx).
    It only proves the key authenticates; project verification or billing problems show up
    on the first speech request.
    """
    if key is None:
        key, _ = find_api_key(fresh=True)
    client = get_client(key)
    try:
        model = _call_with_deadline(lambda: client.models.get(model=DEFAULT_MODEL), 60)
    except TTSError as exc:
        return {"key_valid": None, "key_error": str(exc)}
    except Exception as exc:
        code = _status_code(exc)
        low = str(exc).lower()
        friendly = str(_friendly(exc))
        if "location is not supported" in low or "user location" in low:
            return {"key_valid": None, "key_error": friendly}
        if code in (401, 403) or any(s in low for s in ("api key not valid", "api_key_invalid", "invalid api key",
                                                          "reported as leaked", "api key expired")):
            return {"key_valid": False, "key_error": friendly}
        return {"key_valid": None,
                "key_error": "無法確認金鑰（可能是網路或 Google 暫時異常，不一定是金鑰的問題）：" + friendly}
    return {"key_valid": True, "model_checked": getattr(model, "name", None) or DEFAULT_MODEL}


def check_setup(verify: bool = False) -> dict[str, Any]:
    """Report versions, settings and whether an API key is reachable (never returns the key).

    verify=True also makes one metadata call to Google to confirm the key works (no TTS quota used).
    """
    import platform
    from importlib.metadata import PackageNotFoundError, version

    info: dict[str, Any] = {
        "tool_version": __version__,
        "platform": f"{platform.system()} {platform.release()} ({sys.platform})",
        "python_version": platform.python_version(),
        "install_dir": str(HERE),
        "default_model": DEFAULT_MODEL,
        "default_output_dir": str(DEFAULT_OUTPUT_DIR),
        "audio_player": _player_name(),
        "tier": TIER,
        "settings_file": str(SETTINGS_FILE) + ("" if SETTINGS_FILE.exists() else "（尚未建立，使用預設：免費版）"),
    }
    for pkg in ("google-genai", "mcp"):
        try:
            info[f"{pkg.replace('-', '_')}_version"] = version(pkg)
        except PackageNotFoundError:
            info[f"{pkg.replace('-', '_')}_version"] = None
    key = None
    try:
        key, source = find_api_key(fresh=True)
        info["api_key_found"] = True
        info["api_key_source"] = source
    except TTSError as exc:
        info["api_key_found"] = False
        info["how_to_fix"] = str(exc)
    env_gemini = _clean_key(os.environ.get("GEMINI_API_KEY"))
    env_google = _clean_key(os.environ.get("GOOGLE_API_KEY"))
    if key and env_gemini and env_gemini != key:
        info["key_note"] = (
            "Claude 啟動時帶的是另一把（舊的）金鑰；Gemini TTS 已改用你剛存的金鑰。"
            "請找時間完全結束 Claude 再打開，讓其他程式也用新金鑰。"
        )
    if key and "GOOGLE_API_KEY" in info.get("api_key_source", ""):
        info["key_warning"] = (
            "目前用的是 GOOGLE_API_KEY（找不到 GEMINI_API_KEY）。建議照安裝包 docs 的說明設定 GEMINI_API_KEY。"
        )
    elif env_gemini and env_google and env_gemini != env_google:
        info["key_warning"] = (
            "GEMINI_API_KEY 和 GOOGLE_API_KEY 都有設定而且不一樣。這個工具用 GEMINI_API_KEY，"
            "但其他 Google 工具會優先用 GOOGLE_API_KEY；建議只保留 GEMINI_API_KEY。"
        )
    if verify and key:
        info.update(verify_key(key))
    info["used_today_local_count"] = {m: usage_today(m) for m in SUPPORTED_MODELS}
    info["free_daily_limits"] = FREE_DAILY_LIMITS
    info["quota_resets_at_local"] = f"{_next_reset_local():%m/%d %H:%M}"
    info["quota_note"] = (
        "本機只記錄這個工具成功送出的次數（同一把金鑰在其他電腦的用量不會算進來）；"
        "實際額度以 https://aistudio.google.com/rate-limit 為準。"
        + ("目前設定為付費（settings.json 的 tier 為 paid）：每次請求從預付金扣款，上限以 AI Studio 顯示為準；"
           "預付餘額用完時 API 會回 402 並停止。"
           if TIER == "paid" else
           "目前設定為免費版：每日上限見 free_daily_limits，在美國太平洋時間午夜重置；"
           "已開通付費的話，請把 settings.json 的 tier 改成 paid。")
    )
    return info


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    ap = argparse.ArgumentParser(description="Gemini 3.8 Flash TTS：文字轉語音（WAV）")
    ap.add_argument("text", nargs="?", help="要念的文字")
    ap.add_argument("--file", help="從 UTF-8 文字檔讀取稿子")
    ap.add_argument("--dialogue", help='對話 JSON：{"speakers": {名字: 聲音}, "turns": [{"speaker","text","style"}]}')
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--style", default="")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("-o", "--out", default="", help="輸出 .wav 路徑")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--play", action="store_true", help="存檔後播放")
    ap.add_argument("--list-voices", action="store_true")
    ap.add_argument("--search", default="")
    ap.add_argument("--language-code", nargs="*")
    ap.add_argument("--gender", nargs="*")
    ap.add_argument("--check", action="store_true", help="檢查 API Key 與 SDK（不連網、不顯示金鑰）")
    ap.add_argument("--verify-key", action="store_true",
                    help="同 --check，另外向 Google 查一次模型資訊來確認金鑰有效（不使用語音額度）")
    ap.add_argument("--version", action="version", version=f"gemini-tts {__version__}")
    a = ap.parse_args(argv)
    try:
        if a.check or a.verify_key:
            result = check_setup(verify=a.verify_key)
        elif a.list_voices:
            result = list_voices(a.search, a.language_code, a.gender)
        elif a.dialogue:
            data = json.loads(Path(a.dialogue).read_text(encoding="utf-8-sig"))
            result = synthesize_dialogue(
                data["turns"], data["speakers"], a.model, a.out, a.overwrite, a.play, wait=True
            )
        else:
            text = Path(a.file).read_text(encoding="utf-8-sig") if a.file else a.text
            if not text:
                ap.error("請提供文字、--file、--dialogue、--list-voices 或 --check")
            result = synthesize(text, a.voice, a.style, a.model, a.out, a.overwrite, a.play, wait=True)
    except (TTSError, OSError, KeyError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": redact(str(exc))}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
