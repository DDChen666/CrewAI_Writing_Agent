# Reddit Agent 使用指南

本文件說明如何以自然語言驅動的方式，透過 CrewAI 代理整合 Reddit 官方 Data API 來擷取資料。代理的入口點為 `run_reddit_agent.py`，其會根據你的中文或英文指令，自動決定呼叫下列工具並回傳結構化 JSON：
- `reddit_subreddit_fetcher`：抓取子版面貼文與留言（偏列表型需求）
- `reddit_api_gateway`：任意 Reddit Data API 端點（當需求超出列表抓取時）

## 先決條件
- Python 3.10 以上（已於 3.13.5 測試）
- 可用的 `python3 -m pip`

## 建立與啟用虛擬環境
1. 於專案根目錄（`CrewAI_Writing_Agent`）建立虛擬環境：
   ```bash
   python3 -m venv .venv
   ```
2. 啟用：
   - macOS/Linux：
     ```bash
     source .venv/bin/activate
     ```
   - Windows（PowerShell）：
     ```powershell
     .venv\Scripts\Activate.ps1
     ```

看到 shell 提示開頭出現 `(.venv)`，代表環境已啟用。

## 安裝相依套件
啟用虛擬環境後安裝套件：
```bash
pip install -r requirement.txt
```

## 設定環境變數（.env）
在專案根目錄的 `.env` 檔設定以下變數（請勿將實際金鑰提交版本控制）：
- `REDDIT_CLIENT_ID`：Reddit 應用程式的 Client ID
- `REDDIT_CLIENT_SECRET`：Reddit 應用程式的 Client Secret
- `REDDIT_USER_AGENT`：自訂的 User-Agent（建議包含 app/版本 與 Reddit 帳號資訊）
- `GEMINI_API_KEY`：Google Generative AI（Gemini）API 金鑰

代理在內部使用 OAuth2 client credentials 流程取得 Reddit 存取權杖，並使用 Gemini 做任務規劃與工具選擇。程式已預設關閉 CrewAI 遙測。

## 執行方式
以自然語言下指令，代理會決定如何呼叫工具並回傳 JSON：
```bash
python run_reddit_agent.py "請抓取 r/Python 最新 30 則貼文（略過含媒體），並附每篇前 2 層留言"
```

更多範例：
- 「抓取 r/news 最新 10 則貼文，輸出標題、連結與分數」
- 「用 Reddit API 查詢 r/learnpython 的熱門貼文（本週），包含 upvote_ratio」
- 「找出 r/dataisbeautiful 最近 20 則且含圖片的貼文」

## 回傳格式（範例節錄）
工具任務的預期輸出為單一 JSON 物件，含解讀摘要與結果：
```json
{
  "request_summary": "抓取 r/Python 最新 30 則貼文並略過含媒體，附上前 2 層留言",
  "results": {
    "platform": "reddit",
    "subreddit": "Python",
    "items": [
      {"id": "abc123", "title": "...", "comments": [...], "statistics": {"score": 123, "num_comments": 4}}
    ]
  }
}
```

實際欄位會依請求而異。列表抓取時會偏向使用 `reddit_subreddit_fetcher`，需要更彈性的端點呼叫時則可能使用 `reddit_api_gateway`。

## 輸出檔案位置
- 成功取得的結構化 JSON（且 `status` ≠ `error`）會自動寫入 `scraper.json` 中 `output_root` 指定的位置（預設 `scraepr/`）。
- 檔案命名規則與 CLI 爬蟲一致：`scraepr/YYYYMMDD/YYYYMMDDHHMM_reddit_agent.json`。
- 終端仍會輸出同一份 JSON 內容，另在標準錯誤輸出顯示儲存路徑提醒。
- 若回傳為純文字或錯誤 JSON，則不寫檔。

## 常見問題
- 缺少 Reddit 憑證：`REDDIT_CLIENT_ID` 與 `REDDIT_CLIENT_SECRET` 必填，否則 OAuth 初始化會拋錯。
- 401/403：確認 Reddit 憑證正確、User-Agent 合理、與 API 使用限制。
- 429/速率限制：降低 `limit` 或增加重試間隔；避免短時間大量請求。
- Gemini 金鑰缺失：未設 `GEMINI_API_KEY` 會導致代理無法使用 LLM 規劃。
- 工具參數格式：代理呼叫工具時需提供有效 JSON 參數（程式已內建約束與驗證）。

## 進階說明（工具）
- `reddit_subreddit_fetcher` 參數：`subreddit`、`limit`、`skip_media`、`comment_depth`、`timeout`
- `reddit_api_gateway` 參數：`endpoint`、`method`、`params`、`data`、`json`、`timeout`

一般使用者僅需以自然語言輸入需求；若你熟悉 Reddit API，可在指令中更精確描述要呼叫的端點與參數，代理會盡量遵循並產生結構化結果。
