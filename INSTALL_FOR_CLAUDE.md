# 給 Claude Code 的安裝指引（INSTALL_FOR_CLAUDE）

> 這份文件是寫給 **AI 代理（Claude Code）** 看的操作手冊。使用者把 `https://github.com/junny0204/gemini-tts-junny` 貼給你、請你安裝或更新時，請**從頭到尾照這份文件做**。
> 請讀**原文**：先做第 1 步把安裝包下載到本機，再用 Read 工具讀本機的這個檔案。不要用會摘要內容的 WebFetch，指令細節會跑掉。
> 使用者不一定懂程式：用使用者的語言（預設**繁體中文**）、一次一步、白話說明；需要使用者動手時，清楚說出要點哪裡、看到什麼畫面算成功。

## 安全規則（全程遵守）

1. **API 金鑰只能由使用者自己輸入**到作業系統的環境變數（透過第 4 步開的視窗）。**絕對不要**請使用者把金鑰貼到對話裡；如果使用者主動貼了，提醒他這把金鑰已經出現在對話紀錄裡，建議到 https://aistudio.google.com/apikey 建立新金鑰、刪除舊的，再用第 4 步重新設定。不要替他把貼在對話裡的金鑰寫進任何地方。
2. **不要讀取或印出金鑰，也不要讀取存放金鑰的檔案**：不要用 `cat`、`grep`、`head`、`tail`、`sed`、`less`、Read 工具等讀 `~/.zshenv`、`~/.zshrc`、`~/.zprofile`、`~/.zlogin`、`~/.bash_profile`、`~/.bash_login`、`~/.bashrc`、`~/.profile` 或任何 `*.bak-gemini-tts-*` 檔；不要執行 `echo $GEMINI_API_KEY`、`printenv`、`env`、`set`、`export -p`、`Get-ChildItem Env:`、`$env:GEMINI_API_KEY`、`reg query HKCU\Environment`。要確認金鑰，只用工具的 `--check`／`--verify-key`（只會回報有沒有、從哪裡找到、是否有效）。
3. 不要把金鑰寫進 `~/.claude.json`、`settings.json`、`.mcp.json`，也不要用 `claude mcp add -e`。
4. 你的 Bash／PowerShell 工具沒有互動終端機，`Read-Host`、`read -s` 在裡面不能用；需要使用者輸入時，一律**開一個新視窗**給使用者操作。
5. 安裝 Python、安裝 Claude CLI、開通付費這類動作，先徵得使用者同意；付款一律由使用者自己操作。
6. 不要建議「多開 Google 帳號輪流換金鑰」來規避免費額度（違反 Google API 服務條款）。

## 第 0 步：判斷作業系統和你能用的工具

看你的環境資訊（`Platform: win32` = Windows、`darwin` = macOS）。之後每一步都有三種寫法，**選一種用到底**：

| 你的狀況 | 用哪一種 |
|---|---|
| macOS | 「**macOS**」的指令（Bash 工具） |
| Windows，而且你有 Bash 工具（Git Bash） | 「**Windows／Git Bash**」的指令 |
| Windows，只有 PowerShell 工具（沒裝 Git for Windows 時就是這樣） | 「**Windows／PowerShell**」的指令 |

告訴使用者：「偵測到你的電腦是 Windows／Mac，接下來照這個平台的步驟。」Windows 上執行 Python 一律加 `-X utf8`，中文才不會變亂碼。

## 第 1 步：取得安裝包

放在 `<家目錄>/.claude/gemini-tts-junny-src`。這個資料夾只是下載下來的安裝包，可以整個取代；使用者的設定和紀錄存在別的地方。

**macOS**（先用 `xcode-select -p` 判斷：成功才用 git；失敗代表沒有開發者工具，**不要**執行 git，以免跳出安裝視窗）：

```bash
cd "$HOME"; SRC="$HOME/.claude/gemini-tts-junny-src"
if xcode-select -p >/dev/null 2>&1; then
  if [ -d "$SRC/.git" ]; then git -C "$SRC" pull --ff-only; else rm -rf "$SRC"; git clone https://github.com/junny0204/gemini-tts-junny.git "$SRC"; fi
else
  TMP="$(mktemp -d)"; curl -fsSL -o "$TMP/src.zip" https://github.com/junny0204/gemini-tts-junny/archive/refs/heads/main.zip \
    && unzip -q "$TMP/src.zip" -d "$TMP" && rm -rf "$SRC" && mv "$TMP/gemini-tts-junny-main" "$SRC"
fi
ls "$SRC/install.py" && echo READY
```

**Windows／Git Bash**：

```bash
H="$(cygpath -u "$USERPROFILE")"; cd "$H"; SRC="$H/.claude/gemini-tts-junny-src"
if [ -d "$SRC/.git" ]; then git -C "$SRC" pull --ff-only; else rm -rf "$SRC"; git clone https://github.com/junny0204/gemini-tts-junny.git "$SRC"; fi
ls "$SRC/install.py" && echo READY
```

**Windows／PowerShell**：

```powershell
Set-Location $env:USERPROFILE; $src = "$env:USERPROFILE\.claude\gemini-tts-junny-src"; $tmp = Join-Path $env:TEMP ("gtts_" + [guid]::NewGuid())
New-Item -ItemType Directory $tmp | Out-Null
Invoke-WebRequest https://github.com/junny0204/gemini-tts-junny/archive/refs/heads/main.zip -OutFile "$tmp\src.zip" -UseBasicParsing
Expand-Archive "$tmp\src.zip" $tmp
if (Test-Path $src) { Remove-Item -Recurse -Force $src -ErrorAction Stop }
Move-Item "$tmp\gemini-tts-junny-main" $src
if (Test-Path "$src\install.py") { 'READY' }
```

看到 `READY` 才繼續。git 的 `pull` 失敗時（例如有人改過裡面的檔案），改用 zip 的寫法。接著用 Read 工具讀 `gemini-tts-junny-src/INSTALL_FOR_CLAUDE.md`（就是這份文件的最新版），照它繼續。

## 第 2 步：問使用者一個問題（只問一次）

先看是否已經裝過：安裝資料夾裡有 `settings.json` 就**不用問**，第 3 步也**不要**加 `--tier`（會沿用原本的設定）。

- macOS：`ls ~/.claude/mcp-servers/gemini-tts/settings.json`
- Windows／Git Bash：`ls "$(cygpath -u "$USERPROFILE")/.claude/mcp-servers/gemini-tts/settings.json"`
- Windows／PowerShell：`Test-Path "$env:USERPROFILE\.claude\mcp-servers\gemini-tts\settings.json"`

否則問使用者：

> 你的 Gemini API 帳號是**免費版**，還是已經在 Google AI Studio **開通付費**（有買點數或綁卡）？不確定的話選免費版，之後可以改。

免費版 → `--tier free`；付費 → `--tier paid`。這個設定只影響提醒訊息，不影響 Google 實際的額度。

## 第 3 步：執行安裝程式

第一次要下載套件，約 1–3 分鐘。請把 timeout 設成最大值（600000）；網路很慢時改用 `run_in_background` 執行，等完成通知再讀結果。下面的 `--tier free` 依第 2 步調整（已裝過就拿掉）。只要任何 Python 3.8 以上能啟動 `install.py` 就好，它會自己挑 3.11 以上的版本來建立環境。

**macOS**（不用萬用字元，也避開沒裝開發者工具時會跳出安裝視窗的 `/usr/bin/python3`）：

```bash
cd "$HOME/.claude/gemini-tts-junny-src" || exit 1
PY=""
for v in 3.14 3.13 3.12 3.11 3.15 3.16; do
  c="/Library/Frameworks/Python.framework/Versions/$v/bin/python3"; [ -z "$PY" ] && [ -x "$c" ] && PY="$c"
done
for c in /opt/homebrew/bin/python3 /usr/local/bin/python3; do [ -z "$PY" ] && [ -x "$c" ] && PY="$c"; done
c="$(command -v python3 2>/dev/null)"; [ -z "$PY" ] && [ -n "$c" ] && [ "$c" != /usr/bin/python3 ] && PY="$c"
[ -z "$PY" ] && xcode-select -p >/dev/null 2>&1 && PY=/usr/bin/python3
if [ -z "$PY" ]; then echo NO_PYTHON; else "$PY" install.py --tier free --verify-key; fi
```

**Windows／Git Bash**（只選一次 Python，不會重複執行）：

```bash
cd "$(cygpath -u "$USERPROFILE")/.claude/gemini-tts-junny-src" || exit 1
ok() { "$@" -c "import sys; sys.exit(sys.version_info < (3, 8))" >/dev/null 2>&1; }
PY=()
if command -v py >/dev/null 2>&1 && ok py -3; then PY=(py -3)
else
  for c in "$(cygpath -u "$LOCALAPPDATA")"/Programs/Python/Python3*/python.exe; do
    [ ${#PY[@]} -eq 0 ] && [ -x "$c" ] && ok "$c" && PY=("$c")
  done
  [ ${#PY[@]} -eq 0 ] && ok python && PY=(python)
fi
if [ ${#PY[@]} -eq 0 ]; then echo NO_PYTHON; else "${PY[@]}" -X utf8 install.py --tier free --verify-key; fi
```

**Windows／PowerShell**：

```powershell
Set-Location "$env:USERPROFILE\.claude\gemini-tts-junny-src" -ErrorAction Stop
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function Test-Py($exe, $pre) { try { & $exe @pre -c "import sys; sys.exit(sys.version_info < (3, 8))" 2>$null | Out-Null; return $LASTEXITCODE -eq 0 } catch { return $false } }
$py = $null; $pre = @()
if ((Get-Command py -ErrorAction SilentlyContinue) -and (Test-Py 'py' @('-3'))) { $py = 'py'; $pre = @('-3') }
else {
  foreach ($c in Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue) {
    if (-not $py -and (Test-Py $c.FullName @())) { $py = $c.FullName }
  }
  if (-not $py -and (Test-Py 'python' @())) { $py = 'python' }
}
if (-not $py) { 'NO_PYTHON' } else { & $py @pre -X utf8 install.py --tier free --verify-key }
```

安裝程式會：找 Python 3.11+ → 有變動的舊檔先備份 → 複製程式到 `<家目錄>/.claude/mcp-servers/gemini-tts/`、Skill 到 `<家目錄>/.claude/skills/gemini-tts/` → 建立虛擬環境、安裝固定版本的套件 → 用 `claude mcp add --scope user` 註冊（PATH 上沒有 `claude` 時，會自動找 Claude 桌面 App 內建的那一份）→ 自我檢查並向 Google 確認金鑰（不用語音額度）。**它從不讀取或顯示金鑰。**

在輸出裡找開頭是 `GEMINI_TTS_INSTALL_RESULT` 的那一行（JSON），之後的步驟都用它的欄位（例如 `venv_python`、`install_dir`）：

| 情況 | 意思 | 你要做的事 |
|---|---|---|
| `exit_code` 0 | 成功 | 看 `api_key_found`、`key_valid`：<br>• `api_key_found` false → 第 4 步<br>• `key_valid` true → 第 5 步（`api_key_source` 含 `GOOGLE_API_KEY` 時，建議做第 4 步改設 `GEMINI_API_KEY`）<br>• `key_valid` false → 把 `key_error` 告訴使用者，做第 4 步（多半要建立新金鑰）<br>• `key_valid` null → 看 `key_error`：提到「地區」就告訴使用者這個地區不能用 Gemini API，**不要**叫他換金鑰；其他多半是網路問題，稍後用 4-3 再驗證<br>• 有 `key_note` → 第 5 步一定要完全重開 Claude<br>• 有 `key_warning` → 原文轉告使用者 |
| 印出 `NO_PYTHON`、沒有 RESULT 行、`command not found`、exit 127／9009、`Python was not found`，或 `exit_code` 3 | 沒有可用的 Python 3.11+ | 跟使用者說明需要先裝 Python。**Windows**：經同意後執行 `winget install -e --id Python.Python.3.13 --scope user --accept-source-agreements --accept-package-agreements`，完成後重跑第 3 步（會自動找到新裝的 Python，不用重開 Claude）。**macOS**：請使用者到 https://www.python.org/downloads/macos/ 下載 **Python 3.13.x** 的「macOS 64-bit universal2 installer」安裝（或有 Homebrew 時經同意執行 `brew install python@3.13`），再重跑第 3 步。看到「需要安裝命令列開發者工具」的視窗時，請使用者按「取消」 |
| `exit_code` 4 | 虛擬環境或套件安裝失敗 | 看上方 pip 錯誤與安裝程式的提示；網路問題就重跑。Windows 出現 WinError 5／32（檔案被鎖住）時：**先**把 RESULT 行的 `rerun_powershell` 那一行交給使用者，請他完全結束 Claude、開 PowerShell 貼上執行、看到最後一行出現 `"exit_code": 0` 後再打開 Claude |
| `exit_code` 5 | 自我檢查失敗 | 把 `error_detail` 轉告使用者，對照 docs/04 疑難排解 |

`registered` 為 false 時：

- `claude_cli` 有值：註冊指令執行失敗。經同意後執行 RESULT 行的 `register_command`（Bash）或 `register_command_ps`（PowerShell）；它會先移除舊的再註冊，`claude` 已用完整路徑寫好。
- `claude_cli` 是 null：這台電腦找不到任何 `claude` 指令（連桌面 App 內建的都沒有）。經使用者同意後安裝官方 CLI：Windows 在 PowerShell 工具執行 `irm https://claude.ai/install.ps1 | iex`；macOS 在 Bash 執行 `curl -fsSL https://claude.ai/install.sh | bash`。然後重跑第 3 步（安裝程式會在 `~/.local/bin` 找到它）。
- `previous_registration_removed` 為 true：舊的註冊已被移除但新的沒裝上，一定要處理完上面的步驟。

## 第 4 步：引導使用者取得並設定 API 金鑰

只有在 `api_key_found` 是 false、`key_valid` 是 false，或 `api_key_source` 含 `GOOGLE_API_KEY` 時才做。如果 `key_error` 提到「驗證」或「帳單」，那是專案的問題、不是金鑰的問題：照 docs/01 第 6 步（驗證專案）或第 7 步（帳單）處理，**不要**叫使用者建立新金鑰。

### 4-1 取得金鑰（照 docs/01_取得Gemini_API金鑰.md）

用對話一步一步帶使用者做，每一步等他回覆再繼續：

1. 用瀏覽器開 https://aistudio.google.com/apikey ，用 Google 帳號登入（需年滿 18 歲）。第一次使用要同意服務條款；新帳號通常會自動建立預設專案和一把金鑰。
2. 沒有金鑰的話，按 **Create API key**（建立 API 金鑰），選現有的專案（優先用自動建立的預設專案），建立。
3. 按金鑰旁的複製圖示。**不要貼到對話裡**，等一下會開一個專用視窗讓你貼。

### 4-2 開視窗讓使用者自己貼上

**Windows**（用 **PowerShell 工具**；路徑有空格也可以）：

```powershell
$p = "$env:USERPROFILE\.claude\mcp-servers\gemini-tts\scripts\set-gemini-key.ps1"
Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$p`""
```

（只有 Bash 工具時：`powershell.exe -NoProfile -Command 'Start-Process powershell.exe -ArgumentList ("-NoProfile -ExecutionPolicy Bypass -File " + [char]34 + "$env:USERPROFILE\.claude\mcp-servers\gemini-tts\scripts\set-gemini-key.ps1" + [char]34)'`）

告訴使用者：「我開了一個標題是『Gemini TTS：設定 API Key』的藍色（或黑色）視窗，請在裡面按 Ctrl+V（或滑鼠右鍵）貼上金鑰，再按 Enter。畫面只會顯示 *，這是正常的。看到綠色的『已儲存』後按 Enter 關閉，再回來告訴我。」

如果視窗沒出現，或使用者偏好圖形介面，改開系統的環境變數視窗：`Start-Process rundll32.exe -ArgumentList 'sysdm.cpl,EditEnvironmentVariables'`，再照 docs/02 方法 B 帶他做（上半部「使用者變數」→「新增(N)...」→ 變數名稱 `GEMINI_API_KEY` → 變數值貼上 → 確定 → **主視窗再按一次確定**）。

**macOS**（Bash 工具）：

```bash
F="$HOME/.claude/mcp-servers/gemini-tts/scripts/set-gemini-key.command"; chmod +x "$F" && open -a Terminal "$F"
```

告訴使用者：「我開了一個標題是『Gemini TTS：設定 API Key』的終端機視窗（如果你的終端機是用分頁，可能是新分頁），請在**那個**視窗按 Cmd+V 貼上金鑰，再按 Return。畫面不會顯示任何字，這是正常的。看到『已儲存到 …』後按 Return，再回來告訴我。」它會把金鑰寫進 `~/.zshenv`（bash 使用者是 bash 的登入設定檔，權限 600），並把其他設定檔裡舊的 `GEMINI_API_KEY` 換成不含金鑰的註解（先備份）。視窗出現「無法打開」時，改請使用者在終端機貼上：`bash ~/.claude/mcp-servers/gemini-tts/scripts/set-gemini-key.command`。

### 4-3 確認金鑰有效（不用語音額度）

使用者說設好之後，用 RESULT 行的 `venv_python` 和 `install_dir` 執行（不要自己拼路徑）：

- macOS／Git Bash：`"<venv_python>" -X utf8 "<install_dir>/gemini_tts.py" --verify-key`
- PowerShell：`& "<venv_python>" -X utf8 "<install_dir>\gemini_tts.py" --verify-key`

預期 `"api_key_found": true` 且 `"key_valid": true`。工具會優先讀使用者**剛存的**金鑰（Windows 讀登錄檔、macOS 讀 shell 設定檔），所以**不用重開 Claude** 就能確認；如果結果有 `key_note`，代表 Claude 啟動時帶的是舊金鑰，第 5 步一定要重開。

- `api_key_found` 還是 false：請使用者確認視窗有顯示「已儲存」；Windows 用方法 B 的話，確認主視窗有按第二次「確定」。
- `key_valid` false：把 `key_error` 轉告使用者（常見：複製不完整 → 重貼；金鑰被停用 → 建立新金鑰；提到「驗證」或「帳單」→ 照 docs/01 第 6、7 步處理，不用換金鑰）。
- 有 `key_warning`：原文轉告使用者。
- `key_valid` null：看 `key_error`，地區問題就不要再換金鑰；網路問題稍後再試。
- `api_key_source` 含 `GOOGLE_API_KEY`：代表沒找到 `GEMINI_API_KEY`，請回到 4-2。
- 注意：這一步只確認金鑰能通過驗證；如果專案需要「驗證」或帳單有問題，會在第一次產生語音時才出現，工具會用中文說明怎麼處理。

## 第 5 步：重新啟動 Claude

新安裝或更新後，MCP 伺服器要等 Claude 重新啟動才會載入新版。請使用者：

- **Windows 桌面 App**：在右下角系統匣找到 Claude 圖示 → 右鍵 → 結束（Quit），再從開始選單打開。只關視窗不算。
- **macOS 桌面 App**：在 Claude 視窗按 **Cmd+Q**，再重新打開。
- **終端機版 `claude`**：輸入 `/exit` 離開，關掉這個終端機視窗，開一個新的終端機視窗再執行 `claude`（新視窗才會讀到新的環境變數）。

如果使用者現在不方便重開（例如有其他工作在跑）：告訴他新版會在下次重開後生效；在那之前可以用命令列版本（見 skill/SKILL.md「MCP 工具無法使用時」）。

重開後可以請使用者說「檢查 Gemini TTS」，用 `check_setup`（`verify_key=true`）確認：`tool_version` 是新版、`key_valid` 是 true。也可以在 Claude 輸入 `/mcp` 看 `gemini-tts` 是否已連線。

## 第 6 步（選用）：試念一句

**先問使用者**（會用掉 1 次請求；付費版約 NT$0.02），同意才做：

- 用 MCP 工具 `generate_speech`：text `你好，這是 Gemini 語音測試。`，`play=true`，output_path 用絕對路徑，例如使用者「音樂」資料夾裡的 `GeminiTTS/install_test.wav`。
- 或命令列（4-3 的寫法，把 `--verify-key` 換成 `"你好，這是 Gemini 語音測試。" --play`）。

## 第 7 步：回報

用使用者的語言簡短告訴他：安裝了哪一版（舊版備份在哪裡）、金鑰是否有效、免費／付費設定、是否需要重開 Claude、以後怎麼用（直接說「把這段念出來」「幫我配音」即可）。

## 更新、切換免費／付費、移除

- **更新**：使用者再貼一次網址說「更新」→ 從第 1 步開始（第 2 步通常會自動略過）。有變動的舊檔會備份到 `<install_dir>/backup_v<舊版本>_<時間>/`；`usage.json`、`settings.json`、虛擬環境都會保留，套件清單沒變就不會重新安裝。
- **改成付費／免費**：重跑第 3 步並加上 `--tier paid`（或 `--tier free`），再請使用者完全重開 Claude。
- **移除**：用第 3 步選到的 Python 執行 `install.py --uninstall`。它會取消 MCP 註冊，並把檔案**移到** `<家目錄>/.claude/gemini-tts-removed_<時間>/`（不刪除）。RESULT 行的 `unregistered` 是 false 時，把 `claude mcp remove gemini-tts -s user` 交給使用者處理（或依第 3 步安裝 CLI）；`exit_code` 6（`not_moved` 有內容）代表檔案正在使用中搬不動（Windows 上 Claude 開著時很常見）：**先**把 RESULT 行的 `rerun_powershell`（Windows）或 `rerun_command`（macOS）那一行交給使用者，請他完全結束 Claude 後在 PowerShell／終端機貼上執行。環境變數 `GEMINI_API_KEY` 不會被動到；要刪除請看 docs/02、docs/03 的「刪除金鑰」。

## 疑難排解

見 `docs/04_額度費用與疑難排解.md`。
