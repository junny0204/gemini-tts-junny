# Gemini TTS for Claude Code（Windows／macOS）

讓 Claude Code 用 Google **Gemini 3.8 Flash TTS** 把文字變成自然的語音（WAV）：旁白、配音、朗讀、有聲書、Podcast、多人對話，或直接念給你聽。包含一個 MCP 伺服器和一個 Skill，Windows 和 Mac 都能用。

> 🤖 **給 AI 代理（Claude Code 等）**：使用者把這個網址交給你、請你安裝或更新時，請讀 **[INSTALL_FOR_CLAUDE.md](INSTALL_FOR_CLAUDE.md)** 的**原文**並一步一步照做。
> 不要用會摘要內容的 WebFetch；請在 Bash 執行
> `curl -fsSL https://raw.githubusercontent.com/junny0204/gemini-tts-junny/main/INSTALL_FOR_CLAUDE.md`
> （只有 PowerShell 時：`(Invoke-WebRequest https://raw.githubusercontent.com/junny0204/gemini-tts-junny/main/INSTALL_FOR_CLAUDE.md -UseBasicParsing).Content`）。
> 在 Mac 上**不要**先執行 `git` 或 `python3`：沒裝開發者工具時它們會跳出安裝視窗，手冊第 1、3 步有安全的寫法。
> 重點：判斷作業系統 → 執行 `install.py` → 開視窗讓使用者**自己**把 API 金鑰存進環境變數。**絕對不要請使用者把金鑰貼到對話裡，也不要讀取或印出金鑰。**

## 怎麼安裝（給人看）

1. 打開 Claude Code（Claude 桌面 App 的 Code 分頁，或終端機裡的 `claude`）。
2. 把下面這句話貼給它：

   ```text
   請幫我安裝 https://github.com/junny0204/gemini-tts-junny
   ```

3. Claude 會自動判斷你的電腦是 Windows 還是 Mac，然後：
   - 下載這個安裝包、檢查 Python、安裝程式和 Skill；
   - 一步一步教你到 Google AI Studio 取得 API 金鑰；
   - 開一個專用的小視窗，讓你**自己**貼上金鑰，存進電腦的環境變數（Claude 看不到金鑰）；
   - 幫你確認金鑰有效（不會用到語音額度）。
4. 最後依 Claude 的提示，完全結束 Claude 再打開一次。

之後只要跟 Claude 說「把這段念出來」「幫我配一段旁白」就可以用了。

## 需要什麼

- Claude Code（桌面 App 或 CLI）。
- Python 3.11 以上。沒有的話 Claude 會教你安裝（Mac 沒有內建可用的新版 Python）。
- 一個 Google 帳號（年滿 18 歲），用來取得免費的 Gemini API 金鑰；常用的話可以開通付費。
- 網路連線。

## 文件

| 文件 | 內容 |
|---|---|
| [docs/01_取得Gemini_API金鑰.md](docs/01_取得Gemini_API金鑰.md) | 一步一步取得 API 金鑰、驗證專案、開通付費、金鑰外流怎麼辦 |
| [docs/02_設定金鑰_Windows.md](docs/02_設定金鑰_Windows.md) | Windows：把金鑰存成使用者環境變數 |
| [docs/03_設定金鑰_macOS.md](docs/03_設定金鑰_macOS.md) | Mac：把金鑰存進 `~/.zshenv` |
| [docs/04_額度費用與疑難排解.md](docs/04_額度費用與疑難排解.md) | 免費／付費額度、費用、常見錯誤、檔案位置 |
| [INSTALL_FOR_CLAUDE.md](INSTALL_FOR_CLAUDE.md) | 給 Claude Code 的安裝操作手冊 |
| [CHANGELOG.md](CHANGELOG.md) | 版本紀錄 |

## 更新、切換付費、移除

- **更新**：跟 Claude 說「請幫我更新 https://github.com/junny0204/gemini-tts-junny」。舊版會自動備份，設定和使用紀錄會保留。
- **改成付費版**：開通付費後跟 Claude 說「我開通 Gemini 付費了，幫我改設定」。
- **移除**：跟 Claude 說「幫我移除 Gemini TTS」（會執行 `install.py --uninstall`：取消註冊，把檔案移到備份資料夾，不會直接刪除）。

## 功能

- 單人朗讀、旁白；長稿自動分段再接起來。
- 多人對話（2 人原生生成，最自然）。
- 30 種內建聲音，加上擴充聲音庫搜尋。
- Windows（winsound）和 Mac（afplay）都能直接播放。
- 不會卡住：額度用完會**立刻**告訴你幾點重置；伺服器沒回應約 150 秒就停止。
- 錯誤訊息都是繁體中文，並附上解決方法（額度、402 預付餘額、專案驗證、金鑰外流等）。

## 安全

- 這個儲存庫**不包含任何金鑰或使用紀錄**。
- 安裝程式從不讀取或顯示金鑰；工具只回報「找到了沒、從哪裡找到、是否有效」。
- 金鑰只存在你電腦的環境變數：Windows 使用者環境變數；Mac 的 `~/.zshenv`（權限 600）。Mac 的小工具停用舊設定時會先備份（備份檔權限 600，確認新金鑰可用後可以刪除）。
- 工具回傳的訊息會自動遮蔽金鑰；輸出路徑也不能拿來展開環境變數。
- 設定金鑰的小工具原始碼都在 `scripts/`，可以自己打開檢查。

## 檔案結構

```text
install.py                 跨平台安裝程式（Windows／macOS／Linux）
INSTALL_FOR_CLAUDE.md      給 Claude Code 的安裝手冊
server/gemini_tts.py       核心程式和命令列工具
server/mcp_server.py       MCP 伺服器
server/requirements.txt    固定版本的 Python 套件
skill/SKILL.md             Claude Code Skill
scripts/set-gemini-key.ps1       Windows：設定金鑰的小視窗
scripts/set-gemini-key.command   macOS：設定金鑰的小視窗
docs/                      教學文件
tests/                     自動測試
```

## 手動安裝（進階）

```bash
git clone https://github.com/junny0204/gemini-tts-junny.git
cd gemini-tts-junny
python3 install.py --tier free --verify-key   # Windows：py -3 -X utf8 install.py --tier free --verify-key
```

（Mac 需要先安裝 Python 3.11 以上，例如 python.org 的安裝程式；`git` 需要命令列開發者工具。不想裝的話，照 INSTALL_FOR_CLAUDE.md 第 1 步用 zip 下載。）
