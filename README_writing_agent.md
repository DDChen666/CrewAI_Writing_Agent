# Writing Agent

Writing Agent 透過 Content Opportunity Pipeline 產生的趨勢報告、品牌機會與策展簡報，將洞察改寫成可直接上線的社群或內容平台文案。此代理會：

- 自動尋找 `content_pipeline_outputs/` 目錄下最新的內容機會輸出（可透過 `Default_Tasks1.YML` 覆寫）。
- 解析四個核心 Agent 的 `raw` 輸出，同時僅將 Brand Alignment Agent 的 `scored_and_filtered_opportunities` 與 Topic Curator Agent 的 `prioritized_topic_briefs` 精簡傳遞給寫作流程，避免大型 JSON 造成 Token 壓力。
- 透過持久化於 `data_catalog/<dataset_id>/index.db` 的索引，使用 `content_explorer` 工具查詢 Reddit 原始貼文與留言，確保引用可回溯。
- 依照使用者指定或預設平台，呼叫 `facebook_writer`、`x_writer`、`thread_writer` 等風格工具，輸出符合 `WritingAgentOutput` schema 的 JSON。

## 快速開始

```bash
python3 run_writing_agent.py 1
```

`1` 將從 `Default_Tasks1.YML` 中載入 `writing_agent_default` 範本，其預設會：

1. 掃描 `content_pipeline_outputs` 中最新的 `*_content_opportunity_pipeline.json` 檔案。
2. 將使用者 prompt 視為改寫指示；若未指定平台，預設為 `facebook` 風格。
3. 在輸出 JSON 中包含：
   - `source_pipeline_file`：引用來源檔案路徑。
   - `dataset_id`：可透過 `content_explorer` 查詢 Reddit 原文。
   - `rewrites`：至少一個平台改寫結果（標題、主文案、CTA、Supporting Points、references）。
   - `editorial_notes`：編輯注意事項與風險假設。

## 自訂參數

- 在 `Default_Tasks1.YML` 的 `writing_agent_default` 區塊調整：
  - `pipeline_output_root`：指定搜尋的資料夾。
  - `pipeline_output_pattern`：指定檔名模式。
  - `default_rewrite_platform`：未開指令時的預設風格。
  - `prompt`：初始化改寫流程的詳細說明。
- 也可以複製既有區塊，建立新的 `task` 名稱並在執行時透過 `python3 run_writing_agent.py <task_id>` 呼叫。

## 工具組

Writing Agent 預設可呼叫以下工具：

| 工具 | 說明 |
| ---- | ---- |
| `content_explorer` | 從持久化索引讀取 Reddit 摘要、貼文正文、留言樹與原始 JSON。 |
| `facebook_writer` | 提供 Facebook 友善的語氣、結構與 CTA 建議。 |
| `x_writer` | 產出 X/Twitter 線程格式的節奏與文案指引。 |
| `thread_writer` | 提供 Threads / LinkedIn 風格的長文指導。 |

## 輸出儲存

`run_writing_agent.py` 會將有效 JSON 輸出儲存至 `writing_agent_outputs/<YYYYMMDD>/<timestamp>_writing_agent.json`。可在 CLI 結束時的 STDERR 查看實際檔案路徑。

## 依賴

- 需先執行 Content Opportunity Pipeline，並確保 `data_catalog/<dataset_id>/index.db` 已建立（Data Triage Agent 會自動持久化）。
- 需設定 `GEMINI_API_KEY` 使 Writing Agent 能呼叫 Gemini 模型。
