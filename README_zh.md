CrewAI Writing Agent（JustKa AI）

本專案是一套可在生產環境落地的多代理系統，從 Reddit 擷取資料、發現內容機會，最後改寫成可直接上線的社群/內容文案。三個核心模組支持端到端或獨立運行：

- reddit_scraper：高品質 Reddit 擷取，支援彈性範圍與留言深度。
- content_opportunity_pipeline：趨勢分群、品牌契合與風險評估、主題簡報輸出。
- writing_agent：依平台生成成品文案，並提供可追溯引用與風格工具。

[English README](README.md)

關鍵特性
- 基於 CrewAI 的工具導向代理，輸入/輸出皆有明確 schema。
- 以 `dataset_id` 連結至原始貼文/留言，提供完整可追溯性。
- 針對 token 進行優化：寫作代理只接收精簡上下文；遇到需要引用時才用 `content_explorer` 取原文。
- 內建 Gemini 速率限制以及對「含雜訊 JSON」的強健解析。

快速開始
1) 環境
- Python 3.10+
- 建立並啟用虛擬環境：`python3 -m venv .venv && source .venv/bin/activate`
- 安裝依賴：`pip install -r requirement.txt`
- 設定必要 API 金鑰（例如 `GEMINI_API_KEY`）。

2) 執行模組
- 擷取器（v1–v4）：`python3 run_reddit_agent.py 1`（或 2/3/4）
- 內容管線（v1–v4）：`python3 run_content_opportunity_pipeline.py 1`
- 寫作代理（v1–v4）：`python3 run_writing_agent.py 1`

所有版本號皆對應 `Default_Tasks1.YML` 內的區塊，可快速切換不同作業模式。

輸出與資料存放
- 擷取結果：`scraepr_outputs/`（本地使用；已加入 .gitignore）
- 管線結果：`content_pipeline_outputs/`（已忽略）
- 寫作輸出：`writing_agent_outputs/`（已忽略）
- 資料集索引：`data_catalog/<dataset_id>/`（SQLite；已忽略）

架構（概覽）
- reddit_scraper：RAW → 正規化 →（選用）媒體分析。
- content_opportunity_pipeline：triage → 趨勢分析 → 品牌契合 → 主題策展。
- writing_agent：使用「精簡上下文」（機會+簡報），再透過 `content_explorer` 以 post_id 精準取材，輸出 `WritingAgentOutput` JSON（含平台版本、references、editorial_notes）。

Token 管理
- 寫作代理使用「精簡上下文」（只含精要資訊）。
- 不將各 Agent 的 raw log 直接塞進 prompt。
- 風格工具只回傳 preview 而非全文，避免對話暴增。

清除意外加入版本控制的產物
我們已將 `data_catalog/`、`writing_agent_outputs/`、`scraepr_outputs/` 加入 `.gitignore`。若先前誤推到遠端，可在本地保留檔案但移除追蹤：

```
git rm -r --cached data_catalog writing_agent_outputs scraepr_outputs
git commit -m "chore(repo): stop tracking generated artifacts"
git push
```

法遵與安全
- 請勿在擷取結果中包含敏感或具個資風險的內容。
- 請遵守 Reddit API/ToS 與相關法規。

