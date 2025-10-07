# Content Opportunity Pipeline Usage Guide

本文件說明如何在本地端執行 `crews/content_opportunity_pipeline` 相關指令，並整理每個 agent 可能觸發的錯誤情境與排查方式。

## 1. 目錄與組件結構

- **`crews/content_opportunity_pipeline/agents.py`**：定義四個核心 agent，分別負責資料分流、趨勢分析、品牌對齊與主題策展，所有 agent 預設使用 Gemini 2.5 Flash 模型並開啟 verbose 輸出。【F:crews/content_opportunity_pipeline/agents.py†L16-L104】
- **`crews/content_opportunity_pipeline/tools.py`**：提供 Reddit 資料定位、載入、過濾、匯出與查詢的工具，所有資料處理都透過這些工具完成。【F:crews/content_opportunity_pipeline/tools.py†L109-L343】【F:crews/content_opportunity_pipeline/tools.py†L344-L531】
- **`crews/content_opportunity_pipeline/tasks.py`**：描述每個任務的流程與期望輸出，並將上下游任務串接，確保每個 agent 都能取得前一階段的產出。【F:crews/content_opportunity_pipeline/tasks.py†L6-L72】
- **`crews/content_opportunity_pipeline/crew.py`**：建立 `ContentOpportunityPipelineCrew`，把四個 agent 與任務依照資料流順序組成一個可直接呼叫的工作流程。【F:crews/content_opportunity_pipeline/crew.py†L7-L52】

## 2. 指令操作方式

### 2.1 執行腳本

1. 進入專案根目錄後可直接執行：
   ```bash
   python run_content_opportunity_pipeline.py 1
   ```
   指令會讀取 `Default_Tasks1.YML` 中編號 `1` 的預設任務，並自動載入 JustKa AI 品牌知識庫。【F:run_content_opportunity_pipeline.py†L24-L38】【F:Default_Tasks1.YML†L1-L24】

2. 若要改成自訂指令，可改以自然語言輸入：
   ```bash
   python run_content_opportunity_pipeline.py "請分析最新的 r/marketing 討論"
   ```

3. 透過 `--brand-knowledge-base` 覆寫預設的知識庫檔案，例如：
   ```bash
   python run_content_opportunity_pipeline.py 1 --brand-knowledge-base /path/to/brand.yml
   ```
   CLI 參數的優先順序最高，其次為 `content_pipeline_config.json`，最後才是 `Default_Tasks1.YML` 中的設定。【F:run_content_opportunity_pipeline.py†L40-L75】

### 2.2 設定檔說明

- **`content_pipeline_config.json`（可選）**：用於自訂輸出目錄與預設品牌知識庫路徑。例如：
  ```json
  {
    "output_root": "content_pipeline_outputs",
    "brand_knowledge_base": "Brand_Core_Knowledge_Base_for_justka.ai.yml"
  }
  ```
  腳本會將執行結果以 JSON 形式寫入設定的輸出資料夾（預設 `content_pipeline_outputs/`）。【F:run_content_opportunity_pipeline.py†L58-L70】

- **`Default_Tasks1.YML`**：同時保留 Reddit 擷取與內容機會兩種預設任務，第二段對應 `content_opportunity_pipeline`，內含品牌知識庫的相對路徑與多階段指示流程。【F:Default_Tasks1.YML†L1-L24】

### 2.3 工具預設的採樣與預覽策略

- `reddit_scrape_loader` 只會在 `preview` 與 `focus_view` 中提供精簡欄位（post_id、title、score、permalink、body_preview、raw_pointer 等），並附上 `preview_truncated` 與 `focus_view_truncated` 旗標，預設最多僅展示 5 筆預覽資料，若需要更多內容請改以 `reddit_dataset_lookup` 取得。【F:crews/content_opportunity_pipeline/tools.py†L924-L979】
- `reddit_dataset_exporter` 的輸出改為 `content_stream.preview` 區塊，只保留必要欄位與彙總數據，同時標示 `truncated` 與 `limit`，避免在任務交接時塞入整批貼文資料。【F:crews/content_opportunity_pipeline/tools.py†L1061-L1103】
- `reddit_dataset_lookup` 與 `content_explorer` 在未指定 `limit` 或 `post_ids` 時會自動限制為 20 筆，並透過 `truncated` 或 `selection_truncated` 提醒使用者後續是否需要再取樣更多貼文。【F:crews/content_opportunity_pipeline/tools.py†L1015-L1042】【F:crews/content_opportunity_pipeline/tools.py†L1120-L1186】
- `content_explorer` 在 `data_level="full_comments"` 時會針對巢狀留言套用 100 筆的後代節點上限 (`descendant_cap`)，避免一次輸出過多留言樹；若觸發限制會在 `comment_summary.descendants_truncated` 顯示 true。【F:crews/content_opportunity_pipeline/tools.py†L1174-L1208】

## 3. Agents 可能觸發的錯誤與排查

| Agent | 可能的錯誤情境 | 排查建議 |
| --- | --- | --- |
| Data Triage Agent | `reddit_scrape_locator` 指定的資料夾不存在時會回傳 `status: error`；或 `reddit_scrape_loader` 未提供任何檔案時會報 `file_paths cannot be empty`。 | 確認 `scraepr_outputs/` 目錄存在且內含 JSON，必要時更新 `content_pipeline_config.json` 或手動指派檔案。若需要，可在命令前先執行 `run_reddit_agent.py` 產生資料。 |【F:crews/content_opportunity_pipeline/tools.py†L155-L206】【F:crews/content_opportunity_pipeline/tools.py†L236-L269】|
| Trend Analysis Agent | 使用 `reddit_dataset_lookup` 查詢未知的 `dataset_id` 時會回傳錯誤。 | 確認上一階段輸出的 `dataset_id` 是否帶入；如被清空，重新執行 Data Triage 取得有效 ID。 |【F:crews/content_opportunity_pipeline/tools.py†L461-L522】|
| Brand Alignment Agent | 若 `dataset_id` 有誤或已被移除，`reddit_dataset_filter`/`reddit_dataset_lookup` 會報錯；同時若品牌知識庫路徑錯誤，腳本會直接終止。 | 透過腳本輸出訊息確認知識庫路徑，必要時使用 `--brand-knowledge-base` 指定；檢查上一階段輸出的 dataset 資訊。 |【F:crews/content_opportunity_pipeline/tools.py†L385-L459】【F:run_content_opportunity_pipeline.py†L64-L72】|
| Topic Curator Agent | 依賴前一階段的 Scored Opportunities；若前一步驟失敗會導致無法產生 Brief。 | 先確保 Brand Alignment 階段成功執行並產出排序結果，再重新觸發流程。 |【F:crews/content_opportunity_pipeline/tasks.py†L47-L72】|

所有工具在發生錯誤時都會以 JSON 形式回傳 `status: "error"` 與訊息內容，`run_content_opportunity_pipeline.py` 會在輸出中保留原始訊息，方便追蹤。若結果為有效 JSON，腳本會額外存檔於 `content_pipeline_outputs/` 下的時間戳記資料夾中。【F:crews/content_opportunity_pipeline/tools.py†L155-L531】【F:run_content_opportunity_pipeline.py†L72-L77】

## 4. 與其他腳本的協作方式

- `run_reddit_agent.py` 仍可用於快速產生新的 Reddit 原始資料，其預設任務定義同樣集中在 `Default_Tasks1.YML` 中，並會把工具輸出寫入 `scraepr_outputs/` 目錄以供 Data Triage Agent 使用。【F:run_reddit_agent.py†L19-L75】【F:run_reddit_agent.py†L90-L118】
- 兩支腳本共用 `cli_common.py` 內的工具函式，包含預設提示解析、結果序列化與輸出寫檔邏輯，有助於維持一致的 CLI 體驗。【F:cli_common.py†L1-L153】【F:run_content_opportunity_pipeline.py†L13-L77】

## 5. 常見問題

1. **沒有安裝 `crewai` 時執行會失敗嗎？**  
   是，`crewai` 為必要套件，若未安裝會出現 `ModuleNotFoundError`。請先依專案需求安裝。

2. **如何自訂輸出檔名或格式？**  
   目前腳本固定輸出 JSON 並以 `YYYYMMDD/HHMM` 為檔名前綴，若需調整可修改 `cli_common.py` 中的 `ensure_output_path` 與 `persist_result_if_json` 實作。【F:cli_common.py†L82-L133】

3. **想只跑部分 agent 可以嗎？**  
   `ContentOpportunityPipelineCrew` 會一次執行四個任務，若需單獨測試某個 agent，可在互動式環境中直接呼叫對應工具或任務，再依需求客製化流程。【F:crews/content_opportunity_pipeline/crew.py†L16-L45】

透過上述步驟即可在本地端快速啟動內容機會評估流程，並掌握每個階段可能出現的狀況與解法。
