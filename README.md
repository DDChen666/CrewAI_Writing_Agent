# CrewAI Writing Agent（Reddit 代理與爬蟲）

這個專案整合了兩類能力：
- 以 CrewAI 建構的 Reddit 資料擷取代理（自然語言驅動）。
- 多平台爬蟲指令列工具（Reddit 可用；Facebook/Threads/X 介面保留，穩定性視環境而定）。

## 目錄結構（重點）
- `run_reddit_agent.py`：Reddit 代理（自然語言 → 工具 → 結構化 JSON）。
- `crews/reddit_scraper/`：代理的 Agents/Tasks/Tools 實作。
- `scraepr_test1.py`：多平台爬蟲 CLI 入口。
- `scrapers/`：各平台抓取實作（reddit/x/facebook/threads）。
- `scraper.json`：爬蟲設定（輸出路徑、平台預設值、回退策略）。
- `README_redditagent.md`、`README_scrapers.md`：分別對應代理與爬蟲的使用說明。

## 快速開始
1) 建立並啟用虛擬環境
```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows 請用 .venv\Scripts\Activate.ps1
```

2) 安裝套件
```bash
pip install -r requirement.txt
```

3) 設定 `.env`（至少包含 Reddit 與 Gemini 金鑰）
- `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET`、`REDDIT_USER_AGENT`
- `GEMINI_API_KEY`

4) 執行 Reddit 代理（自然語言介面）
```bash
python run_reddit_agent.py "抓取 r/Python 最新 20 則貼文並略過含媒體"
```

或使用爬蟲 CLI（結構化參數介面）：
```bash
python scraepr_test1.py reddit <subreddit> --limit 20 --skip-media
```

更多細節請見：
- `README_redditagent.md`
- `README_scrapers.md`

## 法律與使用注意
- 請遵守各平台的服務條款與 robots 規範。
- 請妥善保存 API 金鑰與私密資訊，不要提交到公開版本庫。
- 留意速率限制與個資法規，僅於合法、合規與授權範圍內使用所取得資料。
