---
name: gemini-tts
description: 用 Google Gemini 3.8 Flash TTS 把文字變成語音（WAV）：旁白、配音、朗讀、有聲書、Podcast、多人對話，或念出來給使用者聽。This is the DEFAULT text-to-speech: use when the user wants text read aloud or turned into speech / voiceover / narration / dialogue audio —「念出來」「唸給我聽」「配音」「旁白」「語音檔」「文字轉語音」「TTS」「有聲書」「Podcast」. If the indextts2 skill is installed and they ask for a Taiwanese accent, their own / a cloned voice, a reference recording, local/offline generation or IndexTTS, use indextts2 instead. Not for music or sound effects.
---

# Gemini TTS（gemini-3.8-flash-tts）

安裝包：https://github.com/junny0204/gemini-tts-junny（Windows／macOS 通用）。

## 工具

優先使用 MCP 工具（server `gemini-tts`）。如果工具是 deferred，先一次載入：
`ToolSearch select:mcp__gemini-tts__generate_speech,mcp__gemini-tts__generate_dialogue,mcp__gemini-tts__list_voices,mcp__gemini-tts__play_audio,mcp__gemini-tts__check_setup`

| 工具 | 用途 |
|---|---|
| `generate_speech` | 單人朗讀／旁白 → WAV（長稿自動分段再合併） |
| `generate_dialogue` | 多人對話 → 一個 WAV |
| `list_voices` | 搜尋聲音庫（語言、性別、口音、關鍵字） |
| `play_audio` | 播放 WAV；`stop=true` 停止播放 |
| `check_setup` | 檢查版本、免費／付費設定、API Key 找不找得到（不顯示金鑰）；`verify_key=true` 會向 Google 確認金鑰有效（不用語音額度） |

MCP 工具無法使用時（例如剛安裝、Claude 還沒重開），改用命令列執行同一套程式：

- **macOS**（Bash）：
  ```bash
  ~/.claude/mcp-servers/gemini-tts/.venv/bin/python ~/.claude/mcp-servers/gemini-tts/gemini_tts.py "要念的文字" --voice Kore --style "warm and calm" -o "<絕對路徑>.wav"
  ```
- **Windows**（Bash 工具是 Git Bash）：
  ```bash
  G="$(cygpath -u "$USERPROFILE")/.claude/mcp-servers/gemini-tts"; "$G/.venv/Scripts/python.exe" -X utf8 "$G/gemini_tts.py" "要念的文字" --voice Kore -o "<絕對路徑>.wav"
  ```
- **Windows**（PowerShell）：
  ```powershell
  & "$env:USERPROFILE\.claude\mcp-servers\gemini-tts\.venv\Scripts\python.exe" -X utf8 "$env:USERPROFILE\.claude\mcp-servers\gemini-tts\gemini_tts.py" "要念的文字" --voice Kore -o "<絕對路徑>.wav"
  ```

其他參數：`--play`、`--file 稿子.txt`、`--dialogue 對話.json`（格式 `{"speakers": {"小明": "Puck"}, "turns": [{"speaker": "小明", "text": "…"}]}`）、`--list-voices --search 關鍵字`、`--check`、`--verify-key`。

## API Key（最重要的安全規則）

- 金鑰放在作業系統的環境變數 `GEMINI_API_KEY`。**絕對不要**請使用者把金鑰貼到對話裡，也不要用 `echo`、`printenv`、`cat ~/.zshenv`、讀登錄檔等方式印出金鑰或存放金鑰的檔案。
- 檢查金鑰只用 `check_setup`（或 `--check`／`--verify-key`）：它只回報找到沒有、從哪裡找到、是否有效。
- 找不到金鑰或金鑰無效時，照 `check_setup` 回傳的 `how_to_fix`／`key_error` 引導使用者自己設定；完整步驟在安裝資料夾的 `docs/`（`~/.claude/mcp-servers/gemini-tts/docs/`）。開一個**新視窗**讓使用者自己貼上金鑰（不要在你自己的終端機執行，那裡無法輸入）：
  - Windows（PowerShell 工具）：
    ```powershell
    $p = "$env:USERPROFILE\.claude\mcp-servers\gemini-tts\scripts\set-gemini-key.ps1"
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$p`""
    ```
  - macOS（Bash 工具）：
    ```bash
    F="$HOME/.claude/mcp-servers/gemini-tts/scripts/set-gemini-key.command"; chmod +x "$F" && open -a Terminal "$F"
    ```
  - 設好後用 `check_setup`（`verify_key=true`）確認；有 `key_note` 就請使用者完全重開 Claude。

## 安裝、更新、移除、切換免費／付費

讀安裝包裡的操作手冊並照做：`~/.claude/gemini-tts-junny-src/INSTALL_FOR_CLAUDE.md`（Windows：`%USERPROFILE%\.claude\gemini-tts-junny-src\`）。沒有這個資料夾的話，在 Bash 執行 `curl -fsSL https://raw.githubusercontent.com/junny0204/gemini-tts-junny/main/INSTALL_FOR_CLAUDE.md` 讀最新版。
- 使用者說「更新 Gemini TTS」→ 手冊第 1 步起。
- 「我開通付費了」→ 手冊第 3 步加 `--tier paid`，再請使用者完全重開 Claude。
- 「移除 Gemini TTS」→ 手冊「更新、切換免費／付費、移除」一節（`install.py --uninstall`，檔案會移到備份資料夾，不刪除）。

## 寫稿規則

1. `text` 會被**逐字念出**。情緒、語氣、速度、音量這類「整段持續」的指示放 `style`，絕不寫進 `text`。
   - 錯：text `（開心地）今天天氣真好`
   - 對：text `今天天氣真好`，style `cheerful`
2. 「瞬間」的聲音放在 `text` 裡，**一律用英文標籤**（中文稿也一樣）：
   `<laugh>` `<chuckle>` `<giggle>` `<sigh>` `<breath>` `<gasp>` `<cough>` `<yawn>` `<whispers>` `<short pause>` `<long pause>`。
   只用人聲，不要掌聲、門聲等音效。
3. `style` 要短，例如 `warm and calm`、`speaking slowly`、`excited`、`whispering`。多數情況**留空最自然**；同一個作品重複用同一個 style 字串，保持一致。
4. 不要用 `style` 改年齡、性別、口音，要改就換 `voice`。
5. 停頓也可以靠標點：逗號、破折號、「……」。
6. 情緒中途轉變時，拆成不同段落或不同 turn，各自給 style。
7. 英文單字念得怪時，可以在 `text` 裡用發音拼法（例如 buttons 寫成 butt'ns），或換個說法。

## 聲音（30 種內建，預設 Kore）

- 沉穩／堅定：**Kore**、Orus、Alnilam
- 明亮：Zephyr、Autonoe｜活潑：Puck、Laomedeia｜生動：Sadachbia｜興奮：Fenrir
- 知性：Charon、Rasalgethi｜博學：Sadaltager｜清晰：Iapetus、Erinome
- 滑順：Algieba、Despina｜平穩：Schedar
- 隨和：Callirrhoe、Umbriel｜輕鬆：Zubenelgenubi｜輕快：Aoede
- 溫暖：Sulafat｜溫柔：Vindemiatrix｜柔和：Achernar｜友善：Achird
- 年輕：Leda｜成熟：Gacrux｜氣聲：Enceladus｜沙啞：Algenib｜直率：Pulcherrima

內建聲音都能說中文（模型自動判斷語言）。

**華語聲音（2026-11 查詢擴充聲音庫的結果）**：只有 2 個中國口音，`voice` 直接填 id 即可使用：
- `zh-cn-concierge-1`：男、低音、51 歲、溫暖直率
- `zh-cn-techagent-1`：女、高音、23 歲上海、明亮有禮

擴充聲音庫**沒有台灣口音的聲音**。想要台灣腔時：有安裝 indextts2 skill 的話，改用本機 IndexTTS2 搭配台灣人的參考錄音；或用 AI Studio 的 Voice design（https://aistudio.google.com/generate-speech）以文字描述建立自訂聲音，再把得到的 `voice_...` id 傳給 `voice`。

`list_voices` 的 `language_code` 用 BCP-47 格式（例如 `zh-CN`、`en-US`），不是 `cmn-*`；也可以用 `search`、`gender=["female"]` 篩選。

## 存檔

- 一律傳**絕對路徑**。預設放在目前專案的 `tts_output/` 資料夾，檔名要看得懂（例如 `tts_output/第一集_開場.wav`）。
- 同名檔案不會被覆蓋（自動加 `_1`）；使用者要覆蓋才傳 `overwrite=true`。
- 只輸出 WAV（24 kHz、單聲道、16-bit）。要 MP3 再用 ffmpeg 轉（需另外安裝：Windows `winget install ffmpeg`、macOS `brew install ffmpeg`）：`ffmpeg -i in.wav -b:a 192k out.mp3`。
- 使用者說「念給我聽」「播出來」才設 `play=true`；只要檔案就不要播。macOS 用內建的 afplay 播放，Windows 用內建的 winsound。

## 模型與額度

- 一律用 `gemini-3.8-flash-tts`。只有使用者明確要求才用 `gemini-3.8-flash-lite-tts`。
- 額度和帳單是按 **Google 專案**計算（不是按金鑰）。這台電腦設定的是免費版還是付費版，看 `check_setup` 的 `tier`／`quota_note`（設定檔：`~/.claude/mcp-servers/gemini-tts/settings.json` 的 `tier`）。
  - **免費版**：gemini-3.8-flash-tts 大約**每天 10 次、每分鐘 3 次**（2026-11 在 AI Studio 看到的數字，以 https://aistudio.google.com/rate-limit 為準），不論文字多短都算一次。免費版的內容可能被 Google 用來改善產品，使用者表示內容機密時要提醒。
  - **付費版**：每次請求從預付金扣款；預付餘額用完時 API 回 402，請轉告使用者到 https://aistudio.google.com/billing 儲值。
- 不論哪一種：不要沒必要地重新生成；能合併的短句放在**同一次**請求（例如多段旁白用 `<long pause>` 隔開，事後再依靜音切開）；長稿直接整段交給工具（約每 2000 字一個請求）。每次結果的 `used_today`／`quota_note` 會顯示這台電腦今天已用幾次。
- 工具不會卡住：每日額度用完會**立刻**回報重置時間（太平洋時間午夜，台灣 16:00，美國夏令時間期間 15:00；同一天不要重試）；伺服器沒回應約 150 秒就停止。
- 遇到 429／402／額度用完：把工具回傳的訊息轉告使用者，**先詢問**要等、儲值、改用 Lite，或（有安裝的話）改用本機 IndexTTS2，不要自動切換。不要建議用多個帳號輪流換金鑰規避額度（違反 Google API 條款）。

## 對話

- 剛好 2 位說話者、都用內建聲音：原生雙人生成，最自然、最省額度。
- 3 位以上或使用自訂聲音（`voice_...`）：工具會逐段生成再接起來，請求數較多，先跟使用者說明。
- 每句一個 turn：`{"speaker": "小明", "text": "…", "style": "可省略"}`。不要在 text 前面寫「小明：」。
- 附和、搶話可用 `|嗯|`、`|真的嗎？|` 夾在說話者的句子裡。

## 完成後回報

告訴使用者：檔案路徑、長度（秒）、使用的聲音；如果分成多個請求，說明分了幾次。
