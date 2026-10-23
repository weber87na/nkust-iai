# 來源、差異與排查

## 文件依據（2026-10-23，臺灣時間）

- 使用者提供的 `iAI 請求格式教學.md`：本 skill 的七類端點、核心必填欄位、範例模型與特殊認證的直接依據。已逐段閱讀；原檔保留於使用者專案，不需要另外複製或在 skill 安裝後依賴原檔。
- [官方教學中心](https://www.iai.nkust.edu.tw/setting)：一般網頁擷取器無法讀取，沙箱內 DNS 失敗；改用具網路權限的公開 HTTP 讀取，取得 HTML 與該頁引用的前端程式，確認它是動態教學中心，含圖文教材與影片入口。這不是已完整操作所有頁面互動的 UI 驗證。
- [教學中心公開文件清單](https://www.iai.nkust.edu.tw/iaibackend/api/documents)：不附認證讀取成功，列有「iAI 模型請求格式教學」、「Codex 串接 iAI 教學」、「ComfyUI 生圖教學資源包」。此端點僅作來源核對，不是 skill 的模型操作端點，不保證網站內部路徑長期穩定。
- 文件清單中「iAI 模型請求格式教學」指向 [Google 文件](https://docs.google.com/document/d/1BaG1DVN6YbeyDoT4Z0uw_ocCa71txZB-fNgA4LZ0Cso/edit?usp=sharing)。本次 API 內容依使用者提供的 Markdown，沒有宣稱另行讀取該雲端文件的最新全文。
- [官網模型頁](https://www.iai.nkust.edu.tw/models)、[服務狀態](https://www.iai.nkust.edu.tw/status)：供日後使用時查閱；本次未將其內容當成已驗證的模型權限或即時狀態。

來源版本可能變更。只把已讀到的資訊當依據，網頁上的公開內部標頭不作為使用者金鑰，不複製到 skill。

## 已處理的教材差異

2026-10-23 參考圖實測與參數發現：`POST /v1/images/edits` 透過 multipart image 欄位上傳單張 PNG，Pic-small／Pic-large 均 HTTP 200 並取得圖片；Pic-large 在當次改色任務較能保留原圖特徵。進階參數查詢受金鑰 llm_api_routes 權限限制。完整的可維護紀錄見 [image-edit.md](image-edit.md)；原始測試媒體及含 base64 的生成回應已依使用者要求移除，不把它們作為 skill 的依賴。

2026-10-23 補充實測：使用使用者本機金鑰重現 `Pic-small` chat 出圖 HTTP 500。遮蔽後 traceback 包含 `litellm ... Invalid response object`、`1 validation error for Message`、`content ... Input should be a valid string ... input_type=list`，並顯示上游已產生 image data URI。相同模型、同一提示詞改用 `POST /v1/images/generations`、`n=1`、`size=1024x1024` 成功，取得並開啟確認 1024×1024 PNG。這支持「chat 回應轉換不相容」的診斷，不支持「提示詞造成 500」的推斷。其他模型先前的 500 未保留細節，不能確認也有相同原因。

| 教材狀況 | 本 skill 的處理 |
|---|---|
| models 標題 POST、curl GET，還列 model 必填 | 預設 GET 無 body／model；提供 --models-method POST，將差異保留說明，不假裝已實測哪個唯一正確 |
| models 回應範例括號與 object 欄位位置不合法 | 文件提供合法的典型 JSON；CLI 保留實際回應 |
| Markdown 把 curl 的連字號、URL、JSON 符號大量跳脫 | 範例改成真正可執行的參數與合法 JSON，去除 URL 外的角括號 |
| 圖片欄位例 Pic-small，但 Images curl 例 z-image | 兩者均標成範例，強制從目前權限／使用者選擇取得模型，不內建固定出圖模型 |
| TTS 欄位表沒列 voice，但 curl 有 taiwan_girl | 提供選填 --voice，明示是否必填與聲線清單未確認 |
| rerank 用 x-litellm-api-key: Bearer，其他用 Authorization | 提供三種顯式認證；--auth litellm-bearer 對應教材，不自動改標頭重送 |
| Embedding 列 float/base64/bytes/bytes_only | 保留可選字串；預設 float，未知 binary encoding 保存原始 bytes，不猜向量結構 |
| 沒有可靠的限制與完整進階參數規格 | 不捏造 token／音檔上限、聲線清單、價格、速率、串流或工具支援 |

## 排查表

| 現象 | 優先檢查 | 後續處理 |
|---|---|---|
| 缺少金鑰 | 環境變數是否在執行 CLI 的同一 process 可見；--api-key-env 是名稱 | 使用者本機設定，不在聊天貼值；可先 dry-run |
| 401 | 金鑰有效性、是否重複 Bearer、auth 模式 | 依目前文件／管理員指示更正；不輪流猜 header |
| 403 | 帳號／模型權限、申請狀態 | 查自己的模型清單，必要時聯繫管理員 |
| 404 | base 少／多 /aihub 或 /v1；選錯端點 | CLI base 到 /aihub，SDK base 到 /aihub/v1 |
| 405 models | 教材 GET／POST 不一致 | 明確選 --models-method，不自動 fallback |
| 400／422 | 欄位型別、model、必填欄位、進階參數 | 先 dry-run，再縮小至教材最小 payload；不要用不明欄位掩蓋錯誤 |
| 模型不存在 | 權限、大小寫、教材範例已過期 | 用 models 清單中的精確 ID，不自行改成猜測的供應商模型名 |
| 413 | 音檔或 payload 太大 | 查目前限制；必要時先提出明確切檔方法 |
| 429 | quota／rate limit／併發 | 按服務資訊等待或減少請求；不要立即循環重送 |
| 5xx／逾時 | 網路、服務狀態、模型載入中 | 回報請求可能已執行；經使用者意圖支持才手動重試 |
| HTTP 3xx | 網址或服務路由變更 | 工具不跟隨，先驗證新 base 是否仍是使用者指定服務 |
| 無法解碼圖片 | schema 不在已知清單、URL 回應、base64 損壞 | 先保存原始 JSON；按實際欄位調整，不對任意字串猜解碼 |
| 輸出檔已存在 | 上次結果或重複命名 | 選新名稱；只有明確要取代才 --overwrite |
| 音檔無法播放 | 實際回應格式、Content-Type、副檔名、空檔 | 不只改副檔名；用播放器／媒體工具確認格式 |
| embedding 維度／檢索不合理 | 建庫與查詢模型、input index、encoding | 不混不同模型；必要時重新建庫 |
| JSON mode／tools／stream 不接受 | 該模型是否支持相容擴充 | 移除擴充或查最新文件，別承諾全支援 |

HTTP 錯誤 body 預設不印出，也不自動保存。可明確指定 `--error-output` 保存遮蔽後的診斷；工具移除目前金鑰、已知輸入文字、敏感鍵名、Bearer token 及圖片 data URI，限制讀取／保存大小。服務錯誤可能仍有內部主機資訊，分享前再檢查。不要把此診斷檔當作成功圖片來源。

## 維護與驗證

```powershell
python path/to/nkust-iai/scripts/test_iai.py
```

測試只用本機 loopback 模擬 API、測試用假金鑰與臨時檔，驗證 URL／method／body、multipart、認證、SSE、音檔保存、圖片解碼、無自動重試、redirect 不轉送與失敗情境。不能代替真實 iAI 金鑰、權限與模型整合測試。

`--dry-run` 不發網路請求，也不需要 key；可用於驗證範例語法。沒有執行真實模型推論時，交付與後續回覆要明說，不宣稱七種服務已全部上線測試成功。

skill 原始碼與安裝資料夾可以分開保存；修正後重新測試再同步，不把測試用 API key、原始網站 bundle 或使用者推論內容包進 skill。
