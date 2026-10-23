# 參考圖生圖與圖片編輯

## 已驗證的端點與效果

`POST https://www.iai.nkust.edu.tw/aihub/v1/images/edits`，使用 multipart/form-data。

2026-10-23 以同一張 1024×1024 PNG 分別測試 `Pic-small`、`Pic-large`，要求只將紅色布料改成藍色，保持臉部、姿勢、盔甲與背景不變。兩者 HTTP 200，均回傳可解碼的 `data[].b64_json` 圖片：

| 模型 | 當次觀察 | 耗時（單次紀錄，非效能保證） |
|---|---|---|
| Pic-small | 延續站位、雨景與燈籠布局，但臉和盔甲被重畫，紅色衣料仍混雜藍色 | 約 34 秒 |
| Pic-large | 原圖的臉、姿勢、盔甲與背景高度保留，布料成功改為藍色 | 約 82 秒 |

需要保留原角色、只改服裝或局部內容時，可優先 Pic-large；需要自由重繪時再按需求比較。樣本各一張，沒有品質勝率或全場景保證。完成後必須查看結果，分辨原圖特徵保留程度和指令是否遵循。

測試媒體已依使用者要求清理，這份紀錄不依賴先前的圖片、base64 回應或測試路徑。

## 已驗證欄位與 CLI

| API 欄位 | CLI | 說明 |
|---|---|---|
| model | --model | 必填，已驗證 Pic-small／Pic-large |
| image | --image | 必填，本機單張參考圖，以 binary file part 上傳，不能填 JSON 路徑字串冒充上傳 |
| prompt | --prompt／--prompt-file | 必填，描述要修改與保留的內容，也可放 body JSON |
| n | --n | 選填，已驗證 1，不知道最大張數 |
| size | --size | 選填，已驗證 1024x1024，其他尺寸需測試 |

`--save-images` 指定保存圖片的目錄，`--output` 保存完整 JSON 回應，`--error-output` 保存失敗診斷，`--timeout` 調整 socket I/O timeout。`--dry-run` 只檢查檔案存在並列出路徑／位元組數，不上傳圖片、不印出 base64、不產生結果。

目前 CLI 僅實作單張參考圖，不支援多次 --image、圖片 URL 自動下載或二進位 mask 上傳。PNG 已實測，JPEG／WebP、檔案大小上限、透明背景、輸出比例等沒有完整的 iAI 規格，不套用其他供應商的限制。

```powershell
$iai = Join-Path $HOME '.codex/skills/nkust-iai/scripts/iai.py'
python $iai edit --model Pic-large --image reference.png --prompt '只將外套改成藍色；保留同一張臉、姿勢、背景與鏡頭構圖' --n 1 --size 1024x1024 --dry-run
python $iai edit --model Pic-large --image reference.png --prompt '只將外套改成藍色；保留同一張臉、姿勢、背景與鏡頭構圖' --n 1 --size 1024x1024 --timeout 300 --save-images output/edit-01 --output output/edit-01.json --error-output output/edit-01-error.json
```

每次使用新的結果目錄；除非明確要取代，勿加 --overwrite。只上傳使用者指定或此任務選用的參考圖，不尋找無關私人圖片。

## JSON body 與延伸參數

`--body edit.json` 只能提供表單欄位，圖片一律另用 --image。以下檔案可搭配 `python $iai edit --body edit.json --image reference.png --save-images output/edit-02`：

```json
{
  "model": "Pic-large",
  "prompt": "Keep the same person, pose and background. Change only the coat to cobalt blue.",
  "n": 1,
  "size": "1024x1024"
}
```

`--param` 也能加入 top-level 欄位；multipart 中的數字、物件與陣列會序列化為 JSON 文字。seed、strength、guidance_scale、步數、quality、input_fidelity、response_format 等不在此次實測保證範圍；只有明確要測試或取得服務規格時才加，不能把「沒有報錯」當作參數生效。

## 等價 curl（PowerShell）

事先由使用者在本機設定 IAI_API_KEY。此命令會把 reference.png 上傳到官方 iAI：

```powershell
curl.exe --request POST 'https://www.iai.nkust.edu.tw/aihub/v1/images/edits' `
  --header "Authorization: Bearer $env:IAI_API_KEY" `
  --header 'Accept: application/json' `
  --form-string 'model=Pic-large' `
  --form 'image=@reference.png;type=image/png' `
  --form-string 'prompt=Keep the same person, pose and background. Change only the coat to cobalt blue.' `
  --form-string 'n=1' `
  --form-string 'size=1024x1024' `
  --max-time 300 --fail-with-body --output edited-response.json

if ($LASTEXITCODE -ne 0) { throw '請求失敗，請檢查回應。' }
$response = Get-Content edited-response.json -Raw -Encoding utf8 | ConvertFrom-Json
if (-not $response.data[0].b64_json) { throw '回應沒有 b64_json。' }
[IO.File]::WriteAllBytes((Join-Path (Get-Location).Path 'edited.png'), [Convert]::FromBase64String($response.data[0].b64_json))
```

不要自行設定 Content-Type multipart boundary，交由 curl 或 CLI 產生。

## 進階參數規格的查詢限制

同日查詢 `/utils/supported_openai_params?model=...`（Pic-large／Pic-small／Speaker）、`/model_group/info`、`/model/info?model=Pic-large`、`/v1/models/Pic-large`，目前金鑰均回 403，明確僅允許 `llm_api_routes`。`/openapi.json` 也回 403；`/redoc` 雖回 200，仍引用被限制的 schema。`/public/model_hub` 回空陣列，`/public/model_hub/info` 只有通用服務資訊；無法據此取得模型完整參數。

這是目前金鑰與當日配置的結果，不代表其他帳號也一樣。需要完整欄位、型別、預設值、範圍與哪些欄位會被忽略時，向管理員取得規格；不繞過 403、不自動更換金鑰、不大批猜測或生成來試參數。
