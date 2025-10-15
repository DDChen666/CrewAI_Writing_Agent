
# 如何建立與使用品牌核心知識庫 (`Brand_Core_Knowledge_Base`)

本文檔詳細說明了 `Brand_Core_Knowledge_Base_for_[YOUR_BRAND].yml` 檔案的用途、格式規範以及它在 CrewAI 自動化內容策略流程中的運作方式。請遵循本指南來建立您自己的品牌知識庫，以確保 AI Agent 能夠準確地為您的品牌生成內容策略。

## 1. 檔案用途

`Brand_Core_Knowledge_Base.yml` 是整個內容策略流程的**核心大腦**與**戰略羅盤**。它將您的品牌戰略、目標客戶、產品資訊和價值觀轉化為 AI Agent 可以理解和執行的指令。

**主要使用者**: `Brand Alignment Agent`

這個 Agent 會完整讀取此檔案的內容，並基於這些資訊完成以下核心任務：
- **評估品牌契合度 (Brand Fit)**：判斷外部趨勢或主題是否符合您的品牌定位與形象。
- **評估目標客戶對齊度 (ICP Alignment)**：分析主題能否解決您理想客戶 (ICP) 的痛點。
- **評估風險 (Risk Assessment)**：根據品牌禁忌 (Taboos) 識別並評分潛在的公關風險。
- **提供可行動洞察 (Actionable Insights)**：建議如何將高價值主題與您的具體產品或服務連結。

如果缺少這份文件或格式錯誤，`Brand Alignment Agent` 將無法做出準確的戰略判斷，後續產出的所有內容都可能偏離方向。

## 2. 如何使用

在執行 `run_content_opportunity_pipeline.py` 腳本時，您可以使用 `--brand-knowledge-base` 旗標來指定要使用的知識庫檔案。

### 指令範例

```bash
python run_content_opportunity_pipeline.py \
  --brand-knowledge-base "Brand_Core_Knowledge_Base_for_my_company.yml" \
  "分析師：請根據最新的 Reddit 數據，為我們找到新的內容機會。"
```
- 如果您不提供此旗標，系統將會嘗試加載預設的 `Brand_Core_Knowledge_Base_for_justka.ai.yml` 檔案。

## 3. YAML 格式規範

請**複製** `Brand_Core_Knowledge_Base_for_justka.ai.yml` 作為模板，並修改其中的**值**，但**不要修改鍵 (key) 和縮排結構**。

### 技術要求
- **檔案格式**: 純文字檔。
- **檔案編碼**: UTF-8。
- **語法**: 嚴格遵守 YAML 語法，特別是**使用兩個空格進行縮排**，不要使用 Tab 鍵。

### 結構與關鍵欄位說明

以下是各個區塊的詳細說明和填寫指南。

---

#### `brand`, `website`, `language`, `core_topics`
- **用途**: 定義品牌的基本身份。
- **範例**:
  ```yaml
  brand: "您的品牌名稱"
  website: "https://www.your-website.com"
  language: "zh-TW" # 主要溝通語言
  core_topics: ["核心主題1", "核心主題2", "核心主題3"]
  ```

---

#### `positioning`
- **用途**: 闡述您的市場定位，這是 `Brand Alignment Agent` 判斷品牌契合度的主要依據。
- **`tagline`**: 您的品牌口號。
- **`elevator_pitch`**: 30秒內能說清楚您是誰、解決什麼問題的電梯簡報。
- **`key_differentiators`**: 您的關鍵差異化優勢，AI 會用這些點來強化內容角度。
- **範例**:
  ```yaml
  positioning:
    tagline: "讓您的商務經驗 更智慧、更省力、更美好"
    elevator_pitch: >
      我們是「對話式商務 + 智慧營銷」的一站式 SaaS 平台...
    key_differentiators:
      - "多智慧體（AI Agents）協作..."
      - "標籤/分群 + 用戶旅程 + CDP..."
  ```

---

#### `ICP` (Ideal Customer Profiles) - **【極度重要】**
- **用途**: 定義您的理想客戶。這是 `Brand Alignment Agent` 評估**內容是否對目標客群有價值**的核心依據。
- **`persona`**: 客戶畫像的簡稱，例如 "成長型電商主理人"。
- **`pain_points`**: **(最關鍵)** 他們最大的痛點是什麼？AI 會優先尋找能解決這些痛點的主題。
- **`interests`**: 他們關心什麼？希望達成什麼目標？
- **`product_fit`**: 針對這個客群，您的產品哪些是 `must_have` (必備)，哪些是 `good_to_have` (加分項)。
- **範例**:
  ```yaml
  ICP:
    - persona: "成長型零售/電商主理人（1–50人）"
      pain_points:
        - "客服量大（重複QA/活動/物流），人力吃緊、易漏回"
        - "行銷訊息同質化、分眾/個人化不足，轉換率偏低"
      interests:
        - "LINE OA 增長/回流、私域精準行銷、導購自動化"
      product_fit:
        must_have: ["對話編輯 + 知識庫", "標籤/分群"]
        good_to_have: ["多智慧體協作", "RPA"]
  ```

---

#### `brand_values_and_taboos`
- **用途**: 設定品牌的行事準則與「紅線」，直接影響 AI 的風險評估。
- **`principles`**: 品牌的核心價值主張。
- **`taboos`**: **(最關鍵)** 品牌絕對不能碰觸的話題或行為。AI 會主動規避或標記與此相關的高風險主題。
- **範例**:
  ```yaml
  brand_values_and_taboos:
    principles:
      - "以用戶為核心..."
      - "AI 賦能而非噱頭..."
    taboos:
      - "追逐短期膚淺熱點而忽略商務落地與績效"
      - "不合規的用藥/醫療建議（需審核與人工覆核）"
  ```

---

#### `content_to_product_mapping`
- **用途**: 建立「內容主題」到「產品功能」的映射，讓 AI 在產出內容策略時，能提出具體的產品導流建議。
- **`topic`**: 一個高層次的內容主題。
- **`maps_to`**: 這個主題可以對應到哪些產品模組或功能。
- **`CTA`**: 針對這個主題，最適合的行動呼籲 (Call to Action) 是什麼。
- **範例**:
  ```yaml
  content_to_product_mapping:
    - topic: "對話式商務：從知識庫到 Botflow 的轉單術"
      maps_to: ["問答知識庫 + 校正", "對話編輯（可分群）"]
      CTA: "導入『標準/專業版』建置商品/QA 知識庫與導購劇本"
  ```

---

#### `tone_and_style`
- **用途**: 指導 AI 生成內容時的語氣和風格。
- **範例**:
  ```yaml
  tone_and_style:
    writing_voice: ["專業清晰", "以成長與效率為導向", "用數據佐證"]
    dos:
      - "以 KPI（轉換率/回覆率）陳述價值"
    donts:
      - "誇大 AI 效果、無數據支撐"
  ```

---

## 4. 快速建立您的檔案

1.  **複製**: 將 `Brand_Core_Knowledge_Base_for_justka.ai.yml` 複製並重新命名為 `Brand_Core_Knowledge_Base_for_[您的品牌名].yml`。
2.  **填寫基本資料**: 快速填寫 `brand`, `website`, `positioning` 區塊。
3.  **聚焦 ICP**: 花最多時間定義您的 `ICP`，特別是 `pain_points`。這是整個檔案的靈魂。
4.  **劃定紅線**: 在 `taboos` 中列出您最擔心的幾個風險點。
5.  **迭代完善**: 其他區塊（如 `product_suite`, `content_to_product_mapping`）可以後續逐步完善。先有核心的 `ICP` 和 `taboos` 就能讓系統開始有效地運作。

遵循以上規範，您將能充分發揮 CrewAI 內容策略流程的強大潛力。