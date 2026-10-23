# iAI API 參數與回應

來源以使用者提供的《iAI 請求格式教學.md》為主，並參照 2026-10-23 讀取的官方教學中心。這是文件整理與相容性實作，不是已通過帳號實測的服務規格。差異見 [來源與排查](sources-and-troubleshooting.md)。

## 目錄

1. 共通設定與認證
2. 模型清單
3. Chat Completions
4. ASR
5. TTS
6. Embeddings
7. Images 與對話出圖
8. Rerank
9. 條件式進階欄位

## 1. 共通設定與認證

| 項目 | 值／規則 |
|---|---|
| 官方網站 | `https://www.iai.nkust.edu.tw` |
| 教學中心 | `https://www.iai.nkust.edu.tw/setting` |
| API 金鑰申請 | 使用者教材列 `https://www.iai.nkust.edu.tw/apply`；目前網站的「取得 API KEY」會依登入狀態路由到申請／管理入口，優先從官網進入 |
| API base | `https://www.iai.nkust.edu.tw/aihub` |
| SDK base_url | `https://www.iai.nkust.edu.tw/aihub/v1`（SDK 自行附加資源路徑） |
| 預設認證 | `Authorization: Bearer <IAI_API_KEY>` |
| JSON 編碼 | UTF-8，`Content-Type: application/json` |
| ASR 編碼 | `multipart/form-data`，boundary 由 client 產生 |
| 預設逾時 | CLI socket I/O timeout 120 秒，可調；不是總執行秒數上限 |
| 重試 | CLI 不自動重試、不跟隨 HTTP redirect，不自動換模型／認證 |

`--auth bearer` 用一般 Authorization；`--auth litellm-bearer` 精確對應教材 rerank 的 `x-litellm-api-key: Bearer <key>`；`--auth litellm` 是可選相容模式，送 `x-litellm-api-key: <key>`。後者不是教材確認的格式，只有服務文件或管理員要求時才用。不同認證模式每次只送一個標頭，不自動嘗試其他組合。

模型 ID 大小寫原樣保留。沒有可靠資料可保證最大 token、檔案上限、並行數、速率、價格、圖片比例、音色或所有進階參數；需要時查詢官網／目前帳號權限，不自行填入固定限制。

## 2. 模型清單

`GET /v1/models`，無 body，也不需要 model。

教材的端點標題寫 POST，curl 範例寫 GET，因此 CLI 預設 GET，另提供 `--models-method POST`，兩者都不附 body。不要自動連續嘗試兩種方法。

典型相容格式（修正教材範例括號位置）：

```json
{
  "object": "list",
  "data": [
    {"id": "Furen-large", "object": "model", "owned_by": "openai"}
  ]
}
```

`data[].id` 是呼叫時使用的 ID。`owned_by` 等 metadata 不代表服務由該供應商提供，也不保證模型能力。不要將官網公開模型介紹清單等同本人的 API 授權清單。

## 3. LLM 對話

`POST /v1/chat/completions`

| API 欄位 | 型別 | 要求／意義 | CLI |
|---|---|---|---|
| `model` | string | 必填，LLM 模型 ID | `--model` |
| `messages` | array | 必填，多輪歷史 | `--messages messages.json` 或 `--prompt` |
| `messages[].role` | string | 一般 `system`、`user`、`assistant`；tool 等依模型 | JSON 檔 |
| `messages[].content` | string／array／null | 教材確認文字；多模態與工具格式需模型支援 | JSON 檔 |
| `temperature` | number | 選填，相容性延伸，依模型範圍 | `--temperature` |
| `max_tokens` | positive integer | 選填，相容性延伸，依模型 | `--max-tokens` |
| `stream` | boolean | 選填，相容性延伸，需支援 SSE | `--stream` |

最小 body：

```json
{"model":"Furen-large","messages":[{"role":"user","content":"你好"}]}
```

`--system` 會在訊息陣列最前方加一則 system 訊息；原本檔案的 system 不會自動刪除。`--prompt` 建立一則 user 訊息，不會自動續接歷史。需要多輪時自行保存 `messages`。

典型文字在 `choices[0].message.content`，完整 JSON 可保留 `usage`、`finish_reason` 與其他 choices。`--text-only` 取第一個 choice 的文字；沒有文字時回報錯誤，不把 tool calls／圖片當成空白成功。

串流原樣輸出 SSE，每個 `data:` 是事件而非完整 JSON 文件；結束常見 `data: [DONE]`。CLI 不拼接 delta，也不自動執行工具呼叫。`--stream` 不可配 `--text-only`／`--save-images`。

## 4. ASR 語音轉文字

`POST /v1/audio/transcriptions`，multipart。

| API 欄位 | 型別 | 要求／意義 | CLI |
|---|---|---|---|
| `file` | binary upload | 必填，本機音檔 | `--file recording.mp3` |
| `model` | string | 必填，教材範例 `Asr` | `--model Asr` |
| `language` | string | 選填，教材建議；`zh`、`en` | `--language zh` |
| `response_format` | string | 選填，教材常見 `json` | `--response-format json` |

CLI 會把其餘 body 欄位作為表單值，數字／陣列／物件序列化為 JSON 文字。`file` 只能用 `--file` 指向本機檔案；不能在 `--body` 假裝是檔案內容。上傳檔名會轉成 ASCII 安全名稱，檔案內容不變。

典型 JSON 回應：`{"text":"辨識出的文字"}`。其他格式（如 srt、vtt、verbose_json）屬模型相依延伸，不保證；若服務回傳純文字，CLI 可直接保存。`language=zh` 不保證輸出繁體中文，若再轉換／校訂，要保存原稿並說明後處理。

CLI multipart 會將整個音檔讀入記憶體，沒有自動切檔、壓縮、分段合併或逐段時間戳。大檔先查服務限制，必要時另作明確的切檔流程。

## 5. TTS 文字轉語音

`POST /v1/audio/speech`，JSON。

| API 欄位 | 型別 | 要求／意義 | CLI |
|---|---|---|---|
| `model` | string | 必填，教材範例 `Speaker` | `--model Speaker` |
| `input` | string | 必填，朗讀文字 | `--input`／`--input-file` |
| `voice` | string | 教材 curl 有 `taiwan_girl`，是否必填未說明 | `--voice taiwan_girl` |
| `response_format` | string | 選填，教材例 mp3／wav，依服務支援 | `--response-format mp3` |

```json
{"model":"Speaker","input":"歡迎使用高科大 iAI","voice":"taiwan_girl","response_format":"mp3"}
```

CLI 要求 `--output` 保存二進位回應，例如 `speech.mp3`；副檔名應與 response_format 一致。若省略 response_format，需自行確認模型預設格式。HTTP 200 回傳 JSON 或文字錯誤時，不把它寫成音檔。音檔保存不等於已驗證時長、編碼或發音品質。

## 6. Embeddings 向量化

`POST /v1/embeddings`，JSON。

| API 欄位 | 型別 | 要求／意義 | CLI |
|---|---|---|---|
| `model` | string | 必填，教材範例 `Embedding` | `--model Embedding` |
| `input` | string／string[] | 必填；批次輸入需服務支援 | 單筆 `--input`；批次 `--body` |
| `encoding_format` | string | 教材必填：float、base64、bytes、bytes_only | `--encoding-format`；CLI 預設 float |

```json
{"model":"Embedding","input":["高科大","人工智慧"],"encoding_format":"float"}
```

float 典型回應在 `data[].embedding`，利用 `data[].index` 對回輸入。base64／bytes 類回應結構未提供，CLI 不自行猜測向量 dtype、端序或維度。若收到非 JSON 二進位，必須 `--output embeddings.bin`。RAG 的建庫向量與查詢向量應使用同一模型與相同維度；不混用不同模型的座標空間。

## 7. 圖片生成

**2026-10-23 實測：優先使用 Images API。** `Pic-small` 在 `/v1/images/generations` 搭配 `n=1`、`size=1024x1024` 成功回傳 PNG（`data[].b64_json`）。相同模型與提示詞在 chat 路徑回 500，診斷顯示 LiteLLM 的 `Message.content` 預期 string，卻收到含 `image_url` 的 list；錯誤內容甚至夾帶已產生的圖片。屬服務端回應轉換問題，不是請求 JSON 格式不合法。僅此模型與組合經此次實測，其他尺寸／模型仍需確認。

### Images API

`POST /v1/images/generations`，JSON。

| API 欄位 | 型別 | 要求／意義 | CLI |
|---|---|---|---|
| `model` | string | 必填；教材欄位例 Pic-small、curl 例 z-image | `--model` |
| `prompt` | string | 必填，圖片提示詞 | `--prompt`／`--prompt-file` |
| `n` | positive integer | 選填；教材例 1 | `--n 1` |
| `size` | string | 選填；教材例 1024x1024 | `--size 1024x1024` |

```json
{"model":"Pic-small","prompt":"A sunset over the ocean","n":1,"size":"1024x1024"}
```

### Chat Completions 出圖

使用同一個 chat 端點，但選擇支援出圖的模型：

```json
{"model":"Pic-small","messages":[{"role":"user","content":"A sunset over the ocean"}]}
```

兩條路不保證每個模型都支援。上面的 chat payload 保留為教材形式，目前 Pic-small 已知有服務端轉換故障，優先選 Images API。失敗不自動換路徑重送。

教材表示通常回傳 base64，未定義唯一 JSON schema。CLI 的 `--save-images` 支援相容常見形式：

- `data[].b64_json`：純 base64。
- `choices[].message.images[].image_url.url`：`data:image/...;base64,...`。
- `choices[].message.content[]` 內的 `image_url.url`：data URI。
- `choices[].message.content` 直接為 image data URI。

這些 schema 是相容性處理，沒有全部經過 iAI 實測。只識別 PNG、JPEG、WebP、GIF 的檔頭，保存 `image-001.png` 等；不等於完整圖檔解碼／視覺驗證。未知結構先 `--output result.json` 保存，再依實際回應調整；不遞迴猜所有字串都是 base64。不自動下載 `https://...` 圖片 URL。

## 8. Rerank 文件重排序

`POST /v1/rerank`，JSON。

| API 欄位 | 型別 | 要求／意義 | CLI |
|---|---|---|---|
| `model` | string | 必填，教材範例 Furen-reranker | `--model Furen-reranker` |
| `query` | string | 必填，原始問題或搜尋字串 | `--query` |
| `documents` | string[] | 必填，候選文本陣列 | `--documents documents.json` |
| `top_n` | positive integer | 選填，回傳前幾筆 | `--top-n 3` |

```json
{"model":"Furen-reranker","query":"什麼是機器學習？","documents":["機器學習是 AI 的分支","今天晴天","深度學習使用神經網路"],"top_n":2}
```

若要精確對應教材認證，附 `--auth litellm-bearer`。一般 bearer 是否支援 rerank 尚未實測。

相容服務常見回傳 `results[].index` 與 `relevance_score`，但教材沒有提供回應 schema；保留完整 JSON，以實際欄位映射原文件。`index` 常見從 0 起算，需依實際服務確認；不要將 rerank 排名當成文件內容已經查證。

## 9. 條件式進階欄位

以下不在使用者教材保證範圍，只有已選模型文件支持或使用者要求測試時才傳。`--param` 可重複，巢狀值用 JSON，複雜資料建議 `--body` 檔案。

| 操作 | 延伸參數示例 | 注意 |
|---|---|---|
| chat | `top_p`、`seed`、`stop`、`presence_penalty`、`frequency_penalty` | 範圍與可重現性依後端；不與 temperature 同時任意調整 |
| chat | `max_completion_tokens` | 不自動與 max_tokens 同時送；模型可能只支援一種 |
| chat | `response_format={"type":"json_object"}` | 不保證 schema／JSON mode；prompt 也要要求格式 |
| chat | `tools`、`tool_choice`、`parallel_tool_calls` | 工具定義透傳；本 CLI 不執行 tool calls |
| transcribe | `prompt`、`temperature`、`timestamp_granularities` | 用 --param；表單陣列如何編碼依後端，CLI 是 JSON 文字而非重複欄位 |
| speak | `speed`、`instructions` | 聲線與範圍依模型 |
| embed | `dimensions`、`user` | 不能假設允許改維度 |
| image | `quality`、`style`、`response_format`、`seed`、`negative_prompt` | 不是每種圖片模型都接受 |
| rerank | `return_documents` | 回傳 schema 依服務 |

參考圖編輯已實作 `edit` → `POST /v1/images/edits`，使用 multipart 的 `image` 檔案欄位；Pic-small 與 Pic-large 均已實測。完整參數、品質差異與 curl 見 [image-edit.md](image-edit.md)。變體端點、二進位 mask、多張參考圖、Realtime、Responses 或微調仍未實作，不能自行拼湊未公告能力。
