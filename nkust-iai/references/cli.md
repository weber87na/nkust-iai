# CLI 參數與操作

## 執行環境與金鑰

Python 3.10+，不需 pip install、不需 OpenAI SDK。PowerShell：

```powershell
$iai = Join-Path $HOME '.codex/skills/nkust-iai/scripts/iai.py'
python $iai --help
```

若 skill 放在其他位置，將 `$iai` 指向其實際檔案。本機讀取金鑰可用 PowerShell 7 的遮罩提示，請使用者自行輸入，agent 不讀取或輸出值：

```powershell
$env:IAI_API_KEY = Read-Host '輸入 iAI API Key（僅本次 shell）' -MaskInput
python $iai models
```

`-MaskInput` 需要 PowerShell 7.1+。其他 shell 請用自己的安全環境變數設定方式。這只在目前 process／子程序有效，不會自動寫入使用者設定或 `.env`。CLI 不自動載入 `.env`。

CLI 的 `--base-url` 不含 `/v1`；OpenAI SDK 的 base_url 則含 `/v1`。預設只允許 HTTPS；為本機測試允許 loopback HTTP，金鑰不會跟隨 3xx 轉址。

## 設定優先序

同一 API body 欄位由低至高：

1. `--body request.json` 的欄位。
2. `IAI_MODEL`（只影響非 models 操作的 model）。
3. 明確的便利旗標，如 `--model`、`--temperature`、`--prompt`。
4. `--param KEY=VALUE`，最後出現的同名欄位勝出。

沒有明確 encoding_format 時，embed 補 float。其他未知欄位原樣保留。`--param` 是最上層覆寫，**沒有深層合併**：`--param 'response_format={"type":"json_object"}'` 取代整個 response_format；`foo.bar=1` 會送名為 `foo.bar` 的欄位，不會建立巢狀結構。

`IAI_MODEL` 可能覆蓋 body 原有模型；同一 shell 切換任務時，建議明確 `--model`，或移除環境變數。多任務需要不同模型時，不設全域 IAI_MODEL 也可以。

| 環境變數 | 預設 | 用途 |
|---|---|---|
| `IAI_API_KEY` | 無 | 認證；可用 --api-key-env 改讀其他名稱 |
| `IAI_BASE_URL` | 官方 `/aihub` URL | --base-url 未給時使用 |
| `IAI_MODEL` | 無 | 非 models 的模型後備值 |
| `IAI_TIMEOUT` | `120` | socket I/O timeout 秒；可用 --timeout 覆寫 |

認證模式沒有環境變數設定；明確用 `--auth`。沒有 config profile／自動重試，複雜模板直接用 JSON body。

## 共通旗標

| 旗標 | 型別／預設 | 說明 |
|---|---|---|
| `operation` | 必填 | models、chat、transcribe、speak、embed、image、edit、rerank |
| `--base-url` | URL | API root，省略 `/v1` |
| `--api-key-env` | string，IAI_API_KEY | 環境變數**名稱**，不是金鑰值 |
| `--auth` | bearer | bearer／litellm／litellm-bearer，見 API 文件 |
| `--timeout` | positive number，120 | socket I/O timeout；串流持續有資料時總時長可超過此值 |
| `--models-method` | GET | 僅 models 使用，GET／POST，不附 body |
| `--model` | string | 模型 ID，大小寫原樣 |
| `--body` | file path | UTF-8（可含 BOM）JSON object；transcribe／edit 作為表單欄位，二進位檔案另給 |
| `--param` | KEY=JSON_OR_TEXT，可多次 | 完整 JSON 可解析就保留型別，否則當字串 |
| `--output` | file path | 保存 JSON、文字、SSE 或 TTS 二進位 |
| `--error-output` | file path | HTTP 失敗時保存遮蔽敏感值的診斷 JSON；最多讀取 8 MiB，移除圖片 data URI 後保留最多 64 KiB 文字；不重試 |
| `--text-only` | false | 僅 chat／transcribe，抽取文字而非完整 JSON |
| `--save-images` | directory | 僅 chat／image／edit；解碼已知 base64 欄位 |
| `--overwrite` | false | 允許取代指定檔案；否則存在即失敗 |
| `--dry-run` | false | 不需金鑰、不發網路請求、不寫 output，只顯示檢查後的請求 |
| `--help` | — | 列出全部參數 |

`--dry-run` 隱藏認證值，但會顯示完整 prompt、文件與本機音檔路徑。分享預覽前自行刪除不應公開的內容。預覽只檢查本機型別與必填欄位，不能驗證帳號權限、模型是否存在與伺服器是否接受參數。

## 各操作便利旗標

| 操作 | 旗標 | 型別與行為 |
|---|---|---|
| chat／image／edit | --prompt、--prompt-file | 文字／UTF-8 文字檔，兩者擇一 |
| edit | --image | 必填本機單張參考圖，實際上傳欄位 image；dry-run 也檢查檔案存在 |
| chat | --messages | JSON array 檔，與 --prompt／--prompt-file 擇一 |
| chat | --system | 在 messages 前加 system 訊息；不刪除原有 system |
| chat | --temperature | finite number，模型決定合法範圍 |
| chat | --max-tokens | positive integer |
| chat | --stream | 啟用 raw SSE，支援狀態依模型 |
| speak／embed | --input、--input-file | 文字／UTF-8 文字檔，兩者擇一；input-file 不解析 JSON |
| transcribe | --file | 必填本機音檔，連 dry-run 也檢查是否存在 |
| transcribe | --language | zh、en 等字串；不強制選擇 |
| transcribe／speak／image／edit | --response-format | 字串；json、mp3、b64_json 等依操作與模型；圖片的此選項尚未實測 |
| speak | --voice | 聲線字串，例 taiwan_girl |
| embed | --encoding-format | 字串，預設 float；其他格式依服務 |
| image／edit | --n | positive integer，不假設最大張數 |
| image／edit | --size | 字串，不硬編尺寸白名單 |
| rerank | --query | 文字查詢 |
| rerank | --documents | JSON string array 檔 |
| rerank | --top-n | positive integer |

錯用便利旗標會失敗，例如 image --voice；刻意測試延伸欄位時用 --param，不會默默忽略。布林值使用 JSON `true`／`false`，null 使用 `null`；字串若恰好是數字或 true，必須給 JSON 引號以保留字串型別。

## 自訂 JSON 參數與 PowerShell 引號

簡單值：

```powershell
python $iai chat --model Furen-large --prompt '說明 embeddings' --param top_p=0.9 --param seed=42 --dry-run
```

巢狀值在 PowerShell 7.3+ 通常可這樣傳；舊版 PowerShell／原生命令引號行為不同時，優先改用 body JSON 檔，不用反覆堆疊跳脫：

```powershell
python $iai chat --model Furen-large --prompt '回傳 JSON 物件' --param 'response_format={"type":"json_object"}' --dry-run
```

穩定的檔案方式：

```powershell
@'
{
  "model": "Furen-large",
  "messages": [
    {"role":"system","content":"使用臺灣繁體中文，輸出 JSON 物件。"},
    {"role":"user","content":"列出三個 iAI 應用"}
  ],
  "temperature": 0.3,
  "response_format": {"type":"json_object"},
  "stream": false
}
'@ | Set-Content -LiteralPath request.json -Encoding utf8
python $iai chat --body request.json --dry-run
python $iai chat --body request.json --output answer.json
```

將範例 model 改為可用 ID。body 裡不要放 API key。上例 response_format 是模型相依延伸參數，非教材保證。

## 輸出規則

- JSON 預設印到 stdout；`--output` 保存 UTF-8 JSON。`--text-only` 保存文字，只保留第一個 chat choice 的文字，不含 usage 或其他 metadata。
- TTS 一定要 --output；收到 JSON／text Content-Type 時報錯，不保存假音檔。
- ASR 支援 JSON 或原始文字保存；若選 srt／vtt，就以 --output 存成對應副檔名。服務是否支援該格式需確認。
- Embedding 非 JSON 回應必須 --output，以原始 bytes 保存，不猜測向量格式。
- SSE 原樣逐行輸出或保存；中斷可能留下部分檔案。不是可直接 `json.load` 的單一 JSON。
- `--save-images images/run-01` 保存 image-001.png 等。不自動下載遠端 URL，未知結構會報錯。建議同時 --output response.json，保存原始 JSON 以便排查；沒有 --output 且有 --save-images 時不印出整段 base64。
- 已存在的 output 在送 API 前拒絕；圖片檔名須收到回應才能確定，因此圖片衝突是在推論後發現。每次生成使用新目錄，避免已生成卻因檔名衝突而無法保存。
- output 的父目錄會自動建立。--overwrite 的非串流輸出以暫存檔再取代；串流直接寫入，可能留下不完整內容。多張圖片整批先解碼及檢查已存在檔案，再依序保存；不保證整批磁碟寫入的交易性。
- 同時有 --output 與 --save-images 時先保存 JSON，再解碼圖片；若後者失敗，JSON 仍保留。CLI 不另存 request 或任何認證檔案。

## Exit code

| 值 | 意義 |
|---|---|
| 0 | 本機預覽成功，或請求與要求的保存／處理完成；不表示語意品質已驗證 |
| 2 | 參數／檔案／JSON／回應格式／解碼錯誤；若發生在收到回應後，API 可能已消耗額度 |
| 3 | HTTP 非成功狀態，包括不跟隨的 redirect |
| 4 | 網路／逾時錯誤，請求可能已送達 |
| 130 | 使用者中斷 |

錯誤預設不輸出伺服器完整 body。需要診斷時加 `--error-output error.json`，記錄 status、method、endpoint、model、request ID 及經遮蔽的服務錯誤；遮蔽目前金鑰、敏感鍵名、Bearer token 與請求中已知文字。這不是可公開分享的保證：服務錯誤仍可能帶有內部主機資訊，分享前再檢查。現有 error-output 會在發出請求前拒絕，除非 --overwrite。沒有自動重試、退避、斷點續傳或 API 金鑰申請自動化。
