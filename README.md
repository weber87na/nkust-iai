# 高科大 iAI Skill

以 Python 標準函式庫操作高科大 iAI AIHub 的 Codex skill，提供繁體中文說明、可調參數與命令列工具。

## 功能

- 查詢帳號可用模型。
- 文字對話、訊息歷史與可選串流。
- 語音辨識、文字轉語音。
- 文字向量化與檢索結果重排序。
- 文字生圖，以及使用參考圖編輯圖片。
- 本機請求預覽、回應保存、base64 圖片解碼與遮蔽敏感值的錯誤診斷。

## 使用

需要 Python 3.10+，CLI 不需要安裝其他 Python 套件。先在本機設定 `IAI_API_KEY` 環境變數；金鑰不放入檔案、Git 或前端程式。

### 設定 IAI_API_KEY 環境變數

請先從 [高科大 iAI 官網](https://www.iai.nkust.edu.tw/) 的「取得 API KEY」申請金鑰，再於本機設定。CLI 會讀取執行程序的 `IAI_API_KEY`；不會自動載入 `.env`，也不會自動讀取尚未繼承到目前程序的 Windows 使用者／系統變數。

#### Windows（PowerShell）

**只在目前 PowerShell 工作階段使用**（PowerShell 7.1+，輸入時遮蔽金鑰）：

```powershell
$env:IAI_API_KEY = Read-Host '輸入 iAI API Key' -MaskInput
```

**保存為 Windows 使用者環境變數**（先完成上面的輸入）：

```powershell
[Environment]::SetEnvironmentVariable('IAI_API_KEY', $env:IAI_API_KEY, 'User')
```

這會將金鑰保存到目前使用者的環境變數，不需要系統管理員權限。之後新開的程序會繼承設定；已開啟的終端機或 Codex 請重新啟動，讓新設定生效。使用舊版 Windows PowerShell 時，也可從 Windows「環境變數」設定畫面新增同名的使用者變數。

確認目前程序已讀到設定，只顯示是否存在，不輸出金鑰內容：

```powershell
-not [string]::IsNullOrWhiteSpace($env:IAI_API_KEY)
```

回傳 `True` 代表目前程序已設定此變數；金鑰是否有效仍需用 `models` 請求確認。環境變數的值只填 API Key 本身，不加 `Bearer ` 前綴。不要將實際金鑰貼到 README、聊天或提交進 Git。

#### macOS（zsh）

在 zsh 終端機中設定目前工作階段使用的金鑰，輸入時不顯示內容，也不將金鑰寫進命令歷史：

```zsh
read -rs 'IAI_API_KEY?輸入 iAI API Key: '
printf '\n'
export IAI_API_KEY
```

若要每次開啟 zsh 都可使用，請以文字編輯器開啟 `~/.zshrc`，加入下列一行，並將佔位文字換成自己的金鑰：

```zsh
export IAI_API_KEY='你的_iAI_API_KEY'
```

儲存後，在終端機執行 `source ~/.zshrc`，或重新開啟終端機。若有自訂 `ZDOTDIR`，請改用該目錄下的 `.zshrc`。

#### Linux（bash）

在 bash 終端機中設定目前工作階段使用的金鑰：

```bash
read -r -s -p '輸入 iAI API Key: ' IAI_API_KEY
printf '\n'
export IAI_API_KEY
```

若要每次開啟互動式 bash 都可使用，請以文字編輯器在 `~/.bashrc` 加入：

```bash
export IAI_API_KEY='你的_iAI_API_KEY'
```

儲存後執行 `source ~/.bashrc`，或重新開啟終端機。使用 zsh 的 Linux 使用者請採用上面的 zsh 設定；其他 shell 的啟動檔與語法可能不同。排程、系統服務與桌面程式不一定載入這些 shell 設定檔，需在實際啟動 CLI 的環境設定同名變數。

macOS／Linux 可用以下指令確認目前 shell 是否設定金鑰，不會輸出金鑰值：

```sh
if [ -n "${IAI_API_KEY:-}" ]; then
  printf 'IAI_API_KEY 已設定\n'
else
  printf 'IAI_API_KEY 未設定\n'
fi
```

上述永久設定會把金鑰明文保存於個人的 shell 設定檔；不要將含金鑰的設定檔納入 Git 或公開分享。若要讓 Codex 使用，請從已設定變數的 shell 啟動，或確保其啟動環境有此變數；僅修改 `.zshrc`／`.bashrc` 不保證已開啟或由桌面啟動的 Codex 能讀到設定。

### 執行 CLI

在本儲存庫根目錄執行。Windows PowerShell：

```powershell
python .\nkust-iai\scripts\iai.py --help
python .\nkust-iai\scripts\iai.py models
python .\nkust-iai\scripts\iai.py chat --model Furen-large --prompt '用繁體中文說明 RAG' --dry-run
python .\nkust-iai\scripts\iai.py edit --model Pic-large --image reference.png --prompt '只將外套改成藍色，保持人物與背景不變' --n 1 --size 1024x1024 --timeout 300 --save-images output/edit-01
```

macOS／Linux（需安裝 Python 3.10+，指令通常為 `python3`）：

```bash
python3 ./nkust-iai/scripts/iai.py --help
python3 ./nkust-iai/scripts/iai.py models
python3 ./nkust-iai/scripts/iai.py chat --model Furen-large --prompt '用繁體中文說明 RAG' --dry-run
python3 ./nkust-iai/scripts/iai.py edit --model Pic-large --image reference.png --prompt '只將外套改成藍色，保持人物與背景不變' --n 1 --size 1024x1024 --timeout 300 --save-images output/edit-01
```

範例模型需以目前帳號權限為準。`--dry-run` 不發出請求；其他命令可能使用服務額度。若要讓 Codex 使用此 skill，將 `nkust-iai` 資料夾安裝到個人 Codex skills 目錄，入口為 `SKILL.md`。

## 文件

- [Skill 入口](nkust-iai/SKILL.md)
- [API 與參數](nkust-iai/references/api.md)
- [CLI 設定與旗標](nkust-iai/references/cli.md)
- [使用範例](nkust-iai/references/examples.md)
- [參考圖編輯、curl 與實測限制](nkust-iai/references/image-edit.md)
- [來源與排查](nkust-iai/references/sources-and-troubleshooting.md)
- [使用者提供的原始請求格式教材](iAI%20請求格式教學.md)

## 驗證與已知限制

```powershell
python .\nkust-iai\scripts\test_iai.py
```

macOS／Linux 使用 `python3 ./nkust-iai/scripts/test_iai.py`。

目前有 21 項本機測試，使用 loopback 模擬 API 與假金鑰，不連真實 iAI。

2026-10-23 已實際驗證 Pic-small／Pic-large 文字生圖與單張 PNG 參考圖編輯；當次編輯比較中 Pic-large 較能保留原圖特徵。圖片編輯採 `/v1/images/edits`，不使用當時存在回應轉換錯誤的 chat 出圖路徑。其他參數與能力依後端配置，不保證相容 API 的全部欄位都會生效。

模型進階參數查詢與 OpenAPI schema 對目前測試金鑰回傳權限限制，因此 seed、strength、mask 等未實測功能不能視為已支援。Speaker 的完整聲線與參考音檔能力也尚未確認。

版本控制只納入維護中的 skill 原始碼、文件及原始教材。本機金鑰、音檔、測試圖片、生成回應、查詢輸出、快取與 ZIP 套件都排除。
