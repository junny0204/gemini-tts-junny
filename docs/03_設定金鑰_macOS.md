# 在 Mac 設定 API 金鑰

金鑰會存成 shell 的環境變數 `GEMINI_API_KEY`，寫在你家目錄的 `~/.zshenv` 檔案裡（檔案權限設成只有你自己能讀）。Claude 不會看到金鑰內容。

還沒有金鑰？先看 [01_取得Gemini_API金鑰.md](01_取得Gemini_API金鑰.md)。

## 方法 A（推薦）：用「設定金鑰」小視窗

1. 跟 Claude 說「幫我開設定金鑰的視窗」。Claude 會打開一個「**終端機**」（Terminal）視窗。
   - 想自己開的話：打開「終端機」（應用程式 → 工具程式 → 終端機），貼上這行再按 Return：
     ```bash
     bash ~/.claude/mcp-servers/gemini-tts/scripts/set-gemini-key.command
     ```
2. 視窗出現「請貼上 Gemini API Key 後按 Return」時，按 **Cmd+V** 貼上金鑰，再按 **Return**。
   - 為了安全，畫面**不會顯示任何字**，這是正常的。
3. 看到「**已儲存到 /Users/你的名字/.zshenv（xx 個字元）**」就成功了。按 Return，然後可以關掉終端機視窗。
4. 回到 Claude 說「金鑰設好了」，Claude 會幫你確認金鑰有效。

這個小工具還會幫你處理舊設定：如果 `~/.zshrc`、`~/.zprofile` 等檔案裡有舊的 `export GEMINI_API_KEY=...`，它會先備份那個檔案（`檔名.bak-gemini-tts-日期`，權限設成只有你能讀），再把那一行換成不含金鑰的註解，避免舊金鑰蓋過新金鑰。確認新金鑰能用之後，備份檔可以刪除。存好之後它也會清掉剪貼簿，避免金鑰被不小心貼到別處。

> 原始碼在安裝包的 `scripts/set-gemini-key.command`，可以打開來看。它只把金鑰寫進你自己的 `~/.zshenv`，不會上傳到任何地方。

## 方法 B：手動編輯

1. 打開「終端機」，貼上下面這行按 Return（會用 nano 編輯器打開 `~/.zshenv`）：
   ```bash
   nano ~/.zshenv
   ```
2. 用方向鍵移到最後一行，貼上（把中間換成你的金鑰，前後保留**單引號**）：
   ```bash
   export GEMINI_API_KEY='你的金鑰'
   ```
3. 按 **Control+O**，再按 Return 存檔；按 **Control+X** 離開。
4. 貼上這行，把檔案設成只有你能讀：
   ```bash
   chmod 600 ~/.zshenv
   ```

> 不建議用「文字編輯」（TextEdit）改這個檔案：它可能自動把引號換成彎引號，金鑰就讀不到了。

## 為什麼放 `~/.zshenv`，不是 `~/.zshrc`？

macOS 的 zsh 每次啟動都會讀 `~/.zshenv`，包括不是在終端機裡啟動的情況；`~/.zshrc` 只有在互動式終端機才會讀。從 Dock 打開的 App（例如 Claude）不一定讀得到 `~/.zshrc` 的設定。另外，Gemini TTS 工具自己也會去讀 shell 設定，所以就算 Claude 沒帶到環境變數，工具仍然找得到金鑰。

（如果你的預設 shell 是 bash，小工具會改寫到 bash 登入時讀的檔案：`~/.bash_profile`、`~/.bash_login`、`~/.profile` 中第一個存在的；都沒有就建立 `~/.bash_profile`。以下 zsh 的指令，bash 使用者把 `~/.zshenv` 換成那個檔案、`zsh` 換成 `bash` 即可。）

## 讓 Claude 讀到新的金鑰

- Gemini TTS 工具會自己讀 shell 設定，所以設好之後馬上可以確認，不用重開。
- Claude 本身在啟動時才讀環境變數。為了讓一切一致，請找時間在 Claude 視窗按 **Cmd+Q** 完全結束，再重新打開。

## 確認有沒有設定好（不會顯示金鑰）

在終端機貼上：

```bash
zsh -c '[ -n "$GEMINI_API_KEY" ] && echo "已設定（${#GEMINI_API_KEY} 個字元）" || echo "沒有設定"'
```

（bash 使用者：`bash -lc '[ -n "$GEMINI_API_KEY" ] && echo "已設定（${#GEMINI_API_KEY} 個字元）" || echo "沒有設定"'`）

看到「已設定（xx 個字元）」就代表設定好了。

或請 Claude「檢查 Gemini TTS 的金鑰」（它會用 `--verify-key`，不會用到語音額度）。

## 更換金鑰

再做一次方法 A，貼上新金鑰即可（會取代舊的那一行）。

## 刪除金鑰

用方法 B 的 `nano ~/.zshenv` 打開（bash 使用者：`nano ~/.bash_profile` 或小工具顯示的那個檔案），刪掉 `export GEMINI_API_KEY=...` 那一行，存檔離開。

如果用過方法 A 的小工具，家目錄裡可能還有含舊金鑰的備份檔（檔名結尾是 `.bak-gemini-tts-日期`）。在終端機貼上這行可以列出它們（只列檔名，不顯示內容）：

```bash
ls -a ~ | grep bak-gemini-tts
```

確認不需要後，用 `rm ~/檔名` 刪除。

## 注意

- 不要在終端機直接打 `export GEMINI_API_KEY=你的金鑰`：這樣只對那一個視窗有效，而且金鑰會留在指令歷史紀錄（`~/.zsh_history`）裡。
- 如果設定檔裡另外有 `GOOGLE_API_KEY`：其他 Google 工具會優先用它，可能造成混淆。Gemini TTS 用的是 `GEMINI_API_KEY`。
- 「無法打開，因為無法驗證開發者」：改用方法 A 第 1 步「自己開」的那行指令（用 `bash` 執行，不受這個限制）。
