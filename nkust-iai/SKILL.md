---
name: nkust-iai
description: 使用高科大 iAI AIHub API 查詢模型、執行對話、語音辨識、語音合成、向量化、文字生圖、參考圖編輯與文件重排序；提供可調參數的 Python CLI 與串接指引。適用於使用者指定高科 iAI、NKUST iAI 或 iai.nkust.edu.tw 的模型服務。
---

# 高科大 iAI

透過高科大 iAI AIHub 執行模型工作，或產生可直接使用的串接程式。回覆與文件預設採臺灣繁體中文，保留 API 原始欄位與模型 ID。

## 任務與文件

- 實際執行 API：使用 `scripts/iai.py`，Python 3.10+，僅需標準函式庫。使用本 skill 的實際絕對路徑，不假設目前工作目錄就是 skill 資料夾。
- 端點、認證、必填參數與回應：讀 [references/api.md](references/api.md)。
- 全部 CLI 參數、設定優先序、PowerShell、自訂 JSON、串流與輸出：讀 [references/cli.md](references/cli.md)。
- 自然語言呼叫範例、RAG 與 SDK 串接：讀 [references/examples.md](references/examples.md)。
- 參考圖生圖、人物／構圖保留、編輯 API 與 curl：讀 [references/image-edit.md](references/image-edit.md)。
- 來源差異、失敗排查與驗證範圍：讀 [references/sources-and-troubleshooting.md](references/sources-and-troubleshooting.md)。

## 執行原則

1. 預設 API base 是 `https://www.iai.nkust.edu.tw/aihub`，工具附加 `/v1/...`。只有需要 SDK 的 `/v1` base 時才附加一次，不混用網站管理後台端點。
2. 金鑰只從使用者設定的環境變數讀取，預設 `IAI_API_KEY`；不把它寫進指令、範例、檔案或前端。缺少金鑰時仍可完成程式與 `--dry-run`，請使用者在本機設定環境變數，不要求在聊天貼金鑰。
3. 模型隨帳號與時間不同。可先 `models` 查詢，或使用使用者明確指定的模型 ID。教學中的 `Furen-large`、`Asr`、`Speaker`、`Embedding`、`Pic-small`、`z-image`、`Furen-reranker` 都是範例，不保證可用。模型清單不一定含能力資訊，不只憑名稱判定支援語音或工具呼叫。
4. 保留指定模型與參數；未指定的進階參數通常省略，使用服務端預設。僅 Embeddings 在未指定時補 `encoding_format=float`。示範可用 `--dry-run`；使用者要求實際推論時可在既有授權範圍執行，不必逐次要求確認。
5. 不把 OpenAI 相容視為全部參數相容。`temperature`、`stream`、`tools`、尺寸與聲線依模型而異。額外欄位用 `--param` 或 `--body` 透傳；未知支援狀態要說明，不承諾成功。
6. 每次命令只送一次請求，不自動重送推論、不偷偷換模型或改認證重送。401/403 檢查金鑰與權限；429/5xx/逾時先回報，再依使用者意圖決定是否重試。逾時不代表伺服器沒有執行。
7. 回報實際模型、主要參數、結果與輸出路徑。`--dry-run` 是本機檢查，不能稱作 API 成功；HTTP 成功也不代表圖片、音檔或文字品質已驗證。
8. 排查 HTTP 錯誤時用 `--error-output error.json` 保留遮蔽後的原因。先分辨欄位驗證錯誤、上游連線失敗與逾時；不能只憑 500 推斷提示詞、內容政策或模型格式有問題。只有證據支持時才調整端點或參數。
9. 圖片生成優先用 `image`（Images API）。2026-10-23 已實測 `Pic-small` + `n=1` + `size=1024x1024` 成功；同日該模型的 chat 出圖因服務端 LiteLLM 將圖片陣列當字串驗證而回 500。這是可繞過的服務端相容性問題，不是 JSON 語法錯誤。chat 出圖只在服務修復或另有明確需求時使用；不將這次結果泛化到所有模型。
10. 使用參考圖時選 `edit --image <本機檔案>`，不把檔案路徑當文字提示詞。`Pic-small` 與 `Pic-large` 均已透過 `/v1/images/edits` 成功，單張 PNG、`n=1`、`size=1024x1024` 是已驗證組合。當次改色比較中 Pic-large 較能保留臉、盔甲與構圖，Pic-small 重繪較多；不是所有圖片的品質保證。收到圖片後檢查是否真正參考原圖，不能只依 HTTP 200 宣稱修改成功。

## 操作對照

| 需求 | 子命令 | HTTP 路徑 | 最小輸入 |
|---|---|---|---|
| 可用模型 | `models` | `GET /v1/models` | 金鑰；可切 `--models-method POST` |
| 文字對話／對話出圖 | `chat` | `POST /v1/chat/completions` | `--model`、`--prompt` 或 `--messages` |
| 語音轉文字 | `transcribe` | `POST /v1/audio/transcriptions` | `--model`、`--file` |
| 文字轉語音 | `speak` | `POST /v1/audio/speech` | `--model`、`--input`、`--output` |
| 文字向量 | `embed` | `POST /v1/embeddings` | `--model`、`--input` |
| 圖片生成 | `image` | `POST /v1/images/generations` | `--model`、`--prompt` |
| 參考圖編輯／圖生圖 | `edit` | `POST /v1/images/edits` | `--model`、`--image`、`--prompt` |
| 文件重排序 | `rerank` | `POST /v1/rerank` | `--model`、`--query`、`--documents` |

欄位也可由 JSON body 或 `--param` 提供。`transcribe` 與 `edit` 一律 multipart 上傳，不手填 boundary；音檔欄位是 `file`，參考圖欄位是 `image`。`speak` 保存二進位音檔；圖片只有收到已知 base64 結構才解碼，不自動下載遠端 URL。

## 快速開始（PowerShell）

先在本機設定 `IAI_API_KEY`，不用在聊天提供值。以下假設 skill 安裝在預設個人目錄：

```powershell
$iai = Join-Path $HOME '.codex/skills/nkust-iai/scripts/iai.py'
python $iai models
python $iai chat --model Furen-large --prompt '用三句話說明高科大 iAI' --dry-run
python $iai chat --model Furen-large --prompt '用三句話說明高科大 iAI'
python $iai edit --model Pic-large --image reference.png --prompt '只將衣服改成藍色，保持人物與背景不變' --n 1 --size 1024x1024 --timeout 300 --save-images output/edit-01
```

模型需換成帳號有權限使用的 ID。可先 `python $iai --help`。不要從網站 JavaScript 擷取或借用其他用途的認證值執行模型 API。
