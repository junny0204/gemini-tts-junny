# 取得 Gemini API 金鑰（一步一步）

> 適用：Windows、Mac 都一樣，全部在瀏覽器裡完成。約 3 分鐘。
> 資料整理於 2026-11；Google 的畫面偶爾會改版，按鈕位置可能略有不同，名稱大致相同。

## 你需要準備

- 一個 Google 帳號（Gmail 帳號即可）。
- 年滿 18 歲（Google 的規定）。台灣可以使用。
- 一支手機（只有在 Google 要求「驗證專案」時才會用到，見第 6 步）。

## 第 1 步：打開 Google AI Studio 的金鑰頁面

用瀏覽器打開：**https://aistudio.google.com/apikey**

- 還沒登入的話，會先出現 Google 登入畫面，登入你的帳號。
- 第一次使用 AI Studio 時，會跳出服務條款，勾選同意後按繼續（Continue）。
- 新帳號第一次進來，Google 通常會**自動幫你建立一個預設專案和一把金鑰**，這時第 2 步可以略過。

## 第 2 步：建立金鑰

1. 在「API Keys（API 金鑰）」頁面，按 **Create API key（建立 API 金鑰）**。
2. 跳出的視窗會請你選一個**專案（project）**：
   - 已經有專案（例如 Google 自動建立的預設專案）：**直接選它**。
   - 完全沒有專案：選建立新專案（Create project），名字隨意，例如「Gemini TTS」。
   - 不要為了多拿免費額度而另外多開專案：第二個以後的免費專案都要先用手機驗證（第 6 步），額度也不會因此合法地變多。
3. 按建立。列表中會多一把新金鑰。

> **什麼是「專案」？** 可以想成一個帳本。**免費額度和付費帳單都是按專案計算**，不是按金鑰；同一個專案開很多把金鑰，額度也不會變多。

## 第 3 步：複製金鑰

- 在金鑰那一列按**複製**圖示（兩個重疊方框）。
- 金鑰是一長串英文、數字和符號。2026 年 5 月以後建立的新金鑰可能以 `AQ.` 開頭，較舊的可能以 `AIza` 開頭，兩種都可以用。

## 第 4 步：把金鑰設定到電腦（不要貼到對話裡）

**請不要把金鑰貼到 Claude 的對話、Email、LINE、雲端筆記或 GitHub。** 金鑰就像密碼，外流可能被別人盜用，付費帳號還會被扣款。

請 Claude 幫你開「設定金鑰」視窗，你自己在視窗裡貼上：

- Windows：看 [02_設定金鑰_Windows.md](02_設定金鑰_Windows.md)
- Mac：看 [03_設定金鑰_macOS.md](03_設定金鑰_macOS.md)

## 第 5 步：查看額度、用量和帳單等級

| 想知道 | 去哪裡看 |
|---|---|
| 這把金鑰屬於哪個專案 | https://aistudio.google.com/apikey（金鑰列表上有專案名稱） |
| 專案是免費還是付費（Billing Tier 欄） | https://aistudio.google.com/projects |
| 每個模型的額度上限 | https://aistudio.google.com/rate-limit |
| 用了多少 | https://aistudio.google.com/usage |
| 預付餘額、儲值 | https://aistudio.google.com/billing |

## 第 6 步（有遇到才需要）：驗證專案

如果畫面或錯誤訊息出現「Verification needed（需要驗證）」或 `FREE_TIER_VERIFICATION_REQUIRED`：

這通常發生在**第二個以後的免費專案**，或不是在 AI Studio 建立的專案。

1. 到 https://aistudio.google.com/projects ，在該專案按 **Verify project** → **Verify device**。
2. 用手機掃畫面上的 QR code 完成。**不需要電話號碼或簡訊**，也不用裝 App。
   - iPhone：iOS 16.4 以上，而且要開啟「App 剪輯」（App Clips）。
   - Android：要有 Google Play 服務；已 root 或解鎖開機程式的手機無法完成。
3. 你在這個專案要有擁有者（Owner）或編輯者（Editor）權限。
4. 電腦、模擬器不能完成這一步；在同一個專案重新建立金鑰也不會跳過驗證。
5. 不想驗證的話，也可以改成替這個專案開通付費（第 7 步）。

## 第 7 步（選用）：開通付費

免費版的 gemini-3.8-flash-tts 每天只有大約 10 次請求（2026-11 的數字）。常用的話可以開通付費：

1. 到 https://aistudio.google.com/projects ，在你的專案的 **Billing Tier** 欄按 **Set up billing**。
2. 第一次設定：選國家、同意條款、填聯絡資料和付款方式（信用卡）。已有帳單帳戶的話直接選它。
3. 新帳號預設是**預付制**：設定好帳單後，還要到 https://aistudio.google.com/billing 按 **Buy credits** 買點數（畫面會顯示最低金額，通常約 US$5 等值，台灣約 NT$150）。只綁卡、沒買點數的話還不算開通。
4. 付款確認後才會升級：多半 10 分鐘內，銀行轉帳等方式可能要幾天。到 https://aistudio.google.com/projects 看 **Billing Tier** 欄變成付費等級（例如 Tier 1）才算完成。
5. 確認變成付費等級後，告訴 Claude「我開通付費了」，它會把工具設定改成付費版（`install.py --tier paid`）。

要注意：

- **Google Cloud 的「免費試用」（Free Trial，US$300 抵免額）不能拿來付 Gemini API**。選帳單帳戶時，不要選免費試用的那個。
- 預付金 **12 個月後到期**，原則上不退款。
- 預付餘額用完時，Gemini 會拒絕所有請求（錯誤 402），而且**不會自動退回免費版**，要儲值後才恢復。可以開自動儲值，或設定每月花費上限（https://aistudio.google.com/spend）。
- 價格（2026 年底前）：gemini-3.8-flash-tts 每 10 秒語音約 US$0.00225（約 NT$0.07）；**2027 年 1 月 1 日起加倍**。最新價格以 https://aistudio.google.com/docs/pricing 為準。
- 付費版的內容不會被 Google 用來改善產品；免費版可能會，而且可能有人工審閱，請不要送出機密或個人資料。

## 金鑰外流了怎麼辦

1. 到 https://aistudio.google.com/apikey 建立一把**新**金鑰。
2. 用設定金鑰的視窗換成新金鑰（Windows 看 02、Mac 看 03）。
3. 確認新金鑰能用後，刪除舊金鑰（可在 https://console.cloud.google.com/apis/credentials 刪除）。
4. 到 https://aistudio.google.com/usage 檢查有沒有異常用量；付費帳號有異常扣款時，向 Google 帳單客服反映。

Google 偵測到外流的金鑰會自動停用，錯誤訊息是「Your API key was reported as leaked」，這時直接換新金鑰即可。
