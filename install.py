#!/usr/bin/env python3
"""Gemini TTS for Claude Code - cross-platform installer (Windows / macOS / Linux).

Run from the repository folder. Any Python 3.8+ can start it; it then finds a Python >= 3.11
for the tool itself:

    python install.py --tier free --verify-key      # or --tier paid
    python install.py --uninstall

What it does (and never does):
  * copies server/ -> ~/.claude/mcp-servers/gemini-tts/   (changed files are backed up first)
  * copies skill/  -> ~/.claude/skills/gemini-tts/
  * creates a Python virtual environment and installs the pinned requirements
  * registers the MCP server at user scope with the `claude` CLI (also finds the CLI bundled
    with the Claude desktop app)
  * runs the tool's self-check
  * NEVER reads, asks for, prints or stores the Gemini API key. The user sets it in the
    operating system's environment variables (see docs/ and scripts/).

The last line of output is machine-readable for the installing agent:
    GEMINI_TTS_INSTALL_RESULT {...json...}
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

MIN_PY = (3, 11)
MAX_TESTED_PY = (3, 14)   # newest Python the pinned packages were tested with; newer is used only if nothing else
PREFERRED_PY = tuple(f"3.{m}" for m in range(20, 10, -1))   # 3.20 ... 3.11, newest first
NAME = "gemini-tts"
REPO = Path(__file__).resolve().parent
RESULT_TAG = "GEMINI_TTS_INSTALL_RESULT"
REQ_MARK = ".gemini-tts-requirements.sha256"

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"


def say(msg: str = "") -> None:
    print(msg, flush=True)


def step(msg: str) -> None:
    say(f"\n==> {msg}")


def finish(result: dict, code: int) -> None:
    result["exit_code"] = code
    say("")
    say(f"{RESULT_TAG} {json.dumps(result, ensure_ascii=False)}")
    sys.exit(code)


def child_env() -> dict:
    """Environment for child processes: UTF-8 output, and never the API key."""
    env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def run(cmd: list, timeout: float | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(c) for c in cmd], stdin=subprocess.DEVNULL, timeout=timeout, env=env or child_env(),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


# ---------------------------------------------------------------- Python discovery


def py_version(cmd: list) -> tuple | None:
    """(major, minor, executable) of a candidate interpreter, or None if it does not run."""
    try:
        p = run(cmd + ["-c", "import sys; print(sys.version_info[0], sys.version_info[1], sys.executable)"], timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    parts = p.stdout.strip().split(" ", 2)
    if len(parts) != 3 or not parts[0].isdigit():
        return None
    return int(parts[0]), int(parts[1]), parts[2]


def mac_clt_installed() -> bool:
    """Without the Command Line Tools, /usr/bin/python3 and git only open an install dialog."""
    try:
        return run(["/usr/bin/xcode-select", "-p"], timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def python_candidates(explicit: str | None) -> list:
    cands: list = []
    if explicit:
        cands.append([explicit])
    cands.append([sys.executable])
    if IS_WIN:
        cands.append(["py", "-3"])
        for v in PREFERRED_PY:
            cands.append(["py", f"-{v}"])
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "Programs" / "Python"
        for v in PREFERRED_PY:
            cands.append([str(local / f"Python{v.replace('.', '')}" / "python.exe")])
        cands.append(["python"])
        cands.append(["python3"])
    else:
        for v in PREFERRED_PY:
            cands.append([f"python{v}"])
            for prefix in ("/opt/homebrew/bin", "/usr/local/bin",
                           f"/Library/Frameworks/Python.framework/Versions/{v}/bin"):
                cands.append([f"{prefix}/python{v}"])
        for c in ("/opt/homebrew/bin/python3", "/usr/local/bin/python3"):
            cands.append([c])
        cands.append(["python3"])
    skip_stub = IS_MAC and not mac_clt_installed()
    out, seen = [], set()
    for c in cands:
        exe = c[0]
        if os.path.isabs(exe):
            if not os.path.exists(exe):
                continue
            resolved = exe
        else:
            resolved = shutil.which(exe)
            if not resolved:
                continue
        if skip_stub and os.path.realpath(resolved) == "/usr/bin/python3":
            continue  # would pop up the "install developer tools" dialog
        key = tuple(c)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def find_python(explicit: str | None) -> tuple | None:
    """Best interpreter >= 3.11 as (cmd, (major, minor), executable).

    Prefers the newest version up to MAX_TESTED_PY; a newer, untested one only when nothing else exists.
    """
    def rank(ver: tuple) -> tuple:
        return (ver <= MAX_TESTED_PY, ver if ver <= MAX_TESTED_PY else tuple(-x for x in ver))

    best = None
    for cmd in python_candidates(explicit):
        info = py_version(cmd)
        if not info:
            continue
        major, minor, exe = info
        if (major, minor) >= MIN_PY and (best is None or rank((major, minor)) > rank(best[1])):
            best = (cmd, (major, minor), exe)
        if explicit and best:
            break
    return best


def python_help() -> str:
    if IS_WIN:
        return (
            "這台 Windows 找不到 Python 3.11 以上的版本。安裝方式（擇一）：\n"
            "  1) 經使用者同意後，由 Claude 執行：\n"
            "     winget install -e --id Python.Python.3.13 --scope user --accept-source-agreements --accept-package-agreements\n"
            "  2) 使用者自己到 https://www.python.org/downloads/ 下載安裝（依網頁指示）。\n"
            "裝好後再執行一次安裝程式（INSTALL_FOR_CLAUDE.md 第 3 步會自動找到新裝的 Python，"
            "不需要重開 Claude）。"
        )
    if IS_MAC:
        return (
            "這台 Mac 找不到 Python 3.11 以上的版本（macOS 沒有內建可用的新版 Python）。安裝方式（擇一）：\n"
            "  1) 到 https://www.python.org/downloads/macos/ 找 Python 3.13.x（已測試的版本）的「macOS 64-bit universal2 installer」下載並安裝\n"
            "  2) 有 Homebrew 的話：brew install python@3.13\n"
            "裝好後再執行一次安裝程式。"
        )
    return "找不到 Python 3.11 以上的版本，請用系統的套件管理員安裝 python3.11+（含 venv 模組）。"


# ---------------------------------------------------------------- Claude CLI


def _version_key(path: str) -> tuple:
    """Sort key for bundled CLI copies: the x.y.z version folder as numbers, then file time."""
    nums: list = []
    m = re.findall(r"(\d+)\.(\d+)\.(\d+)", path)
    if m:
        nums = [int(x) for x in m[-1]]
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0
    return (tuple(nums), mtime)


def find_claude() -> str | None:
    """The `claude` CLI: PATH, standard install locations, or the copy bundled with the desktop app."""
    found = shutil.which("claude")
    if found:
        return found
    home = Path.home()
    exe = "claude.exe" if IS_WIN else "claude"
    fixed = [
        str(home / ".local" / "bin" / exe),
        str(home / ".claude" / "local" / exe),
        "/opt/homebrew/bin/claude", "/usr/local/bin/claude",
        str(home / ".npm-global" / "bin" / "claude"),
    ]
    if IS_WIN:
        fixed.append(os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"))
    for p in fixed:
        if p and os.path.isfile(p):
            return p
    # The desktop app keeps its own copy, e.g. %LOCALAPPDATA%\Claude-Data\claude_<id>\claude-code\<ver>\<hash>\claude.exe
    # (Windows) or ~/Library/Application Support/Claude/claude-code/<ver>/claude (macOS). Bounded depth, no deep scan.
    layouts = ("claude-code/*/{exe}", "claude-code/*/*/{exe}", "*/claude-code/*/{exe}", "*/claude-code/*/*/{exe}")
    roots: list = []
    if IS_WIN:
        local = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
        roaming = os.environ.get("APPDATA", str(home / "AppData" / "Roaming"))
        roots = [os.path.join(local, "Claude-Data"), os.path.join(local, "Claude"), os.path.join(local, "AnthropicClaude"),
                 os.path.join(roaming, "Claude")]
    elif IS_MAC:
        roots = [str(home / "Library" / "Application Support" / "Claude"),
                 str(home / "Library" / "Application Support" / "Claude-Data")]
    bundled: list = []
    for root in roots:
        for layout in layouts:
            bundled += [p for p in glob.glob(os.path.join(root, layout.format(exe=exe)))
                        if os.path.isfile(p) and (IS_WIN or os.access(p, os.X_OK))]
    if bundled:
        return max(bundled, key=_version_key)
    return None


def _quote(arg: str) -> str:
    return f'"{arg}"' if (" " in arg or "\\" in arg) else arg


def manual_register_cmd(claude: str | None, venv_py: Path, server: Path, scope: str, powershell: bool = False) -> str:
    """Remove-then-add command the user or agent can paste (bash form, or PowerShell form with &)."""
    exe = _quote(claude) if claude else "claude"
    if powershell:
        exe = f"& {exe}"
    remove = f"{exe} mcp remove {NAME} -s {scope}"
    add = f'{exe} mcp add --transport stdio --scope {scope} {NAME} -- "{venv_py}" "{server}"'
    return f"{remove}; {add}"


def rerun_powershell_cmd(args: argparse.Namespace) -> str:
    """A PowerShell line the user can paste to run this installer again without Claude."""
    extra = " --verify-key"
    if args.tier:
        extra += f" --tier {args.tier}"
    return f'& "{sys.executable}" -X utf8 "{REPO / "install.py"}"{extra}'


def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(p.strip().strip('"')))


def register_mcp(claude: str, scope: str, venv_py: Path, server: Path) -> dict:
    """Register (or re-register) the server. Returns {'ok', 'detail', 'removed_previous'}."""
    scope_label = {"user": "user", "project": "project", "local": "local"}[scope]
    try:  # is the same command already registered? (any problem here just means "re-register")
        current = run([claude, "mcp", "get", NAME], timeout=90)
        text = (current.stdout or "") + (current.stderr or "")
        m_scope = re.search(r"^\s*Scope:\s*(\w+)", text, re.M)
        m_cmd = re.search(r"^\s*Command:\s*(.+)$", text, re.M)
        m_args = re.search(r"^\s*Args:\s*(.+)$", text, re.M)
        if (current.returncode == 0 and m_scope and m_scope.group(1).lower() == scope_label
                and m_cmd and _norm(m_cmd.group(1)) == _norm(str(venv_py))
                and m_args and _norm(m_args.group(1)) == _norm(str(server))):
            return {"ok": True, "detail": "已經註冊過（指令相同），不需變更", "removed_previous": False}
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        removed = run([claude, "mcp", "remove", NAME, "-s", scope], timeout=90).returncode == 0
        add = run([claude, "mcp", "add", "--transport", "stdio", "--scope", scope, NAME, "--",
                   str(venv_py), str(server)], timeout=90)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "detail": f"執行 claude CLI 失敗：{exc}", "removed_previous": False}
    if add.returncode != 0:
        return {"ok": False, "detail": (add.stderr or add.stdout or "").strip()[:500], "removed_previous": removed}
    lines = (add.stdout or "").strip().splitlines()
    return {"ok": True, "detail": lines[0][:300] if lines else "", "removed_previous": removed}


# ---------------------------------------------------------------- install steps


def version_of(py_file: Path) -> str | None:
    try:
        m = re.search(r'^__version__\s*=\s*"([^"]+)"', py_file.read_text(encoding="utf-8"), re.M)
    except OSError:
        return None
    return m.group(1) if m else None


def backup_existing(pairs: list, srv: Path, stamp: str) -> Path | None:
    """Back up installed files that the new version will change. pairs = [(installed, new)]."""
    def same(a: Path, b: Path) -> bool:  # byte compare (filecmp caches by size+mtime, which can be stale)
        return b.is_file() and a.read_bytes() == b.read_bytes()

    changed = [(inst, new) for inst, new in pairs if inst.is_file() and not same(inst, new)]
    if not changed:
        return None
    old = version_of(srv / "gemini_tts.py") or "unknown"
    dest = srv / f"backup_v{old}_{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    for inst, _ in changed:
        shutil.copy2(inst, dest / inst.name)
    return dest


def copy_tree_files(src: Path, dst: Path) -> list:
    copied = []
    for f in sorted(src.rglob("*")):
        if f.is_dir() or "__pycache__" in f.parts:
            continue
        target = dst / f.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        copied.append(str(target))
    return copied


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if IS_WIN else "bin/python")


def venv_healthy(vpy: Path) -> tuple | None:
    """(major, minor) if the venv's Python runs, is new enough and has pip; else None."""
    if not vpy.exists():
        return None
    info = py_version([str(vpy)])
    if not info or (info[0], info[1]) < MIN_PY:
        return None
    try:
        if run([str(vpy), "-m", "pip", "--version"], timeout=60).returncode != 0:
            return None
    except (OSError, subprocess.TimeoutExpired):
        return None
    return info[0], info[1]


def ensure_venv(srv: Path, py_cmd: list | None, stamp: str) -> Path:
    venv = srv / ".venv"
    vpy = venv_python(venv)
    if os.path.lexists(str(venv)):
        ok = venv_healthy(vpy)
        if ok:
            say(f"沿用既有的虛擬環境：{venv}（Python {ok[0]}.{ok[1]}）")
            return vpy
        moved = srv / f".venv_old_{stamp}"
        say(f"既有虛擬環境無法使用（或版本太舊），改名保留為 {moved.name}，重新建立。")
        venv.rename(moved)
    if not py_cmd:
        raise RuntimeError("沒有可用的 Python 3.11+ 來建立虛擬環境。")
    say(f"建立虛擬環境：{venv}")
    p = run(py_cmd + ["-m", "venv", str(venv)], timeout=600)
    if p.returncode != 0 or not vpy.exists():
        raise RuntimeError("建立虛擬環境失敗：" + (p.stderr or p.stdout or "").strip()[:800]
                           + ("\n（Linux 可能要先安裝 python3-venv）" if not (IS_WIN or IS_MAC) else ""))
    return vpy


def requirements_hash(req: Path) -> str:
    return hashlib.sha256(req.read_bytes()).hexdigest()


def pip_install(vpy: Path, req: Path, venv: Path) -> bool:
    """Install the pinned requirements. Skipped when the venv already has exactly this list."""
    mark = venv / REQ_MARK
    want = requirements_hash(req)
    try:
        if mark.read_text(encoding="utf-8").strip() == want:
            say("套件已是最新（與 requirements.txt 相同），略過安裝。")
            return False
    except OSError:
        pass
    say("安裝套件（第一次約需 1–3 分鐘）…")
    cmd = [str(vpy), "-m", "pip", "install", "--prefer-binary", "-r", str(req)]
    if IS_WIN and platform.machine().upper() in ("ARM64", "AARCH64"):
        cmd += ["--only-binary=cryptography"]  # no win_arm64 wheel for the newest cryptography
    p = subprocess.run(cmd, stdin=subprocess.DEVNULL, env=child_env(), timeout=1800)
    if p.returncode != 0:
        hint = ""
        if IS_WIN:
            hint = ("\n常見原因：(1) 網路中斷 → 再執行一次。(2) 檔案被正在執行的舊版鎖住（WinError 5／32）→ "
                    "請使用者完全結束 Claude，在 PowerShell 貼上 RESULT 行裡的 rerun_powershell 指令，再重新打開 Claude。"
                    "(3) WinError 206（路徑太長）→ 需要開啟 Windows 長路徑支援（LongPathsEnabled）。")
        raise RuntimeError("套件安裝失敗（請看上方 pip 的錯誤訊息）。" + hint)
    mark.write_text(want + "\n", encoding="utf-8")
    return True


def write_settings(srv: Path, tier: str | None, stamp: str = "") -> dict:
    path = srv / "settings.json"
    data: dict = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
            else:
                raise ValueError("not an object")
        except (OSError, ValueError):
            bad = srv / f"settings.json.bad_{stamp or time.strftime('%Y%m%d-%H%M%S')}"
            shutil.copy2(path, bad)
            say(f"注意：settings.json 格式錯誤，已備份為 {bad.name}，改用新的設定檔。")
            data = {}
    if tier:
        data["tier"] = tier
    data.setdefault("tier", "free")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def self_check(vpy: Path, srv: Path, verify: bool) -> dict:
    cmd = [str(vpy), str(srv / "gemini_tts.py"), "--verify-key" if verify else "--check"]
    env = dict(os.environ)  # the self-check must see the key the same way the tool will
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        p = run(cmd, timeout=150, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "自我檢查逾時"}
    try:
        return json.loads(p.stdout)
    except ValueError:
        return {"ok": False, "error": (p.stderr or p.stdout or "").strip()[:800]}


def key_next_steps(srv: Path) -> list:
    if IS_WIN:
        ps1 = srv / "scripts" / "set-gemini-key.ps1"
        return [
            "還沒有找到 API 金鑰。請照 INSTALL_FOR_CLAUDE.md 第 4 步：開一個『新視窗』讓使用者自己貼上金鑰",
            "（不要在代理的終端機裡直接執行，那裡無法輸入；也不要請使用者把金鑰貼到對話）：",
            f"  PowerShell 工具：Start-Process powershell.exe -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"{ps1}\"'",
        ]
    if IS_MAC:
        cmd = srv / "scripts" / "set-gemini-key.command"
        return [
            "還沒有找到 API 金鑰。請照 INSTALL_FOR_CLAUDE.md 第 4 步：開一個『終端機』視窗讓使用者自己貼上金鑰",
            "（不要請使用者把金鑰貼到對話）：",
            f'  chmod +x "{cmd}" && open -a Terminal "{cmd}"',
        ]
    return ["還沒有找到 API 金鑰：請在 ~/.bashrc 或 ~/.zshenv 加入 export GEMINI_API_KEY='…'（自己輸入，不要貼到對話）。"]


def paths_for(args: argparse.Namespace) -> tuple:
    home = Path(args.home).expanduser().resolve() if args.home else Path.home()
    base = home / ".claude"
    return base, base / "mcp-servers" / NAME, base / "skills" / NAME


def install(args: argparse.Namespace) -> None:
    result: dict = {"action": "install", "platform": f"{platform.system()} {platform.release()}", "ok": False}
    base, srv, skill = paths_for(args)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    new_version = version_of(REPO / "server" / "gemini_tts.py")
    result.update(install_dir=str(srv), skill_dir=str(skill), version=new_version)
    if IS_WIN:
        result["rerun_powershell"] = rerun_powershell_cmd(args)

    say(f"Gemini TTS for Claude Code 安裝程式 — 版本 {new_version}")
    say(f"作業系統：{platform.system()} {platform.release()}（{platform.machine()}）")
    say(f"安裝位置：{srv}")
    say(f"Skill 位置：{skill}")

    step("1/6 尋找 Python 3.11 以上")
    found = find_python(args.python)
    existing_venv_ok = venv_healthy(venv_python(srv / ".venv")) if not found else None
    if found:
        py_cmd, ver, exe = found
        say(f"使用 Python {ver[0]}.{ver[1]}：{exe}")
        result["python"] = f"{ver[0]}.{ver[1]}"
    elif existing_venv_ok:
        py_cmd = None
        say(f"沒有找到其他 Python，沿用既有虛擬環境裡的 Python {existing_venv_ok[0]}.{existing_venv_ok[1]}。")
        result["python"] = f"{existing_venv_ok[0]}.{existing_venv_ok[1]}"
    else:
        say(python_help())
        result["error"] = "python_missing"
        finish(result, 3)

    step("2/6 備份舊版並複製檔案")
    old_version = version_of(srv / "gemini_tts.py")
    srv.mkdir(parents=True, exist_ok=True)
    skill.mkdir(parents=True, exist_ok=True)
    pairs = [(srv / f, REPO / "server" / f) for f in ("gemini_tts.py", "mcp_server.py", "requirements.txt")]
    pairs.append((skill / "SKILL.md", REPO / "skill" / "SKILL.md"))
    backup = backup_existing(pairs, srv, stamp)
    if backup:
        say(f"舊版（{old_version or '未知版本'}）有變動的檔案已備份到：{backup}")
    result.update(previous_version=old_version, backup_dir=str(backup) if backup else None)
    for inst, new in pairs:
        shutil.copy2(new, inst)
    copy_tree_files(REPO / "scripts", srv / "scripts")
    copy_tree_files(REPO / "docs", srv / "docs")
    if not IS_WIN:
        cmd_file = srv / "scripts" / "set-gemini-key.command"
        if cmd_file.exists():
            cmd_file.chmod(0o755)
    say("已複製：伺服器程式、Skill、設定金鑰的小工具（scripts/）、說明文件（docs/）。")
    say("使用紀錄 usage.json、設定檔 settings.json 不會被覆蓋。")

    step("3/6 建立 Python 虛擬環境並安裝套件")
    try:
        vpy = ensure_venv(srv, py_cmd, stamp)
        pip_install(vpy, srv / "requirements.txt", srv / ".venv")
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        say(str(exc))
        result["error"] = "venv_or_pip_failed"
        finish(result, 4)
    result["venv_python"] = str(vpy)

    step("4/6 寫入設定（免費／付費）")
    settings = write_settings(srv, args.tier, stamp)
    say(f"settings.json：tier = {settings['tier']}（只影響提醒訊息；Google 實際的額度以帳號為準）")
    result["tier"] = settings["tier"]

    step("5/6 向 Claude Code 註冊 MCP 伺服器")
    server_py = srv / "mcp_server.py"
    claude = find_claude()
    manual = manual_register_cmd(claude, vpy, server_py, args.scope)
    result["register_command"] = manual
    if IS_WIN:
        result["register_command_ps"] = manual_register_cmd(claude, vpy, server_py, args.scope, powershell=True)
    if args.no_register:
        say("已略過註冊（--no-register）。需要時可執行：")
        say("  " + manual)
        result["registered"] = None
    elif not claude:
        say("找不到 claude 指令（PATH、標準安裝位置、Claude 桌面 App 內建的都沒有），無法自動註冊。")
        say("請依 INSTALL_FOR_CLAUDE.md 第 3 步「registered 為 false」的說明處理。")
        result.update(registered=False, claude_cli=None)
    else:
        reg = register_mcp(claude, args.scope, vpy, server_py)
        say(("註冊成功：" if reg["ok"] else "註冊失敗：") + reg["detail"])
        if not reg["ok"]:
            if reg["removed_previous"]:
                say("注意：舊的註冊已移除，但新的註冊失敗，目前沒有註冊。")
            say("可手動執行：" + manual)
        result.update(registered=reg["ok"], claude_cli=claude, previous_registration_removed=reg["removed_previous"])

    step("6/6 自我檢查")
    check = self_check(vpy, srv, args.verify_key)
    shown = {k: check.get(k) for k in ("tool_version", "python_version", "google_genai_version", "mcp_version",
                                       "audio_player", "tier", "api_key_found", "api_key_source", "key_valid",
                                       "key_error", "key_note", "key_warning") if k in check}
    say(json.dumps(shown, ensure_ascii=False, indent=2))
    result.update(check_ok=bool(check.get("ok")), api_key_found=check.get("api_key_found"),
                  key_valid=check.get("key_valid"))
    for k in ("api_key_source", "key_error", "key_note", "key_warning"):
        if check.get(k):
            result[k] = check[k]
    if not check.get("ok"):
        say("自我檢查失敗：" + str(check.get("error")))
        result["error"] = "self_check_failed"
        result["error_detail"] = str(check.get("error"))[:800]
        finish(result, 5)

    say("\n安裝完成。")
    if not check.get("api_key_found"):
        for line in key_next_steps(srv):
            say(line)
    say("新版要等 Claude 完全結束再打開才會載入（Windows：系統匣圖示 → 結束；Mac：Cmd+Q；"
        "終端機版：輸入 /exit 後開新的終端機視窗再執行 claude）。")
    result["ok"] = True
    finish(result, 0)


def uninstall(args: argparse.Namespace) -> None:
    result: dict = {"action": "uninstall", "ok": False}
    base, srv, skill = paths_for(args)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    claude = find_claude()
    unregistered = None
    if not args.no_register:
        if not claude:
            say("找不到 claude 指令，無法自動取消註冊。請之後執行：claude mcp remove gemini-tts -s " + args.scope)
            unregistered = False
        else:
            try:
                p = run([claude, "mcp", "remove", NAME, "-s", args.scope], timeout=90)
                out = (p.stderr or p.stdout or "").strip()
                if p.returncode == 0:
                    unregistered = True
                    say("已取消 MCP 註冊。")
                elif re.search(r"not found|no .*mcp server|does not exist", out, re.I):
                    unregistered = True
                    say("原本就沒有註冊，不需要取消。")
                else:
                    unregistered = False
                    say("取消 MCP 註冊失敗：" + out[:300])
            except (OSError, subprocess.TimeoutExpired) as exc:
                unregistered = False
                say(f"取消 MCP 註冊失敗：{exc}")
    holder = base / f"{NAME}-removed_{stamp}"
    moved, not_moved = [], []
    for src, name in ((srv, "mcp-server"), (skill, "skill")):
        if not src.exists():
            continue
        holder.mkdir(parents=True, exist_ok=True)
        try:
            os.rename(str(src), str(holder / name))   # same folder tree: all-or-nothing, never a half copy
            moved.append(name)
        except OSError as exc:
            not_moved.append(str(src))
            say(f"無法移動 {src}（可能正在使用中；請完全結束 Claude 後再試一次）：{exc}")
    if moved:
        say(f"檔案已移到 {holder}（沒有刪除；確定不需要再自行刪除）。")
    if not moved and not not_moved:
        say("沒有找到已安裝的檔案。")
    say("環境變數 GEMINI_API_KEY 沒有變動；不再使用時可依 docs/02、docs/03 的「刪除金鑰」自行移除。")
    result.update(ok=not not_moved, unregistered=unregistered, moved_to=str(holder) if moved else None,
                  not_moved=not_moved)
    if IS_WIN:
        result["rerun_powershell"] = f'& "{sys.executable}" -X utf8 "{REPO / "install.py"}" --uninstall'
    else:
        result["rerun_command"] = f'"{sys.executable}" "{REPO / "install.py"}" --uninstall'
    finish(result, 0 if result["ok"] else 6)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Gemini TTS for Claude Code installer")
    ap.add_argument("--tier", choices=["free", "paid"], help="這把 API Key 的 Google 專案是免費版還是已開通付費")
    ap.add_argument("--python", help="指定用哪個 Python（3.11 以上）建立虛擬環境")
    ap.add_argument("--verify-key", action="store_true", help="安裝後向 Google 確認金鑰有效（不使用語音額度）")
    ap.add_argument("--scope", default="user", choices=["user", "project", "local"], help="MCP 註冊範圍（預設 user）")
    ap.add_argument("--no-register", action="store_true", help="不要向 Claude Code 註冊（測試用）")
    ap.add_argument("--home", help=argparse.SUPPRESS)  # testing: install under another home folder
    ap.add_argument("--uninstall", action="store_true", help="取消註冊，並把檔案移到備份資料夾（不刪除）")
    args = ap.parse_args()
    if sys.version_info < (3, 8):
        say("安裝程式需要 Python 3.8 以上才能啟動。")
        sys.exit(3)
    if args.uninstall:
        uninstall(args)
    else:
        install(args)


if __name__ == "__main__":
    main()
