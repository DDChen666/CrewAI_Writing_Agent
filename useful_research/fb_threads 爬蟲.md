
好的！在「**不自架節點、免費、免帳號登入、免瀏覽器自動化**」這四個前提下，能跑得通的 **fb / Threads** 抓取方案其實很有限。我幫你挑了 **3 個成功率最高**、而且目前（2025-10-06）仍可行的路線，並註明關鍵限制與風險：

---

## 1) Facebook 公開粉專 → `facebook-scraper`（純 HTTP，免登入）

**為什麼入選**
這個開源庫的定位就是「**抓 Facebook 公開頁面，不需要 API key**」，走的是 **requests 直抓 HTML** 而非瀏覽器自動化；對大多數「公開粉專」的貼文仍可用。([GitHub][1])

**能做到**

* 抓公開粉專在一段時間內的貼文（以 `page_posts` 迭代、你在本地用 `time` 欄位裁切時間窗）。
* 抓到基本互動數（reactions / comments / shares 解析自頁面）。

**重要限制 / 風險**

* 臉書會不定期加強反爬。社群回報 **大量抓取後會被要求登入或被 302 到登入頁**；建議低頻、加隨機延遲、輪替 UA。若遇到「此頁需登入」屬正常風控表現。([GitHub][2])

> 總結：**公開粉專**的「輕量、週期性」抓取成功率高；**社團/需登入內容**不適用。

---

## 2) Threads 公開頁 / 使用者時間線 → **純 HTTP 抓 `threads.net`**（免登入）

**為什麼入選**
Threads 的 **公開貼文與個人頁** 可直接以 `threads.net` **免登入瀏覽**（仍有速率門檻）；實務上可用 `requests` 取頁面，再從 HTML 內嵌的 JSON 或 API 輔助端點抽資料。([scrapfly.io][3])

**能做到**

* 指定帳號的一段時間內貼文（迭代時間、在本地用 `created_at` 或貼文 URL 序列裁切）。
* 也可做關鍵字過濾（先全量拉、後在本地過濾）。

**重要限制 / 風險**

* **速率限制**明顯，過快會出現 `HTTP 429`；需節流、退避重試。([Reddit][4])
* 某些欄位（例如更細的關聯名單）需要登入才看得到——**避用**。([scrapfly.io][3])

> 總結：不依賴任何登入與瀏覽器，**純 requests 就能跑**；控制好節流即可長期穩定。

---

## 3) Threads 公開時間線 → **RSSHub 公用路由（/threads/:user）**（免登入 / 免自架）

**為什麼入選**
RSSHub 提供 **Threads 的公開路由**（如 `https://rsshub.app/threads/zuck`），可直接以 **RSS/JSON** 拉資料，不需你這端登入或跑瀏覽器。對「固定幾個帳號、定期巡檢」特別省事。([rsshub.netlify.app][5])

**能做到**

* 以多個帳號做日更巡檢，抓到貼文時間、內容、連結，再由你這端以時間窗截取。
* 完全不需要基礎設施（先用官方公開實例）。

**重要限制 / 風險**

* 公開 demo 節點**有配額與不穩定**情況（官方 FAQ 也提示熱門站點容易被反爬影響）；量大或關鍵任務仍建議日後自架。你現在「暫不自架」可先用，低頻拉取成功率高。([docs.rsshub.app][6])

> 總結：最快上手、零維運；把它當 **暫時的「拉流入口」** 很實用。

---

# 不能入選的常見選項（為什麼我沒挑）

* **Meta/Graph 官方 API（Pages API、Threads oEmbed / 官方 Threads API）**：多數情境需要 **App Token / 審核或權限**，不符合你「免登入/免金流」前提（即使有些端點標稱可讀公開資料，實作上仍需 App/Token）。([developers.facebook.com][7])
* **Apify、商業 Threads API 供應商**：雖可免登入、穩定度高，但**非免費**。([Apify][8])
* **需要 Selenium/Playwright 的 Threads/Facebook 爬蟲**：和你的「免瀏覽器」條件相衝；即使標「headless 支援」，本質仍是瀏覽器自動化。([GitHub][9])

---

## 小型落地建議（依你前面 Twitter 的抓取模式對齊）

* **Facebook 公開粉專**：先以 `facebook-scraper` 低頻抓（例如每小時/每日），對單粉專日量 100–300 則很輕鬆；一旦遇到登入牆就降頻換粉專或暫停。([GitHub][1])
* **Threads**：

  * 量小：優先用 **RSSHub 路由**做定時拉；
  * 需要自定欄位或更完整 JSON：改走 **純 HTTP 抓 `threads.net`**，加上節流（按 429/Retry-After 退避）。([scrapfly.io][3])

> 法務提醒：抓取僅限**公開可見內容**；請遵守網站 TOS 與在地法規（個資/著作權）。通則參考近年法務總結：**公開頁面抓取通常可行，但不可繞登入、不可違反明示禁止條款，且須注意個資與著作權使用。** ([ScraperAPI][10])

如果你要，我可以把上述三條路線的「**最小腳本骨架**」（requests 版 Threads、`facebook-scraper` 版粉專、RSSHub 拉流與去重）一次生成給你，參數就照你前面 Twitter 任務的時間窗與帳號清單來配。

[1]: https://github.com/kevinzg/facebook-scraper?utm_source=chatgpt.com "kevinzg/facebook-scraper: Scrape Facebook public pages ..."
[2]: https://github.com/kevinzg/facebook-scraper/discussions/647?utm_source=chatgpt.com "Scraping without logging in + proxies #647"
[3]: https://scrapfly.io/blog/posts/how-to-scrape-threads?utm_source=chatgpt.com "How to scrape Threads by Meta using Python (2025 Update)"
[4]: https://www.reddit.com/r/ThreadsApp/comments/1e2y5jv/threads_web_rate_limit/?utm_source=chatgpt.com "Threads Web rate limit : r/ThreadsApp"
[5]: https://rsshub.netlify.app/routes/social-media?utm_source=chatgpt.com "social-media"
[6]: https://docs.rsshub.app/guide/faqs?utm_source=chatgpt.com "FAQs"
[7]: https://developers.facebook.com/docs/pages-api/overview/?utm_source=chatgpt.com "Overview - Facebook Pages API - Meta for Developers"
[8]: https://apify.com/curious_coder/threads-scraper?utm_source=chatgpt.com "Meta threads scraper"
[9]: https://github.com/Zeeshanahmad4/Threads-Scraper "GitHub - Zeeshanahmad4/Threads-Scraper: A Social media scraper for threads.net , The scraper allows you to collect various information about threads and users on Threads."
[10]: https://www.scraperapi.com/web-scraping/is-web-scraping-legal/?utm_source=chatgpt.com "Is Web Scraping Legal? The Complete Guide for 2025"
