# 在 Windows 設定 API 金鑰

金鑰會存成 Windows 的「使用者環境變數」`GEMINI_API_KEY`。只有你的 Windows 帳號看得到，Claude 不會看到金鑰內容。

還沒有金鑰？先看 [01_取得Gemini_API金鑰.md](01_取得Gemini_API金鑰.md)。

## 方法 A（推薦）：用「設定金鑰」小視窗

1. 跟 Claude 說「幫我開設定金鑰的視窗」。Claude 會開一個 PowerShell 視窗（藍色或黑色）。
   - 想自己開的話：按開始，搜尋 **PowerShell**，打開後貼上這行再按 Enter：
     ```powershell
     powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\mcp-servers\gemini-tts\scripts\set-gemini-key.ps1"
     ```
2. 視窗出現「請貼上 Gemini API Key 後按 Enter」時，按 **Ctrl+V**（或按滑鼠右鍵）貼上金鑰，再按 **Enter**。
   - 為了安全，畫面只會顯示 `*`，這是正常的。
3. 看到綠色的「**已儲存到使用者環境變數 GEMINI_API_KEY（xx 個字元）**」就成功了。按 Enter 關閉視窗。
   - 它也會順便清掉剪貼簿，避免金鑰之後被不小心貼到別處（例如 Claude 的對話框）。
4. 回到 Claude 說「金鑰設好了」，Claude 會幫你確認金鑰有效。

> 這個小視窗只做一件事：把你貼上的金鑰存到你自己的 Windows 使用者環境變數，不會上傳到任何地方。原始碼在安裝包的 `scripts/set-gemini-key.ps1`，可以打開來看。

## 方法 B：用 Windows 的「環境變數」視窗

1. 按開始，搜尋「**環境變數**」，點「**編輯您的帳戶的環境變數**」。
   - 或請 Claude 幫你打開這個視窗。
2. 在上半部「**（你的名字）的使用者變數**」區塊，按「**新增(N)...**」。
3. 在「新增使用者變數」視窗：
   - 變數名稱(N)：`GEMINI_API_KEY`
   - 變數值(V)：貼上你的金鑰（前後不要有空白或引號）
4. 按「**確定**」關閉小視窗，**再按一次主視窗的「確定」**。只按第一次的話不會儲存。

## 讓 Claude 讀到新的金鑰

- Gemini TTS 工具會直接讀取 Windows 的設定（而且優先用你剛存的金鑰），所以設好之後馬上可以確認，不用重開。
- Claude 本身在啟動時才會讀環境變數。為了讓一切一致，請找時間**完全結束 Claude 再打開**：右下角系統匣的 Claude 圖示 → 右鍵 → 結束（Quit），再從開始選單打開。只關掉視窗不算結束。

## 確認有沒有設定好（不會顯示金鑰）

在 PowerShell 貼上：

```powershell
$v = [Environment]::GetEnvironmentVariable('GEMINI_API_KEY', 'User'); if ($v) { "已設定（$($v.Length) 個字元）" } else { '沒有設定' }
```

或請 Claude「檢查 Gemini TTS 的金鑰」（它會用 `--verify-key`，不會用到語音額度）。

## 更換金鑰

- 再做一次方法 A，貼上新金鑰即可（會取代舊的）。
- 或在方法 B 的視窗選取 `GEMINI_API_KEY` → 「編輯(E)...」→ 改變數值 → 確定 → 確定。

## 刪除金鑰

環境變數視窗 → 選取 `GEMINI_API_KEY` → 「刪除(D)」→ 確定。

## 注意

- 不要在 PowerShell 打 `setx GEMINI_API_KEY 你的金鑰`：金鑰會留在 PowerShell 的指令歷史紀錄檔裡，長度超過 1024 字元還會被截斷。
- 如果電腦另外設了 `GOOGLE_API_KEY`：其他 Google 工具會優先用它，可能造成混淆。Gemini TTS 用的是 `GEMINI_API_KEY`；不需要的話建議刪掉 `GOOGLE_API_KEY`。
