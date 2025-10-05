
現在 Google AI Studio / Gemini API 已經有「原生文生圖」可以直接用，而且 API 有免費層（有速率/配額限制）。最關鍵的兩件事：
官方文件已提供 gemini-2.5-flash-image 的 Python 調用範例（即俗稱 Nano Banana 的原生生圖/編輯能力）。(Google AI for Developers)

定價頁明確列出 免費層：例如 Gemini 2.0 Flash 的「Image generation pricing」在免費層為 Free of charge；Gemini 2.5 Flash Image 的計價跟 2.5 Flash 相同（免費層有免費 token 配額，預覽模型限速可能更嚴）。(Google AI for Developers)

下面給你「可直接跑」的 Python 最小範例（AI Studio 金鑰、原生生圖 & 影像編輯），再補充 Imagen 系列（屬付費 API，AI Studio 介面可有限度免費試玩）。

✅ 免費層可用：Gemini 原生文生圖（最佳首選）
安裝與初始化
pip install -U google-genai pillow
# 請先把 GEMINI_API_KEY 設為你的 AI Studio 金鑰

A) 文生圖（gemini-2.5-flash-image）
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client()  # 會自動讀取 GEMINI_API_KEY
prompt = "A cinematic photo of a snow fox, shallow depth of field, 85mm, golden hour"

resp = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=[prompt],
    config=types.GenerateContentConfig(
        # 僅輸出圖片（可省略，預設會同時回文字+圖）
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="16:9")  # 支援多種比例
    ),
)

# 存第一張圖
for part in resp.candidates[0].content.parts:
    if getattr(part, "inline_data", None):
        img = Image.open(BytesIO(part.inline_data.data))
        img.save("gemini_image.png")
        print("Saved gemini_image.png")
        break

這就是官方文件中展示的用法：用文字直接生成圖片，回傳在 inline_data，可存檔；也支援設定只輸出圖片與多種長寬比。(Google AI for Developers)
B) 影像編輯（以圖生圖 + 文字指令）
from google import genai
from google.genai import types
from PIL import Image

client = genai.Client()
prompt = "Remove the background and replace with a sunset beach, film look"

# 你要編的原始圖
base = Image.open("subject.png")

resp = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=[prompt, base],
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="4:5")
    ),
)

# 存編輯後圖片
for part in resp.candidates[0].content.parts:
    if getattr(part, "inline_data", None):
        Image.open(BytesIO(part.inline_data.data)).save("edited.png")
        print("Saved edited.png")
        break

官方指引同樣示範了「文字 + 圖片 → 新圖片」的工作流程（上傳、組合、樣式/局部變更等）。(Google AI for Developers)
關於「免費」怎麼算？
Gemini 2.0 Flash：定價頁明列 Image generation（免費層 = Free of charge）。(Google AI for Developers)

Gemini 2.5 Flash Image：文字/圖片輸入輸出 token 計價與 2.5 Flash 相同；免費層有額度（預覽模型速率限制更嚴，細節以官方定價頁為準）。(Google AI for Developers)

生成的圖片都會帶 SynthID 浮水印（可驗證來源）。(Google AI for Developers)


🧠（補充）Imagen 系列：更高保真，但屬付費 API
若你要 Imagen 4／Imagen 3 這類更高階的生圖模型，現在可直接用 Gemini API 的 generate_images；但 API 層屬付費（例如 Imagen 4 Fast/Standard/Ultra 分別 $0.02/$0.04/$0.06 每張；AI Studio 網頁介面有「有限度免費試玩」，但那不是 API 免付費）。(Google AI for Developers)
Python（付費）
from google import genai
from google.genai import types

client = genai.Client()
resp = client.models.generate_images(
    model="imagen-4.0-generate-001",
    prompt="Robot holding a red skateboard",
    config=types.GenerateImagesConfig(number_of_images=2)
)
for i, gi in enumerate(resp.generated_images, 1):
    gi.image.save(f"imagen4_{i}.png")

官方「Imagen」頁面提供相同結構的 Python/JS/REST 範例；開發者博客也宣布 Imagen 4 進入 Gemini API 與 AI Studio（AI Studio 可限量免費測）。(Google AI for Developers)


＃＃＃＃＃＃＃

2) 免費可用的「最佳 LLM：Google AI Studio（Gemini API）」Python 調用範例
特色：多模態（可上傳圖片/聲音/影片/PDF 等）、Google 搜索 Grounding、URL 讀取、Function Calling 一次搞定。
 需在 AI Studio 建立 API Key（免費層有額度與速率限制），並安裝官方 Python SDK google-genai。(Google AI for Developers)
安裝與初始化：
pip install -U google-genai

from google import genai
from google.genai import types

# 建議以環境變數 GEMINI_API_KEY 帶入，或直接傳 api_key 參數
client = genai.Client()  # 若未設環境變數：genai.Client(api_key="YOUR_KEY")
MODEL = "gemini-2.5-flash"  # 速度快、CP值高

2.1 上傳與理解「圖片 / 音訊 / 影片 / PDF」
Files API 讓你把檔案上傳後重複使用（48 小時保存；Files API 本身不收費）。上傳後直接把檔案物件丟進 generate_content 即可。(Google AI for Developers)
圖片範例（描述/抽取資訊）
img_file = client.files.upload(file="receipt.jpg")  # 也支援 .png/.webp 等
resp = client.models.generate_content(
    model=MODEL,
    contents=["請擷取這張發票的店名、日期、總金額，回傳 JSON。", img_file]
)
print(resp.text)

音訊範例（轉錄/摘要）
audio_file = client.files.upload(file="interview.mp3")  # 也支援 .wav 等
resp = client.models.generate_content(
    model=MODEL,
    contents=["請轉錄並摘要這段訪談，重點列點。", audio_file]
)
print(resp.text)

影片範例（逐段摘要/章節）
官方建議影片較大就先用 Files API，上傳後再生成內容。(Google AI for Developers)
video = client.files.upload(file="meeting_clip.mp4")
resp = client.models.generate_content(
    model=MODEL,
    contents=["將影片內容切成章節並加上時間戳記摘要。", video]
)
print(resp.text)

PDF 範例（長文文件擷取）
pdf = client.files.upload(file="spec.pdf")
resp = client.models.generate_content(
    model=MODEL,
    contents=["幫我摘要文件並萃取出 API 端點與參數表。", pdf]
)
print(resp.text)

Files API 使用說明（容量/時效/語法）見官方檔；亦有教學與文件處理指引可參考。(Google AI for Developers)
2.2 Google 搜索 Grounding（即時查證＋引用）
啟用 google_search 工具，模型會即時搜尋並在輸出中附上 citation/grounding metadata，提升時效與正確性（注意：此工具屬「每次使用計費項目」，但可在免費層額度內使用）。(Google AI for Developers)
grounding_tool = types.Tool(google_search=types.GoogleSearch())
cfg = types.GenerateContentConfig(tools=[grounding_tool])

resp = client.models.generate_content(
    model=MODEL,
    contents="台灣 2025 年 Q3 的央行利率決議重點為何？請附引用來源。",
    config=cfg,
)
print(resp.text)

官方指南（含 Python 範例與回傳的引用結構說明）。(Google AI for Developers)
2.3 URL 讀取（URL Context）
把特定 URL 丟給模型，讓它抓取並閱讀網頁/PDF內容（可與 Google 搜索一起用）。(Google AI for Developers)
tools = [{"url_context": {}}]  # 也可同時加 {"google_search": {}}
resp = client.models.generate_content(
    model=MODEL,
    contents="比較 https://pypi.org/project/google-genai/ 與 https://ai.google.dev/gemini-api/docs 的差異，列出優缺點表格。",
    config=types.GenerateContentConfig(tools=tools),
)
print(resp.text)

URL Context 支援多種內容型態、可一次處理最多 20 個 URL，並在回應中帶回 url_context_metadata 供你檢視實際擷取來源。(Google AI for Developers)
2.4 Function Calling（讓模型主動呼叫你的函式 / 外部 API）
用 function declarations 定義你可被呼叫的工具，模型會在需要時回傳 function_call 與參數；你執行後再把結果回填進對話即可。(Google AI for Developers)
from google import genai
from google.genai import types

client = genai.Client()

# 1) 宣告可被呼叫的函式（JSON Schema）
schedule_meeting_fn = {
    "name": "schedule_meeting",
    "description": "Schedules a meeting.",
    "parameters": {
        "type": "object",
        "properties": {
            "attendees": {"type": "array", "items": {"type": "string"}},
            "date": {"type": "string"},
            "time": {"type": "string"},
            "topic": {"type": "string"},
        },
        "required": ["attendees", "date", "time", "topic"],
    },
}

tools = types.Tool(function_declarations=[schedule_meeting_fn])
cfg = types.GenerateContentConfig(tools=[tools])

# 2) 讓模型決定是否呼叫函式
resp = client.models.generate_content(
    model=MODEL,
    contents="幫我在 2025-10-06 10:00 安排與 Alice、Bob 的 Q4 規劃會議。",
    config=cfg,
)

# 3) 若回傳 function_call，取出參數並在你的系統執行
fc = resp.candidates[0].content.parts[0].function_call
if fc:
    print("Model wants to call:", fc.name, "with args:", fc.args)
    # 這裡可真的去呼叫你的企業系統 / Google Calendar API 等
else:
    print(resp.text)

官方文件也有「強制呼叫 / 禁止呼叫 / 自動呼叫（Python SDK 可自動執行）」等模式範例。(Google AI for Developers)

速率與免費額度（AI Studio）
取得與管理 API Key：在 Google AI Studio 建立金鑰；SDK 會自動讀取 GEMINI_API_KEY。(Google AI for Developers)

免費層與速率限制：官方維護一頁「Rate limits」總覽（不同等級/模型會有 RPM/RPD 等限制；細節常調整，請以官方頁為準）。(Google AI for Developers)

Files API：可上傳並重用檔案、每檔最⼤ 2 GB、專案總量 20 GB、保存 48 小時，Files API 自身不收費。(Google AI for Developers)

Google 搜索 Grounding：屬「工具使用」的計費項目（一次請求內可能做多次搜尋但只計一次工具使用費用）；可在免費額度內用。(Google AI for Developers)