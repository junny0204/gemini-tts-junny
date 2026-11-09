#!/bin/bash
# set-gemini-key.command — 把 Gemini API Key 存進 macOS 的 shell 環境變數
#   zsh（macOS 預設）寫入 ~/.zshenv：每個 zsh（含不互動的）都會讀，App 也比較容易讀到。
#   bash 使用者寫入 ~/.bash_profile、~/.bash_login、~/.profile 中第一個存在的（都沒有就建立 ~/.bash_profile）。
# 由使用者自己在「終端機」視窗貼上金鑰；畫面不顯示、不會寫進指令歷史，也不會經過 Claude。
# 用法（Claude 會幫你開這個視窗）：
#   chmod +x set-gemini-key.command && open -a Terminal set-gemini-key.command
# 測試用環境變數：GEMINI_TTS_DRY_RUN=1 只檢查格式、不儲存；GEMINI_TTS_NO_PAUSE=1 結束時不等待。
# 只用 macOS 內建 bash 3.2 也支援的語法。
set +x
umask 077
printf '\033]0;Gemini TTS：設定 API Key\007'   # 視窗標題

tmp=""
cleanup() { [ -n "$tmp" ] && rm -f "$tmp"; }
trap cleanup EXIT

pause_exit() {  # 顯示訊息、等使用者按 Return，再結束
  printf '\n%s\n' "$1"
  if [ -z "${GEMINI_TTS_NO_PAUSE:-}" ]; then
    read -r -p "按 Return 關閉（之後可以關掉這個終端機視窗）" _ || true
  fi
  exit "$2"
}

# 一律寫到家目錄的檔案：新開的 shell 一開始一定先讀 ~/.zshenv（ZDOTDIR 通常是在這個檔案裡才設定）
login_shell="${SHELL:-/bin/zsh}"
case "$login_shell" in
  */bash)
    # 登入的 bash 只讀 .bash_profile、.bash_login、.profile 中第一個存在的檔案：寫進那一個
    rc=""
    for f in "$HOME/.bash_profile" "$HOME/.bash_login" "$HOME/.profile"; do
      [ -e "$f" ] && { rc="$f"; break; }
    done
    [ -z "$rc" ] && rc="$HOME/.bash_profile"
    ;;
  *) rc="$HOME/.zshenv" ;;
esac
re='^[A-Za-z0-9._~+/=-]+$'   # 長度另外檢查：macOS 的正規表示式重複次數上限是 255
export_re='^[[:space:]]*export[[:space:]]+GEMINI_API_KEY='

printf '\n=== 設定 Gemini API Key（macOS）===\n'
printf '1. 到 https://aistudio.google.com/apikey 複製你的 API Key。\n'
printf '2. 回到這個視窗（標題「Gemini TTS：設定 API Key」）按 Cmd+V 貼上，再按 Return。\n'
printf '   為了安全，畫面不會顯示任何字，這是正常的。\n\n'

if [ -L "$rc" ]; then
  pause_exit "$rc 是一個捷徑（符號連結），可能連到同步或版本控管的資料夾；為了不讓金鑰被上傳，這個工具不會寫入。請改用 docs/03 的方法 B 手動設定到你確定安全的檔案。" 1
fi
if [ -e "$rc" ] && [ ! -w "$rc" ]; then
  pause_exit "沒有權限寫入 $rc（可能曾用 sudo 編輯過）。請先在終端機執行：sudo chown \"${USER:-$(id -un)}\" \"$rc\"，再重新執行這個小工具。" 1
fi
if grep -qE "$export_re" "$rc" 2>/dev/null; then
  printf '%s 裡已經有 GEMINI_API_KEY。貼上新的會取代它；不想變更就直接按 Return。\n\n' "$rc"
fi

key=""
IFS= read -r -s -p "請貼上 Gemini API Key 後按 Return：" key || true
printf '\n'
key="$(printf '%s' "$key" | tr -d '[:space:]')"
key="${key#[\"\']}"
key="${key%[\"\']}"

if [ -z "$key" ]; then
  if grep -qE "$export_re" "$rc" 2>/dev/null; then
    pause_exit "沒有輸入，保留原本的金鑰。" 0
  fi
  pause_exit "沒有輸入任何內容，沒有儲存。" 1
fi
len=${#key}
if ! [[ $key =~ $re ]] || [ "$len" -lt 20 ] || [ "$len" -gt 512 ]; then
  unset key
  pause_exit "格式看起來不對（${len} 個字元，或含有不該有的符號），沒有儲存。請重新複製整把金鑰再試一次。" 1
fi
if [ -n "${GEMINI_TTS_DRY_RUN:-}" ]; then
  unset key
  pause_exit "DryRun：格式正確（${len} 個字元），這次沒有儲存（會寫入 $rc）。" 0
fi

# 1) 在暫存檔組好完整的新內容（舊的 export GEMINI_API_KEY= 行拿掉，最後加一行新的），檢查無誤再寫回
tmp="$(mktemp)" || pause_exit "無法建立暫存檔，沒有儲存。" 1
if [ -f "$rc" ]; then
  grep -vE "$export_re" "$rc" > "$tmp"
  [ $? -le 1 ] || pause_exit "讀取 $rc 失敗，沒有儲存。" 1
fi
printf "export GEMINI_API_KEY='%s'\n" "$key" >> "$tmp" || pause_exit "寫入暫存檔失敗，沒有儲存。" 1
unset key
if ! cat "$tmp" > "$rc"; then
  keep="$tmp"; tmp=""   # 不要刪掉：這是唯一完整的新內容
  pause_exit "寫入 $rc 時發生錯誤（例如磁碟已滿）。完整的新內容保留在 $keep（只有你能讀），請把它複製回 $rc，或改用 docs/03 的方法 B。" 1
fi
chmod 600 "$rc" 2>/dev/null
rm -f "$tmp"; tmp=""

# 2) 確認寫入成功：剛好一行 export GEMINI_API_KEY=，而且長度相同（不顯示內容）
count="$(grep -cE "$export_re" "$rc" 2>/dev/null)"
saved_len="$(grep -E "$export_re" "$rc" | tail -n 1 | sed -e "s/^[^=]*='//" -e "s/'[[:space:]]*$//" | tr -d '\n' | wc -c | tr -d ' ')"
if [ "$count" != "1" ] || [ "$saved_len" != "$len" ]; then
  pause_exit "儲存後檢查失敗（$rc 裡的設定不完整）。請改用 docs/03 的方法 B 手動設定。" 1
fi

# 3) 其他設定檔裡舊的 export GEMINI_API_KEY= 會蓋過新的設定：備份（權限 600）後，把那幾行換成不含金鑰的註解
stamp="$(date +%Y%m%d-%H%M%S)"
files="$HOME/.zshrc $HOME/.zprofile $HOME/.zlogin $HOME/.bash_profile $HOME/.bashrc $HOME/.profile"
if [ -n "${ZDOTDIR:-}" ] && [ "$ZDOTDIR" != "$HOME" ]; then
  files="$files $ZDOTDIR/.zshenv $ZDOTDIR/.zshrc $ZDOTDIR/.zprofile $ZDOTDIR/.zlogin"
fi
for f in $files; do
  [ "$f" = "$rc" ] && continue
  [ -f "$f" ] || continue
  if grep -qE "$export_re" "$f"; then
    if [ -L "$f" ] || [ ! -w "$f" ]; then
      printf '注意：%s 裡也有舊的 GEMINI_API_KEY，但這個檔案是捷徑或沒有寫入權限，請手動刪掉那一行。\n' "$f"
      continue
    fi
    bak="$f.bak-gemini-tts-$stamp"
    if ! cp "$f" "$bak"; then   # umask 077：備份一建立就是只有你能讀
      printf '注意：無法備份 %s，所以沒有修改它；請手動刪掉裡面 export GEMINI_API_KEY= 那一行。\n' "$f"
      continue
    fi
    chmod 600 "$bak"
    tmp="$(mktemp)" || continue
    awk -v note="# [gemini-tts] 舊的金鑰設定已移除，現在放在 $rc：export GEMINI_API_KEY=<已移除>" \
      '{ if ($0 ~ /^[[:space:]]*export[[:space:]]+GEMINI_API_KEY=/) print note; else print }' "$f" > "$tmp" \
      && cat "$tmp" > "$f"
    rm -f "$tmp"; tmp=""
    printf '已移除 %s 裡舊的 GEMINI_API_KEY 設定。\n' "$f"
    printf '  備份（含舊金鑰，只有你能讀）：%s ——確認新金鑰能用後可以刪除。\n' "$bak"
  fi
  if grep -qE '^[[:space:]]*export[[:space:]]+GOOGLE_API_KEY=' "$f"; then
    printf '注意：%s 設定了 GOOGLE_API_KEY。其他 Google 工具會優先用它；Gemini TTS 用的是 GEMINI_API_KEY。\n' "$f"
  fi
done

# 4) 清掉剪貼簿，避免金鑰之後被不小心貼到別的地方（例如 Claude 的對話框）
command -v pbcopy >/dev/null 2>&1 && pbcopy < /dev/null && printf '已清除剪貼簿。\n'

pause_exit "已儲存到 $rc（${len} 個字元）。請回到 Claude 告訴它「金鑰設好了」；之後完全結束 Claude 再打開（App：Cmd+Q；終端機版：/exit 後開新視窗）。" 0
