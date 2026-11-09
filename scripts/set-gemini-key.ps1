# set-gemini-key.ps1 — 把 Gemini API Key 存成 Windows「使用者環境變數」GEMINI_API_KEY
# 由使用者自己在這個視窗貼上金鑰；畫面只顯示 *，不會寫進指令歷史，也不會經過 Claude。
# 用法（Claude 會幫你開這個視窗）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File set-gemini-key.ps1
# 測試用：加上 -DryRun 只檢查格式、不儲存。
param([switch]$DryRun)

# 清理與檢查金鑰格式（測試時可以只載入這兩個函式：. .\set-gemini-key.ps1）
function Get-CleanKey([string]$Raw) {
    return ($Raw -replace '\s', '').Trim([char[]]@([char]34, [char]39))
}
function Test-KeyFormat([string]$Key) {
    return ($Key -match '^[A-Za-z0-9._~+/=-]+$') -and $Key.Length -ge 20 -and $Key.Length -le 512
}
if ($MyInvocation.InvocationName -eq '.') { return }

$ErrorActionPreference = 'Stop'
try { $Host.UI.RawUI.WindowTitle = 'Gemini TTS：設定 API Key' } catch { }

function Done([string]$msg, [int]$code) {
    Write-Host ''
    Write-Host $msg
    Read-Host '按 Enter 關閉這個視窗' | Out-Null
    exit $code
}

Write-Host ''
Write-Host '=== 設定 Gemini API Key（Windows）===' -ForegroundColor Cyan
Write-Host '1. 到 https://aistudio.google.com/apikey 複製你的 API Key。'
Write-Host '2. 回到這個視窗，按 Ctrl+V（或滑鼠右鍵）貼上，再按 Enter。'
Write-Host '   為了安全，畫面只會顯示 * 號，這是正常的。'
Write-Host ''

$existing = [Environment]::GetEnvironmentVariable('GEMINI_API_KEY', 'User')
if ($existing) {
    Write-Host "目前已經有 GEMINI_API_KEY（$($existing.Length) 個字元）。" -ForegroundColor Yellow
    Write-Host '貼上新的金鑰會取代它；不想變更就直接按 Enter。' -ForegroundColor Yellow
    Write-Host ''
}

$sec = Read-Host -AsSecureString '請貼上 Gemini API Key 後按 Enter'
$key = [System.Net.NetworkCredential]::new('', $sec).Password
$key = Get-CleanKey $key
Remove-Variable sec

if (-not $key) {
    if ($existing) { Done '沒有輸入，保留原本的金鑰。' 0 }
    Done '沒有輸入任何內容，沒有儲存。' 1
}
if (-not (Test-KeyFormat $key)) {
    $len = $key.Length
    Remove-Variable key
    Done "格式看起來不對（$len 個字元，或含有不該有的符號），沒有儲存。請重新複製整把金鑰再試一次。" 1
}

$len = $key.Length
if ($DryRun) {
    Remove-Variable key
    Done "DryRun：格式正確（$len 個字元），這次沒有儲存。" 0
}

[Environment]::SetEnvironmentVariable('GEMINI_API_KEY', $key, 'User')
Remove-Variable key
$saved = [Environment]::GetEnvironmentVariable('GEMINI_API_KEY', 'User')
if (-not $saved -or $saved.Length -ne $len) { Done '儲存失敗，請改用「環境變數」視窗手動設定（見 docs/02_設定金鑰_Windows.md）。' 1 }
Remove-Variable saved

try {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.Clipboard]::Clear()
    $cleared = $true
} catch { $cleared = $false }

Write-Host ''
Write-Host "已儲存到使用者環境變數 GEMINI_API_KEY（$len 個字元）。" -ForegroundColor Green
if ($cleared) {
    Write-Host '已清除剪貼簿（避免金鑰之後被不小心貼到別處）。如果有開「剪貼簿歷程記錄」（Win+V），也可以在那裡刪掉這筆。'
}
if ([Environment]::GetEnvironmentVariable('GOOGLE_API_KEY', 'User') -or [Environment]::GetEnvironmentVariable('GOOGLE_API_KEY', 'Machine')) {
    Write-Host '注意：這台電腦另外設定了 GOOGLE_API_KEY。Gemini TTS 用的是 GEMINI_API_KEY，' -ForegroundColor Yellow
    Write-Host '      但其他 Google 工具會優先用 GOOGLE_API_KEY；如果不需要，建議刪掉它。' -ForegroundColor Yellow
}
Done '完成！請回到 Claude 告訴它「金鑰設好了」。之後請完全結束 Claude 再打開（系統匣圖示 → 結束）。' 0
