# 版本紀錄

## 1.2.0（2026-11-09）— 跨平台安裝包

- 新增 `install.py`：Windows／macOS／Linux 通用。會尋找 Python 3.11 以上、備份舊版、建立虛擬環境、安裝固定版本的套件、用 `claude mcp add --scope user` 註冊、執行自我檢查。從不讀取金鑰。
- 新增 `INSTALL_FOR_CLAUDE.md`：使用者把 GitHub 網址交給 Claude Code，它就能判斷平台並一步一步引導。
- 新增設定金鑰小工具：`scripts/set-gemini-key.ps1`（Windows，隱藏輸入，存成使用者環境變數）、`scripts/set-gemini-key.command`（macOS，寫入 `~/.zshenv`，權限 600，並停用其他設定檔裡舊的金鑰設定）。
- macOS：找不到環境變數時，會自己從登入 shell 讀取金鑰（從 Dock 開的 App 讀不到 `~/.zshrc` 的問題）；播放改用內建的 afplay；`stop_audio` 真的能停止播放。
- 新增 `settings.json` 的 `tier`（free／paid），取代原本要手改程式的 `FREE_DAILY_LIMITS`；MCP 說明會依設定自動調整。
- 新增 `--verify-key` 和 `check_setup(verify_key=true)`：只查一次模型資訊，確認金鑰有效，不用語音額度。
- 新的錯誤說明：專案需要驗證（FREE_TIER_VERIFICATION_REQUIRED）、金鑰被判定外洩、401／403 的常見原因。
- 只有裝了 indextts2 skill 的電腦，錯誤訊息才會建議改用 IndexTTS2。
- 固定套件版本：google-genai 2.34.0、mcp 2.3.0、pydantic 2.14.2（需要 Python 3.11 以上）。
- 安全：輸出路徑不再展開任意環境變數（以前寫成 `%GEMINI_API_KEY%.wav` 會把金鑰變成檔名）；所有回傳訊息自動遮蔽金鑰；安裝時的 pip 不會拿到金鑰。
- 金鑰：使用者剛存的金鑰優先於 Claude 啟動時帶的舊金鑰（Windows 讀登錄檔；macOS 讀 shell 設定檔，結果會暫存一段時間）；只有找不到 GEMINI_API_KEY 才用 GOOGLE_API_KEY，並提出警告。
- 驗證金鑰時分辨「金鑰無效」和「暫時連不上 Google」；Google 回報上限 0 次時提供正確說明。
- 安裝程式：能找到 Claude 桌面 App 內建的 `claude` 指令；Mac 不會碰到會跳出開發者工具安裝視窗的 `/usr/bin/python3`；支援 Microsoft Store 版 Python；套件清單沒變就不重裝；只備份有變動的檔案；壞掉的虛擬環境會重建。

## 1.1.1（2026-11-09）

- 402（預付餘額用完）改成中文說明。
- 每日上限分成「免費額度」和「付費帳號的每日上限」兩種訊息。
- MCP 說明不再寫死「免費版」。

## 1.1.0（2026-11-09）

- 修正：免費額度用完時工具卡住約 30 分鐘、沒有任何提示。原因是 google-genai SDK 照伺服器的 `Retry-After`（約 12 小時）去睡覺。現在 SDK 不再自行重試 429：每日上限立刻回報重置時間，每分鐘上限最多等 60 秒重試，每個請求最多 150 秒。
- 新增本機使用次數紀錄 `usage.json`（依金鑰指紋分開，不存金鑰）。

## 1.0.0（2026-11-03）

- 第一版（Windows）：MCP 伺服器、命令列工具、Skill。
