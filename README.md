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
CrewAI Writing Agent (JustKa AI)

This repository contains a production‑minded, multi‑agent system that discovers content opportunities from Reddit and rewrites them into channel‑ready copy. It is built around three crews that can be run end‑to‑end or independently:

- reddit_scraper: High‑quality Reddit data ingestion with flexible scopes and comment depth.
- content_opportunity_pipeline: Trend clustering, brand alignment scoring, and prioritized topic briefs.
- writing_agent: Platform‑specific rewrites with verifiable citations and style tools.

[中文說明 (Chinese)](README_zh.md)

Highlights
- Structured, tool‑driven agents using CrewAI with explicit schemas and outputs.
- Persistent dataset catalog with `dataset_id` tracing back to raw posts/comments.
- Token‑efficient prompting: condensed context for the writer, on‑demand fetch via `content_explorer`.
- Baked‑in Gemini rate limiting and robust JSON extraction for noisy model outputs.

Quickstart
1) Environment
- Python 3.10+
- Create and activate venv: `python3 -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r requirement.txt`
- Set API keys as needed (e.g., `GEMINI_API_KEY`).

2) Run the crews
- Scraper (v1–v4): `python3 run_reddit_agent.py 1` (or 2/3/4)
- Content Pipeline (v1–v4): `python3 run_content_opportunity_pipeline.py 1`
- Writing Agent (v1–v4): `python3 run_writing_agent.py 1`

Versioned prompts map to sections in `Default_Tasks1.YML` so you can quickly switch operating modes without editing code.

Outputs
- Scraped JSON goes to `scraepr_outputs/` (local‑only; now ignored by Git).
- Pipeline results go to `content_pipeline_outputs/` (ignored by Git).
- Final rewrites go to `writing_agent_outputs/` (ignored by Git).
- A persistent SQLite index lives under `data_catalog/<dataset_id>/` (ignored by Git).

Architecture (high level)
- reddit_scraper crew: discovers and loads RAW → normalized items → optional media analysis.
- content_opportunity_pipeline crew: triage → trend analysis → brand alignment → topic curator.
- writing_agent crew: consumes a condensed context (scored opportunities + briefs), fetches exact posts with `content_explorer`, and emits `WritingAgentOutput` JSON with platform variants and references.

Token discipline
- The writer uses a condensed context (top opportunities, top briefs, trimmed angles, capped links).
- Raw agent logs are not inlined into prompts.
- Writer tools return previews instead of full source text.

Cleaning mistakenly tracked artifacts
We’ve added `.gitignore` rules for `data_catalog/`, `writing_agent_outputs/`, and `scraepr_outputs/`. To remove previously committed files from the remote while keeping them locally, run:

```
git rm -r --cached data_catalog writing_agent_outputs scraepr_outputs
git commit -m "chore(repo): stop tracking generated artifacts"
git push
```

Legal and safety
- Do not include sensitive, personal, or proprietary data in scraped outputs.
- Respect Reddit’s API/ToS and all applicable laws.
