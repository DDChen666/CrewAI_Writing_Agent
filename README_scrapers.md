# Scrapers 安裝與使用指南

本文件說明如何設定 Python 環境並使用指令列工具 `scraepr_test1.py` 來進行社群平台資料擷取。當前已知狀態：

- Reddit：可運作（使用官方 Data API，必要時會回退至 PullPush API）。
- Facebook、Threads、X/Twitter：程式碼存在但在部分環境下可能失敗或受網路限制影響；命令仍保留以利未來維護。

> 提示
> 若遇到網路封鎖或外部服務不可用，請改小測範圍（降低 `--limit`）或稍後再試。

## 先決條件
- Python 3.10 以上（已於 3.13.5 測試）
- 可用的 `python3 -m pip`

## 建立虛擬環境
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

## 安裝相依套件
```bash
pip install -r requirement.txt
```
`requirement.txt` 包含核心套件（`requests`、`facebook-scraper`、`snscrape`、`crewai`、`google-generativeai`）。

## Reddit 憑證（建議）
Reddit 主抓取流程走官方 OAuth Data API，需在 `.env` 設定：
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT`

若未設定，程式會嘗試回退至 PullPush API（功能有限、易受外部可用性影響）。

## 執行 Reddit 爬蟲
```bash
python scraepr_test1.py reddit <subreddit>
```
常用參數：
- `--limit N`：最多抓取 N 筆貼文。
- `--skip-media`：略過含媒體貼文。
- `--include-media`：包含含媒體貼文（與前一參數互斥）。

輸出檔會儲存在 `scraper.json` 內 `output_root` 指定的資料夾（預設 `scraepr/`），以日期資料夾 + 時戳檔名區分。

## 其他平台（目前可能不穩定）
以下命令目前用於介面保留，實際運行可能因環境或服務阻擋而失敗：
```bash
python scraepr_test1.py facebook <full_facebook_url>
python scraepr_test1.py threads <threads_url>
python scraepr_test1.py x <username>
```

## 預設測試情境（僅驗證部分流程）
執行簡單 Smoke Test（目前聚焦於可行流程）：
```bash
python scraepr_test1.py tests
```
執行後會在 `scraepr/` 目錄下輸出測試結果與彙整檔。

## 設定檔 `scraper.json`
關鍵欄位說明（節錄）：
- `reddit.max_posts`：預設抓取貼文數量。
- `reddit.skip_media_posts`：預設是否略過含媒體貼文。
- `reddit.comment_depth`：留言深度。
- `reddit.pullpush_base`：回退抓取時使用的 PullPush API 端點。
- `output_root`：輸出資料夾根目錄（預設 `scraepr`）。

## 停用虛擬環境
```bash
deactivate
```

