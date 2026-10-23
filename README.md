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

在本儲存庫根目錄執行：

```powershell
python .\nkust-iai\scripts\iai.py --help
python .\nkust-iai\scripts\iai.py models
python .\nkust-iai\scripts\iai.py chat --model Furen-large --prompt '用繁體中文說明 RAG' --dry-run
python .\nkust-iai\scripts\iai.py edit --model Pic-large --image reference.png --prompt '只將外套改成藍色，保持人物與背景不變' --n 1 --size 1024x1024 --timeout 300 --save-images output/edit-01
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

目前有 21 項本機測試，使用 loopback 模擬 API 與假金鑰，不連真實 iAI。

2026-10-23 已實際驗證 Pic-small／Pic-large 文字生圖與單張 PNG 參考圖編輯；當次編輯比較中 Pic-large 較能保留原圖特徵。圖片編輯採 `/v1/images/edits`，不使用當時存在回應轉換錯誤的 chat 出圖路徑。其他參數與能力依後端配置，不保證相容 API 的全部欄位都會生效。

模型進階參數查詢與 OpenAPI schema 對目前測試金鑰回傳權限限制，因此 seed、strength、mask 等未實測功能不能視為已支援。Speaker 的完整聲線與參考音檔能力也尚未確認。

版本控制只納入維護中的 skill 原始碼、文件及原始教材。本機金鑰、音檔、測試圖片、生成回應、查詢輸出、快取與 ZIP 套件都排除。
