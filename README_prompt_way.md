# 以「提示詞」動態配置三套工作流（Prompt → Workflow Directives）

本專案已將三條執行入口（run_content_opportunity_pipeline.py、run_writing_agent.py、run_reddit_agent.py）全面升級為「提示詞驅動」。

重點特性：
- 支援在自由文字提示中使用區段式指令（[section] 區塊），讓你以自然語言同時配置多個 Agent/任務的行為。
- 每個區段可以同時包含「說明文字」與「鍵值參數」。
- 當指令不完整時，系統保留安全的預設值（不會硬崩或亂猜）。

本文將完整說明：
1) 區段語法與解析方式
2) 各 run_*.py 支援的區段與參數
3) 範例（多組實戰樣式）

---

## 1. 區段式提示詞語法

支援兩種資料表達：

- INI/指令式：
  ```
  [section_name]
  key1 = value1
  key2: value2
  其他自然語言說明（將視為 instructions，會附加到該任務描述中）
  ```

- 純 JSON（整段為物件）：
  ```
  [section_name]
  {"key1": "value1", "key2": 2}
  ```

特殊區段名稱會被正規化為小寫並以底線連接（例如「Trend Analysis」→ `trend_analysis`）。

全域區段：`[global]`
- 這些說明與參數會被自動合併到各個階段的區段（例如 data_triage、strategy、scraper…）。

---

## 2. 各入口程式支援的區段與參數

以下列出每個 run_*.py 入口支援的區段、常見參數鍵，以及行為說明。注意：參數會被注入到對應任務的描述（description）中，因此屬於「強指令」，Agent 會據此優先採取行動；未提供時採預設行為。

### 2.1 run_content_opportunity_pipeline.py（內容機會管線）

支援區段
- `global`：對整條管線的通用說明與參數（會合併到各階段）。
- `config` / `brand` / `settings`：用來覆寫品牌知識庫路徑。
- `data_triage`（資料分揀）：定位原始 JSON 檔、讀取、並「立即匯出 SQLite」為預設行為。
- `trend_analysis`（趨勢分析）：叢集、動量、情緒、KOL。
- `brand_alignment`（品牌對齊/評分）：依品牌 KB 進行評分與排序。
- `topic_curator`（主題策展）：產出 Prioritized_Topic_Brief。

參數鍵（常用）
- `config`/`brand`/`settings` 區段
  - `brand_knowledge_base` | `brand_kb` | `brand_kb_path` | `kb_path`: 指向品牌知識庫檔案路徑。

- `data_triage` 區段（建議鍵，用來指示工具與篩選策略；未提供則以預設進行）
  - `target_files`：指定要處理的 scrape JSON 檔（路徑或檔名片段）。
  - `include_subreddits` / `exclude_subreddits`：要包含或排除的子版名稱。
  - `time_range`：時間範圍（例如 `7d`, `30d`）。
  - `sample_limit`：預覽樣本上限；未指定時仍會「先完整匯出 SQLite」。
  - `auto_export`：是否強制匯出（預設已啟用）。
  - `export_format`：匯出格式（預設 `sqlite`）。

- `trend_analysis` 區段
  - 可傳入任何輔助決策的鍵值（例如 `min_cluster_size`, `sentiment_model`），Agent 會視為操作指令。

- `brand_alignment` 區段
  - 可傳入 `risk_tolerance`, `icp_priority` 等鍵做權重指示。

- `topic_curator` 區段
  - 可傳入 `max_topics`、`angle_style`（如：教育、案例、對比）等偏好。

注意
- 實作上會將上述參數注入任務描述，成為 Agent 的強指令；非必要不硬性限制可用鍵。
- 品牌知識庫路徑是唯一會被入口程式直接讀檔處理的參數（其餘交由 Agent 依說明執行）。

### 2.2 run_writing_agent.py（寫作代理）

支援區段
- `global`：全域說明/參數（會合併到後述各階段）。
- `pipeline` / `context` / `data`：覆寫要讀取的內容機會管線輸出檔案或搜尋規則。
- `strategy`：策略藍圖（Editor in Chief）。
- `hook`：多平台 Hook 與敘事節奏。
- `writing`：產製不同平台的成品稿。
- `quality`：品質稽核與建議。

參數鍵（常用）
- `pipeline`/`context`/`data` 區段
  - `pipeline_output_path` | `pipeline_file` | `pipeline_path`: 直接指定管線輸出 JSON 檔。
  - `pipeline_output_root` | `pipeline_root`: 由此根目錄下尋找最新檔案。
  - `pipeline_output_pattern` | `pipeline_pattern`: 搭配 root 的搜尋樣式（預設 `*_content_opportunity_pipeline.json`）。

- `strategy` / `hook` / `writing` / `quality` 區段
  - 可傳 `platforms`, `tone`, `max_variants`, `risk_notes_required` 等鍵自訂寫作策略、輸出數量與驗證清單。

注意
- 本程式會先驗證 `pipeline_context` 的完整性（dataset_id / briefs / scored opportunities）；缺失會直接報錯，避免「交接失誤」。

### 2.3 run_reddit_agent.py（Reddit 擷取代理）

支援區段
- `global`：全域說明/參數。
- `scraper` / `reddit` / `fetch`：具體擷取與展開參數。

參數鍵（常用）
- `subreddit`：如 `r/artificial`、`r/python`。
- `user`：如 `u/spez`（使用者貼文軌跡）。
- `limit`：貼文筆數上限。
- `sort`：如 `new`、`hot`、`top`（`best` 會自動解讀為 `top`）。
- `time_filter`：當 `sort=top` 時可用（如 `day`、`week`、`month`、`year`、`all`）。
- `comment_depth`：`0-10` 或 `all`（`all` 會展開整串留言）。
- `skip_media`：是否略過媒體抓取。
- `timeout`：工具呼叫逾時秒數。

注意
- 上述鍵若在區段內提供，Agent 會把它們視為操作指令並嘗試傳給對應工具的 JSON 參數。

---

## 3. 範例

### 3.1 單段最小化（全域說明）
```
幫我找出近 30 天品牌最適合的 Reddit 議題，並產出策略與成品。
```

### 3.2 內容機會管線：指定品牌 KB ＋ 分揀策略
```
[global]
請聚焦高互動串，並記錄任何資料缺口，不要憑空猜測。

[brand]
brand_kb = data/Brand_Core_Knowledge_Base_for_acme.yml

[data_triage]
target_files = scrapes/2025-10/*.json
include_subreddits = r/artificial, r/marketing
time_range = 30d
sample_limit = 200
```

### 3.3 寫作代理：覆寫管線檔案，並強化 Hook 與 QA 要求
```
[pipeline]
pipeline_output_path = content_pipeline_outputs/20251014/202510141504_content_opportunity_pipeline.json

[strategy]
請先明確列出「資料缺口」與「下一步建議」，再選 1 個 brief。

[hook]
max_variants = 3
tone = 實用、可信、可行

[quality]
risk_notes_required = true
請顯示核對清單（引用可追溯、避免誇大、避免敏感承諾）。
```

### 3.4 Reddit 擷取：多工具鏈狀操作
```
[scraper]
subreddit = r/artificial
sort = top
time_filter = week
comment_depth = all
limit = 100
skip_media = true

[global]
若遇到 API 限流，請降低速率，並改抓次佳的子版 r/MachineLearning。
```

### 3.5 綜合案例：從抓取 → 管線 → 寫作（跨三條入口）

1) 先執行 Reddit 擷取：
```
[scraper]
subreddit = r/artificial
sort = new
limit = 200
comment_depth = 0
```

2) 再跑內容機會管線：
```
[brand]
brand_kb = data/acme_brand_kb.yml

[data_triage]
target_files = scrapes/today/*.json
auto_export = true
```

3) 最後交給寫作代理：
```
[pipeline]
pipeline_output_root = content_pipeline_outputs
pipeline_output_pattern = *_content_opportunity_pipeline.json

[strategy]
請誠實列出資料缺口與下一步建議。

[writing]
platforms = facebook, x, threads
max_variants = 2
```

---

## 4. 常見問題（FAQ）

- Q：如果我同時在 `[global]` 與各區段都給了同名參數，哪個生效？
  - A：區段參數優先；`global` 會被合併進每個階段做為預設。

- Q：參數是不是一定要用上面列出的鍵？
  - A：不是。你可以新增任意鍵來表達意圖；Agent 會把它們視為操作指令。列出的鍵只是常見建議。

- Q：為何我的品牌名稱在離線 Demo 模式有英文化？
  - A：離線模式會用中立預設字串（Default Brand/英文化鍵詞），僅為無憑證環境快速演示，不影響正式運行。

---

若有更進階的需求（例如：自訂工具參數映射、加入新區段），歡迎擴充對應的 `crew.py` 與 `tasks.py`，目前架構已支援以「參數＋說明」直接擴大 Agent 指令面。

